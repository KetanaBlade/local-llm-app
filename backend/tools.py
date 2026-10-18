"""
Antigravity Agent Tool Suite & Sandbox Executor.

Provides structured local tools for:
1. create_excel_spreadsheet — Builds formatted .xlsx workbooks with formulas, styling, and live UI table previews
2. create_document — Generates .pdf and .docx documents with structured sections and tables
3. generate_visual_media — Generates REAL neural AI images via built-in GPU Stable Diffusion (`sd-cli.exe` + `DreamShaper 8`), high-DPI Matplotlib charts, or motion sequences
4. build_interactive_app — Creates self-contained interactive HTML/CSS/JS web apps with live preview
5. run_python_sandbox — Executes custom Python scripts and auto-captures any generated files as Artifacts
6. search_web — Searches DuckDuckGo when the user turns ON "Web Search Allowed" (blocked in Offline Mode)
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime
import difflib
import html
import json
import math
import mimetypes
import os
import platform
import random
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .database import register_artifact

ROOT_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = ROOT_DIR / "workspace"
ARTIFACTS_DIR = WORKSPACE_DIR / "artifacts"
PROJECTS_DIR = WORKSPACE_DIR / "projects"
SD_CLI_PATH = ROOT_DIR / "bin" / "sd" / ("sd-cli.exe" if platform.system() == "Windows" else "sd-cli")
SD_MODEL_DIR = ROOT_DIR / "models" / "image"

ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def confine_to_workspace(candidate: Path | str, base_dir: Path = WORKSPACE_DIR) -> Path:
    """
    Strict Path Confinement Boundary (inspired by Odysseus).
    - Blocks NUL bytes, newlines, and illegal escape characters.
    - Canonicalizes both base_dir and candidate using resolve().
    - Validates that os.path.commonpath([base_real, cand_real]) == base_real.
    - Fails closed on any path escape, symlink hop, or cross-drive access.
    """
    raw_str = str(candidate)
    if "\0" in raw_str or "\n" in raw_str or "\r" in raw_str:
        raise ValueError("Invalid path: illegal control characters detected")

    base_real = base_dir.resolve()
    cand_path = Path(candidate)
    if not cand_path.is_absolute():
        cand_path = base_real / cand_path
    cand_real = cand_path.resolve()

    try:
        common = Path(os.path.commonpath([str(base_real), str(cand_real)])).resolve()
        if common != base_real:
            raise ValueError(f"Path escape attempt blocked: '{cand_real}' is outside allowed '{base_real}'")
    except Exception as exc:
        raise ValueError(f"Access denied: path is outside allowed workspace ({base_real}): {exc}")

    return cand_real


RESTRICTED_SYSTEM_DIRS = [
    Path("C:/Windows").resolve(),
    Path("C:/Program Files").resolve(),
    Path("C:/Program Files (x86)").resolve(),
] if platform.system() == "Windows" else [
    Path("/etc").resolve(),
    Path("/bin").resolve(),
    Path("/sbin").resolve(),
    Path("/usr").resolve(),
]


def resolve_safe_path(
    candidate: Path | str,
    allow_outside_workspace: bool = True,
    base_dir: Optional[Path] = None,
) -> Path:
    """
    Resolve and validate file/directory path.
    - Resolves user home `~`
    - Blocks NUL bytes, newlines, and illegal escape control characters
    - If allow_outside_workspace is False, confines strictly to base_dir (defaults to WORKSPACE_DIR)
    - If allow_outside_workspace is True, allows user documents, projects, and drives while blocking Windows system directories
    """
    raw_str = str(candidate).strip()
    if not raw_str:
        raise ValueError("Path cannot be empty")
    if "\0" in raw_str or "\n" in raw_str or "\r" in raw_str:
        raise ValueError("Invalid path: illegal control characters detected")

    active_base = (base_dir or WORKSPACE_DIR).resolve()

    if raw_str.startswith("~"):
        p = Path(raw_str).expanduser()
    else:
        p = Path(raw_str)

    if not p.is_absolute():
        p = (active_base / p).resolve()
    else:
        p = p.resolve()

    if not allow_outside_workspace:
        try:
            common = Path(os.path.commonpath([str(active_base), str(p)])).resolve()
            if common != active_base:
                raise ValueError(f"Path escape blocked: '{p}' is outside allowed workspace '{active_base}'")
        except Exception as exc:
            raise ValueError(f"Access denied: {exc}")

    # Guard against OS critical system directories
    for restricted in RESTRICTED_SYSTEM_DIRS:
        is_restricted = False
        try:
            if restricted.exists() and (p == restricted or restricted in p.parents):
                is_restricted = True
        except Exception:
            pass
        if is_restricted:
            raise PermissionError(f"Access denied: '{p}' is inside protected system directory '{restricted}'")

    return p


def create_file_backup(path: Path) -> Optional[Path]:
    """
    Creates an automatic timestamped backup (.bak_YYYYMMDD_HHMMSS) before file modifications.
    """
    try:
        if path.exists() and path.is_file():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = path.with_name(f"{path.name}.bak_{ts}")
            shutil.copy2(path, backup_path)
            return backup_path
    except Exception:
        pass
    return None


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip().lower()).strip("_")
    return s[:48] or f"file_{int(time.time())}"


def _inspect_model_metadata(path: Path) -> tuple[str, str, bool]:
    """
    Returns (label, style, is_sdxl).
    Extracts embedded safetensors metadata or derives a human-readable label from filename.
    """
    name_lower = path.stem.lower()
    raw_title = ""
    arch = ""

    if path.suffix.lower() == ".safetensors":
        try:
            with open(path, "rb") as f:
                header_len = struct.unpack("<Q", f.read(8))[0]
                if header_len < 10 * 1024 * 1024:
                    header = json.loads(f.read(header_len).decode("utf-8", errors="ignore"))
                    meta = header.get("__metadata__", {})
                    raw_title = str(meta.get("modelspec.title") or meta.get("title") or meta.get("name") or "")
                    arch = str(meta.get("modelspec.architecture") or "")
        except Exception:
            pass

    combined = f"{raw_title} {arch} {name_lower}".lower()
    is_sdxl = "xl" in combined or "sdxl" in combined or (path.stat().st_size > 4.5 * 1024 * 1024 * 1024)

    # 1. Pony Diffusion / V6 full TE
    if "v6-full-te" in combined or "pony" in combined:
        return "Pony Diffusion V6 XL", "pony", True
    # 2. CyberRealistic
    if "cyberrealistic" in combined:
        return "CyberRealistic V8 (Photo)", "photorealistic", is_sdxl
    # 3. AbsoluteReality
    if "absolutereality" in combined or "absolute_reality" in combined:
        return "AbsoluteReality (Photo)", "photorealistic", is_sdxl
    # 4. Realistic Vision / General Realism
    if any(k in combined for k in ("realistic", "photo", "dslr", "realvis")):
        clean = (raw_title or path.stem).replace("_", " ").replace("-", " ").title()
        return f"{clean} (Photo)", "photorealistic", is_sdxl
    # 5. MeinaMix / Anime
    if "meina" in combined:
        return "MeinaMix V11 (Anime)", "anime", is_sdxl
    if any(k in combined for k in ("anime", "manga", "waifu", "animagine")):
        clean = (raw_title or path.stem).replace("_", " ").replace("-", " ").title()
        return f"{clean} (Anime)", "anime", is_sdxl
    # 6. DreamShaper
    if "dreamshaper" in combined:
        return "DreamShaper 8 (Artistic)", "artistic", is_sdxl
    # 7. Generic fallback from filename
    clean_name = (raw_title if len(raw_title) > 3 else path.stem).replace("_", " ").replace("-", " ").strip().title()
    badge = " (SDXL)" if is_sdxl else ""
    return f"{clean_name}{badge}", "generalist" if is_sdxl else "artistic", is_sdxl


def list_available_sd_models() -> Dict[str, Dict[str, Any]]:
    """
    Scan models/image/ and classify installed diffusion checkpoints into styles.
    """
    catalog: Dict[str, Dict[str, Any]] = {}
    if not SD_MODEL_DIR.exists():
        return catalog

    for ext in ("*.safetensors", "*.gguf", "*.ckpt"):
        for p in sorted(SD_MODEL_DIR.glob(ext)):
            if p.name.endswith(".part"):
                continue
            label, style, is_sdxl = _inspect_model_metadata(p)
            catalog[p.name] = {
                "filename": p.name,
                "path": p,
                "style": style,
                "label": label,
                "is_sdxl": is_sdxl,
                "size_gb": round(p.stat().st_size / (1024**3), 2),
            }
    return catalog


def resolve_sd_model_and_prompts(
    prompt: str,
    requested_style: str = "auto",
) -> tuple[Optional[Path], str, str, str, str]:
    """
    Multi-Model Diffusion Router:
    Selects the optimal installed neural checkpoint and tailored prompt enhancements
    based on the user request, chosen checkpoint filename, or artistic style.
    Returns: (model_path, resolved_style, enhanced_prompt, negative_prompt, engine_label)
    """
    models = list_available_sd_models()
    if not models:
        return None, "artistic", prompt, "", "No local diffusion model found"

    req = (requested_style or "auto").strip().lower()
    selected: Optional[Dict[str, Any]] = None

    # 1. Direct model selection: match exact filename, key, or stem
    for k, m in models.items():
        if req == k.lower() or req == m["filename"].lower() or req == Path(m["filename"]).stem.lower():
            selected = m
            break

    # 2. Check for explicit model names mentioned in prompt or request
    if not selected:
        p_lower = prompt.lower()
        combined_query = f"{req} {p_lower}"
        if any(k in combined_query for k in ("pony", "v6", "autism")):
            target_style = "pony"
        elif any(k in combined_query for k in ("meinamix", "meina mix", "meina")):
            target_style = "anime"
        elif any(k in combined_query for k in ("cyberrealistic", "cyber realistic", "realistic vision", "realisticvision", "absolute")):
            target_style = "photorealistic"
        elif any(k in combined_query for k in ("dreamshaper", "dream shaper")):
            target_style = "artistic"
        elif req in ("photorealistic", "photo", "realistic"):
            target_style = "photorealistic"
        elif req in ("anime", "manga", "cartoon"):
            target_style = "anime"
        elif req in ("artistic", "stylized", "fantasy", "digital_art"):
            target_style = "artistic"
        elif req in ("pony", "generalist"):
            target_style = "pony"
        else:
            # Automatic intent classification from prompt
            anime_keywords = (
                "anime", "manga", "cel-shaded", "waifu", "chibi", "studio ghibli",
                "shinkai", "otaku", "comic", "japanese animation", "anime girl", "anime boy"
            )
            photo_keywords = (
                "photo", "photograph", "realistic", "photorealistic", "real life",
                "dslr", "candid", "portrait", "35mm", "hyperrealistic", "shot on",
                "raw photo", "macro photo", "national geographic"
            )
            if any(k in p_lower for k in anime_keywords):
                target_style = "anime"
            elif any(k in p_lower for k in photo_keywords):
                target_style = "photorealistic"
            else:
                target_style = "artistic"

        # Pick matching model or fallback
        matching = [m for m in models.values() if m["style"] == target_style]
        selected = matching[0] if matching else list(models.values())[0]

    model_path = selected["path"]
    resolved_style = selected["style"]
    engine_label = f"{selected['label']} • {selected['filename']}"

    # 3. Apply model-specialized prompt engineering
    if resolved_style == "pony" or "pony" in engine_label.lower():
        enhanced_prompt = f"score_9, score_8_up, score_7_up, {prompt}"
        negative_prompt = "score_4, score_5, score_6, low quality, bad anatomy, deformed, blurry, watermark"
    elif resolved_style == "photorealistic":
        enhanced_prompt = f"{prompt}, raw photo, 35mm photograph, DSLR, detailed skin texture, natural ambient lighting, sharp focus, 8k uhd"
        negative_prompt = (
            "drawing, painting, illustration, cartoon, anime, 3d render, CGI, digital art, "
            "concept art, sketch, airbrushed, cartoonish, blurry, low quality, deformed, "
            "watermark, text, signature, ugly, bad anatomy"
        )
    elif resolved_style == "anime":
        enhanced_prompt = f"{prompt}, masterpiece, best quality, ultra-detailed anime aesthetic, expressive eyes, vibrant colors, cinematic anime lighting"
        negative_prompt = (
            "photorealistic, realistic, 3d render, cgi, low quality, worst quality, blurry, "
            "bad anatomy, deformed hands, missing fingers, extra limbs, watermark, text, signature, ugly"
        )
    else:
        enhanced_prompt = f"{prompt}, masterpiece, concept art, high quality, intricate details, sharp focus, dramatic lighting, rich color palette"
        negative_prompt = "blurry, low quality, deformed, watermark, text, signature, ugly, bad anatomy"

    return model_path, resolved_style, enhanced_prompt, negative_prompt, engine_label


def extract_excel_preview(filepath: Path) -> Dict[str, Any]:
    """Read an .xlsx file to extract both formula strings and display structure for live UI preview."""
    try:
        wb = openpyxl.load_workbook(filepath, data_only=False)
        sheets_preview = []
        for sheet_name in wb.sheetnames[:5]:
            ws = wb[sheet_name]
            rows_data = []
            max_r = min(ws.max_row or 1, 50)
            max_c = min(ws.max_column or 1, 15)
            for r in range(1, max_r + 1):
                row_vals = []
                for c in range(1, max_c + 1):
                    val = ws.cell(row=r, column=c).value
                    row_vals.append("" if val is None else str(val))
                if any(cell != "" for cell in row_vals):
                    rows_data.append(row_vals)
            sheets_preview.append({
                "name": sheet_name,
                "columns": [get_column_letter(c) for c in range(1, max_c + 1)],
                "rows": rows_data,
            })
        return {"sheets": sheets_preview}
    except Exception as exc:
        return {"error": str(exc), "sheets": []}


def _denoise_search_query(query: str) -> str:
    """
    Query De-Noiser & Meta-Phrase Stripper (inspired by Odysseus).
    Strips conversational preambles like 'can you search for', 'search the web for'
    so the search engine receives clean, high-signal keywords.
    """
    q = (query or "").strip()
    patterns = [
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:please\s+)?(?:search(?:\s+the\s+web|\s+online|\s+google|\s+for)?\s+(?:for|about)?)\s*",
        r"^(?:look\s+up(?:\s+online|\s+on\s+google)?\s+(?:for|about)?)\s*",
        r"^(?:find\s+(?:me\s+)?(?:out\s+)?about)\s*",
        r"^(?:what\s+(?:is|are)\s+the\s+latest\s+(?:on|about))\s*",
        r"^(?:search\s+for)\s*",
    ]
    for pat in patterns:
        q = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
    q = re.sub(r'^["\']|["\']$', "", q).strip()
    return q or query.strip()


def _extract_clean_domain(url_str: str) -> str:
    """
    Extract a readable, clean domain name (e.g. 'wikipedia.org') from a URL.
    """
    try:
        netloc = urllib.parse.urlparse(url_str).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _clean_ddg_url(raw_href: str) -> str:
    """
    Decode real destination URLs from DuckDuckGo redirect wrappers (/l/?uddg=...).
    """
    if not raw_href:
        return ""
    if "uddg=" in raw_href:
        try:
            m = re.search(r"[?&]uddg=([^&]+)", raw_href)
            if m:
                return urllib.parse.unquote(m.group(1))
        except Exception:
            pass
    if raw_href.startswith("//"):
        return f"https:{raw_href}"
    return raw_href


def _clean_and_filter_content(text: str, max_chars: int = 1400) -> str:
    """
    Boilerplate & Cookie Wall Filter (inspired by Odysseus `is_low_quality`).
    Removes common web junk (cookie notices, newsletter signups, JS warnings).
    """
    if not text:
        return ""
    text = re.sub(r"^(Title:.*?|URL Source:.*?|Markdown Content:)\n+", "", text, flags=re.MULTILINE)
    junk_patterns = [
        r"(?i)we\s+use\s+cookies[^\n\.]*[\n\.]",
        r"(?i)accept\s+(?:all\s+)?cookies[^\n\.]*[\n\.]",
        r"(?i)cookie\s+preferences[^\n\.]*[\n\.]",
        r"(?i)subscribe\s+to\s+our\s+newsletter[^\n\.]*[\n\.]",
        r"(?i)please\s+enable\s+javascript[^\n\.]*[\n\.]",
        r"(?i)all\s+rights\s+reserved[^\n\.]*[\n\.]",
    ]
    for p in junk_patterns:
        text = re.sub(p, "", text)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


async def _search_brave_api(query: str, api_key: str) -> List[Dict[str, str]]:
    """
    Query the official Brave Search API (2,000 free queries/month).
    Official API designed for programmatic access — ZERO bot-flagging risk.
    """
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key.strip(),
    }
    params = {
        "q": query,
        "count": 6,
        "text_decorations": False,
        "search_lang": "en",
    }
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            items = []
            for r in data.get("web", {}).get("results", [])[:6]:
                u = r.get("url", "").strip()
                t = r.get("title", "").strip()
                s = r.get("description", "").strip()
                if u and t:
                    items.append({"title": t, "url": u, "snippet": s})
            return items
    return []


async def _search_duckduckgo(query: str) -> List[Dict[str, str]]:
    """
    DuckDuckGo search using standard browser form POST request (status 200)
    with automatic /l/?uddg= redirect URL unquoting and lite fallback.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://html.duckduckgo.com",
        "Referer": "https://html.duckduckgo.com/",
    }

    body = ""
    async with httpx.AsyncClient(timeout=7.0, follow_redirects=True) as client:
        try:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": ""},
                headers=headers,
            )
            if resp.status_code == 200:
                body = resp.text
        except Exception:
            pass

        if not body or "result__a" not in body:
            try:
                resp_lite = await client.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                    headers=headers,
                )
                if resp_lite.status_code == 200:
                    body = resp_lite.text
            except Exception:
                pass

    if not body:
        return []

    # 1. Standard html.duckduckgo.com parsing
    link_matches = re.findall(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    snippet_matches = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>',
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )

    items: List[Dict[str, str]] = []
    if link_matches:
        for idx, (raw_href, raw_title) in enumerate(link_matches[:6]):
            t_clean = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            dest_url = _clean_ddg_url(html.unescape(raw_href))
            s_clean = ""
            if idx < len(snippet_matches):
                raw_s = snippet_matches[idx][0] or snippet_matches[idx][1]
                s_clean = html.unescape(re.sub(r"<[^>]+>", "", raw_s)).strip()
            if t_clean and dest_url.startswith("http"):
                items.append({"title": t_clean, "url": dest_url, "snippet": s_clean})
        return items

    # 2. DDG Lite parsing fallback
    lite_matches = re.findall(
        r'<a[^>]*class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    lite_snippets = re.findall(
        r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for idx, (raw_href, raw_title) in enumerate(lite_matches[:6]):
        t_clean = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        dest_url = _clean_ddg_url(html.unescape(raw_href))
        s_clean = ""
        if idx < len(lite_snippets):
            s_clean = html.unescape(re.sub(r"<[^>]+>", "", lite_snippets[idx])).strip()
        if t_clean and dest_url.startswith("http"):
            items.append({"title": t_clean, "url": dest_url, "snippet": s_clean})

    return items


async def _fetch_shielded_reader_content(client: httpx.AsyncClient, target_url: str) -> str:
    """
    Jina Reader Proxy Fetcher (Bot & Residential IP Shield).
    Fetches the article through Jina's cloud cluster (`https://r.jina.ai/<url>`).
    Target websites NEVER see the user's home IP, shielding the user from Cloudflare,
    Akamai, or bot rate limiters. Returns clean parsed Markdown.
    """
    try:
        reader_url = f"https://r.jina.ai/{target_url}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain",
            "X-Timeout": "6",
        }
        resp = await client.get(reader_url, headers=headers, timeout=5.5)
        if resp.status_code == 200 and resp.text:
            return _clean_and_filter_content(resp.text, max_chars=1400)
    except Exception:
        pass
    return ""


async def tool_search_web(
    query: str,
    offline_mode: bool = True,
    brave_api_key: str = "",
) -> Dict[str, Any]:
    """
    Deep, Agentic Web Search Engine with Residential IP Bot Shielding & Odysseus Guardrails.
    - Air-Gap Guard: Blocks immediately if Offline Mode is active.
    - Query De-Noising: Strips conversational preambles into high-signal keywords.
    - Dual Indexing: Brave Search API (if key configured) with fallback to DuckDuckGo.
    - IP Bot-Shield: Top article bodies fetched via remote Jina Reader proxy (`r.jina.ai`).
      The user's home residential IP is NEVER exposed to target web servers.
    - Odysseus Untrusted Content Boundary: Wraps text in <untrusted_web_source> tags
      to block indirect prompt injection.
    - Domain Diversity: Enforces varied sources (max 2 per domain).
    """
    if offline_mode:
        return {
            "status": "blocked",
            "summary": "Blocked by Offline Mode: Web search is disabled while 'Offline Only' privacy lock is active.",
            "results": [],
        }

    clean_query = _denoise_search_query(query)
    candidates: List[Dict[str, str]] = []

    # 1. Search Phase: Brave Search API (if configured)
    if brave_api_key and brave_api_key.strip():
        try:
            candidates = await _search_brave_api(clean_query, brave_api_key.strip())
        except Exception:
            candidates = []

    # Fallback to DuckDuckGo if Brave wasn't configured or returned no items
    if not candidates:
        try:
            candidates = await _search_duckduckgo(clean_query)
        except Exception:
            candidates = []

    if not candidates:
        return {
            "status": "success",
            "summary": f"No web search results found for '{clean_query}'.",
            "results": [],
        }

    # 2. Domain Diversity Filter (Odysseus practice: max 2 results per domain)
    domain_counts: Dict[str, int] = {}
    filtered_candidates: List[Dict[str, str]] = []
    for c in candidates:
        dom = _extract_clean_domain(c["url"])
        if domain_counts.get(dom, 0) < 2:
            domain_counts[dom] = domain_counts.get(dom, 0) + 1
            filtered_candidates.append(c)
        if len(filtered_candidates) >= 5:
            break

    # 3. Reading Phase (Concurrent Shielded Reader via Jina)
    top_to_read = filtered_candidates[:2]
    reader_texts: List[str] = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tasks = [_fetch_shielded_reader_content(client, item["url"]) for item in top_to_read]
            reader_texts = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        reader_texts = []

    # 4. Construct Final Structured Results with Untrusted Content Boundary
    final_results = []
    summary_blocks = []
    for idx, c in enumerate(filtered_candidates, start=1):
        dom = _extract_clean_domain(c["url"])
        deep_text = ""
        if idx - 1 < len(reader_texts) and isinstance(reader_texts[idx - 1], str) and reader_texts[idx - 1]:
            deep_text = reader_texts[idx - 1]
        else:
            deep_text = c.get("snippet", "")

        entry = {
            "index": idx,
            "title": c.get("title", ""),
            "url": c.get("url", ""),
            "domain": dom,
            "snippet": c.get("snippet", ""),
            "deep_content": deep_text,
        }
        final_results.append(entry)

        summary_blocks.append(
            f'[{idx}] {entry["title"]} ({dom})\n'
            f'URL: {entry["url"]}\n'
            f'<untrusted_web_source index="{idx}" domain="{dom}">\n'
            f'{deep_text}\n'
            f'</untrusted_web_source>'
        )

    summary_text = (
        f"Found {len(final_results)} relevant web sources for '{clean_query}':\n\n"
        + "\n\n".join(summary_blocks)
    )

    return {
        "status": "success",
        "summary": summary_text,
        "results": final_results,
    }


async def tool_create_excel_spreadsheet(
    title: str,
    sheets: List[Dict[str, Any]],
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    filename = f"{_slugify(title)}_{int(time.time()) % 10000}.xlsx"
    filepath = confine_to_workspace(ARTIFACTS_DIR / filename)

    wb = openpyxl.Workbook()
    default_ws = wb.active

    header_fill = PatternFill(start_color="18181B", end_color="18181B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FAFAFA")
    zebra_fill = PatternFill(start_color="F4F4F5", end_color="F4F4F5", fill_type="solid")
    total_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    body_font = Font(name="Segoe UI", size=10, color="18181B")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="18181B")
    thin_border = Border(
        left=Side(style="thin", color="E4E4E7"),
        right=Side(style="thin", color="E4E4E7"),
        top=Side(style="thin", color="E4E4E7"),
        bottom=Side(style="thin", color="E4E4E7"),
    )

    if not sheets:
        sheets = [
            {
                "name": "Summary",
                "headers": ["Category", "Q1", "Q2", "Q3", "Q4", "Annual Total"],
                "rows": [
                    ["Product Revenue", 42500, 48900, 53200, 61800, "=SUM(B2:E2)"],
                    ["Services & Consulting", 18200, 19500, 22400, 25100, "=SUM(B3:E3)"],
                    ["Operating Expenses", -24100, -25300, -26800, -28400, "=SUM(B4:E4)"],
                    ["Net Operating Income", "=SUM(B2:B4)", "=SUM(C2:C4)", "=SUM(D2:D4)", "=SUM(E2:E4)", "=SUM(F2:F4)"],
                ],
            }
        ]

    for idx, sheet_spec in enumerate(sheets):
        sheet_name = str(sheet_spec.get("name", f"Sheet_{idx + 1}"))[:31]
        ws = default_ws if idx == 0 else wb.create_sheet(title=sheet_name)
        ws.title = sheet_name

        headers = sheet_spec.get("headers") or []
        rows = sheet_spec.get("rows") or []

        start_row = 1
        if headers:
            for c_idx, h_val in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=c_idx, value=h_val)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center" if c_idx > 1 else "left", vertical="center")
                cell.border = thin_border
            ws.row_dimensions[1].height = 28
            start_row = 2

        for r_offset, row_vals in enumerate(rows):
            r_idx = start_row + r_offset
            is_summary_row = any(
                isinstance(v, str) and ("total" in v.lower() or "net " in v.lower() or "average" in v.lower())
                for v in row_vals[:1]
            )
            ws.row_dimensions[r_idx].height = 22
            for c_idx, val in enumerate(row_vals, start=1):
                if isinstance(val, str) and not val.startswith("="):
                    clean_num = val.replace("$", "").replace(",", "").strip()
                    try:
                        if "." in clean_num:
                            val = float(clean_num)
                        elif clean_num.lstrip("-").isdigit():
                            val = int(clean_num)
                    except ValueError:
                        pass

                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                cell.border = thin_border
                if is_summary_row:
                    cell.fill = total_fill
                    cell.font = bold_font
                else:
                    if r_offset % 2 == 1:
                        cell.fill = zebra_fill
                    cell.font = bold_font if (isinstance(val, str) and val.startswith("=")) else body_font

                if isinstance(val, (int, float)) or (isinstance(val, str) and val.startswith("=")):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if isinstance(val, float) or (isinstance(val, int) and abs(val) >= 100):
                        cell.number_format = "#,##0.00" if isinstance(val, float) else "#,##0"
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws.columns:
            max_len = 10
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                max_len = max(max_len, min(len(val_str) + 4, 42))
            ws.column_dimensions[col_letter].width = max_len

    wb.save(filepath)
    preview = extract_excel_preview(filepath)
    artifact = await register_artifact(
        title=title,
        filename=filename,
        category="spreadsheet",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_bytes=filepath.stat().st_size,
        preview_data=preview,
        conversation_id=conversation_id,
    )
    return {
        "status": "success",
        "summary": f"Created Excel workbook '{filename}' with {len(sheets)} sheet(s).",
        "artifact": artifact,
    }


async def tool_create_document(
    title: str,
    doc_format: str,
    sections: List[Dict[str, Any]],
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    fmt = doc_format.lower().strip().lstrip(".")
    if fmt not in ("pdf", "docx", "md"):
        fmt = "pdf"

    filename = f"{_slugify(title)}_{int(time.time()) % 10000}.{fmt}"
    filepath = confine_to_workspace(ARTIFACTS_DIR / filename)

    markdown_preview_lines = [f"# {title}\n"]
    for sec in sections:
        heading = sec.get("heading")
        body = sec.get("body", "")
        bullets = sec.get("bullets") or []
        if heading:
            markdown_preview_lines.append(f"## {heading}\n")
        if body:
            markdown_preview_lines.append(f"{body}\n")
        for b in bullets:
            markdown_preview_lines.append(f"- {b}")
        if bullets:
            markdown_preview_lines.append("")

    preview_text = "\n".join(markdown_preview_lines)

    if fmt == "docx":
        from docx import Document

        doc = Document()
        doc.add_heading(title, level=0)
        for sec in sections:
            if sec.get("heading"):
                doc.add_heading(str(sec["heading"]), level=1)
            if sec.get("body"):
                doc.add_paragraph(str(sec["body"]))
            for b in sec.get("bullets") or []:
                doc.add_paragraph(str(b), style="List Bullet")
        doc.save(filepath)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    elif fmt == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#111317"),
            spaceAfter=16,
        )
        h2_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "BodyCopy",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#374151"),
            spaceAfter=8,
        )

        story = [Paragraph(title, title_style)]
        for sec in sections:
            if sec.get("heading"):
                story.append(Paragraph(str(sec["heading"]), h2_style))
            if sec.get("body"):
                clean_body = str(sec["body"]).replace("\n", "<br/>")
                story.append(Paragraph(clean_body, body_style))
            bullets = sec.get("bullets") or []
            if bullets:
                items = [ListItem(Paragraph(str(b), body_style)) for b in bullets]
                story.append(ListFlowable(items, bulletType="bullet", start="circle"))
            story.append(Spacer(1, 8))
        doc.build(story)
        mime = "application/pdf"
    else:
        filepath.write_text(preview_text, encoding="utf-8")
        mime = "text/markdown"

    artifact = await register_artifact(
        title=title,
        filename=filename,
        category="document",
        mime_type=mime,
        size_bytes=filepath.stat().st_size,
        preview_data={"markdown": preview_text, "format": fmt},
        conversation_id=conversation_id,
    )
    return {
        "status": "success",
        "summary": f"Generated {fmt.upper()} document '{filename}'.",
        "artifact": artifact,
    }


async def tool_build_interactive_app(
    title: str,
    html_code: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    filename = f"{_slugify(title)}_{int(time.time()) % 10000}.html"
    filepath = confine_to_workspace(ARTIFACTS_DIR / filename)
    filepath.write_text(html_code, encoding="utf-8")

    artifact = await register_artifact(
        title=title,
        filename=filename,
        category="webapp",
        mime_type="text/html",
        size_bytes=filepath.stat().st_size,
        preview_data={"code_snippet": html_code[:2000]},
        conversation_id=conversation_id,
    )
    return {
        "status": "success",
        "summary": f"Built interactive web application '{filename}'.",
        "artifact": artifact,
    }


async def _evict_ollama_vram_if_needed(model: str, vram_handoff: bool) -> bool:
    if not vram_handoff:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            ps_resp = await client.get("http://127.0.0.1:11434/api/ps")
            loaded = [m.get("name") for m in ps_resp.json().get("models", []) if m.get("name")]
            if model and model not in loaded:
                loaded.append(model)
            for m_name in loaded:
                await client.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={"model": m_name, "keep_alive": 0},
                )
        return True
    except Exception:
        return False


async def tool_generate_visual_media(
    prompt: str,
    media_type: str = "image",
    style: str = "auto",
    chart_data: Optional[Dict[str, Any]] = None,
    active_model: str = "",
    vram_handoff: bool = True,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a real neural AI image (routed to Realistic Vision, MeinaMix Anime, or DreamShaper),
    a high-DPI Matplotlib chart, or an animated clip.
    """
    from PIL import Image, ImageDraw

    is_video = media_type.lower() in ("video", "animation", "gif", "motion")
    is_chart = media_type.lower() == "chart" or (
        chart_data and isinstance(chart_data, dict) and chart_data.get("labels") and chart_data.get("values")
    )
    slug = _slugify(prompt[:36])

    # 1. Data Chart via Matplotlib
    if is_chart and chart_data and chart_data.get("labels") and chart_data.get("values"):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        filename = f"chart_{slug}_{int(time.time()) % 10000}.png"
        filepath = confine_to_workspace(ARTIFACTS_DIR / filename)

        fig, ax = plt.subplots(figsize=(10, 5.8), dpi=160)
        fig.patch.set_facecolor("#0F1115")
        ax.set_facecolor("#161920")

        labels = [str(x) for x in chart_data["labels"]]
        values = [float(v) for v in chart_data["values"]]
        chart_kind = str(chart_data.get("type", "bar")).lower()
        palette = ["#D97757", "#10B981", "#3B82F6", "#F59E0B", "#8B5CF6", "#EC4899"]

        if chart_kind == "line":
            ax.plot(labels, values, color="#D97757", linewidth=3, marker="o", markersize=8)
            ax.fill_between(range(len(labels)), values, color="#D97757", alpha=0.15)
        else:
            bars = ax.bar(labels, values, color=palette[: len(labels)], width=0.58, edgecolor="#262A34")
            for bar in bars:
                yval = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    yval,
                    f"{yval:,.0f}",
                    ha="center",
                    va="bottom",
                    color="#E5E7EB",
                    fontsize=9.5,
                    fontweight="bold",
                )

        ax.set_title(prompt, color="#F9FAFB", fontsize=14, fontweight="bold", pad=16)
        ax.tick_params(colors="#9CA3AF", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#262A34")
        ax.grid(axis="y", linestyle="--", alpha=0.2, color="#9CA3AF")
        plt.tight_layout()
        plt.savefig(filepath, dpi=160)
        plt.close(fig)

        artifact = await register_artifact(
            title=prompt[:60],
            filename=filename,
            category="image",
            mime_type="image/png",
            size_bytes=filepath.stat().st_size,
            preview_data={"prompt": prompt, "engine": "Matplotlib HD Chart"},
            conversation_id=conversation_id,
        )
        return {"status": "success", "summary": f"Rendered chart '{filename}'.", "artifact": artifact}

    # 2. Multi-Model Neural Diffusion Image Generation (Vulkan GPU)
    model_path, resolved_style, enhanced_prompt, negative_prompt, engine_label = resolve_sd_model_and_prompts(
        prompt=prompt,
        requested_style=style,
    )
    if not is_video and SD_CLI_PATH.exists() and model_path and model_path.exists():
        await _evict_ollama_vram_if_needed(active_model, vram_handoff)
        filename = f"img_{resolved_style}_{slug}_{int(time.time()) % 10000}.png"
        filepath = confine_to_workspace(ARTIFACTS_DIR / filename)
        seed = random.randint(1, 999999999)

        models_cat = list_available_sd_models()
        model_info = models_cat.get(model_path.name, {})
        is_sdxl = model_info.get("is_sdxl", False) or (model_path.stat().st_size > 4.5 * 1024**3)
        target_res = "1024" if is_sdxl else "512"
        steps = "20" if is_sdxl else "16"

        cmd = [
            str(SD_CLI_PATH),
            "-m",
            str(model_path),
            "-p",
            enhanced_prompt,
            "-n",
            negative_prompt,
            "-W",
            target_res,
            "-H",
            target_res,
            "--steps",
            steps,
            "--cfg-scale",
            "7.0",
            "--sampling-method",
            "euler_a",
            "-s",
            str(seed),
            "-o",
            str(filepath),
        ]

        def _run_sd():
            return subprocess.run(
                cmd,
                cwd=str(SD_CLI_PATH.parent),
                capture_output=True,
                text=True,
                timeout=90.0,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )

        proc = await asyncio.to_thread(_run_sd)
        if proc.returncode == 0 and filepath.exists():
            artifact = await register_artifact(
                title=prompt[:60],
                filename=filename,
                category="image",
                mime_type="image/png",
                size_bytes=filepath.stat().st_size,
                preview_data={
                    "prompt": prompt,
                    "style": resolved_style,
                    "engine": engine_label,
                    "model_filename": model_path.name,
                },
                conversation_id=conversation_id,
            )
            return {
                "status": "success",
                "summary": f"Generated {resolved_style} AI image '{filename}' using {engine_label} on your local GPU.",
                "artifact": artifact,
            }

    # 3. Animated Motion Clip
    filename = f"motion_{slug}_{int(time.time()) % 10000}.gif"
    filepath = confine_to_workspace(ARTIFACTS_DIR / filename)
    frames = []
    width, height = 640, 380
    for f_idx in range(24):
        t = f_idx / 24.0
        img = Image.new("RGB", (width, height), (13, 15, 20))
        draw = ImageDraw.Draw(img)
        for ring in range(6):
            phase = t * 2 * math.pi + ring * 0.55
            cx = int(width * 0.5 + math.cos(phase) * (90 + ring * 18))
            cy = int(height * 0.5 + math.sin(phase * 1.5) * (45 + ring * 10))
            r = 28 + ring * 12
            color = (
                min(255, 190 + ring * 10),
                min(255, 95 + ring * 20),
                min(255, 70 + ring * 25),
            )
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
        draw.rectangle([20, height - 54, width - 20, height - 18], fill=(20, 23, 30))
        draw.text((34, height - 42), f"LOCAL MOTION  •  {prompt[:46].upper()}", fill=(235, 237, 242))
        frames.append(img)

    frames[0].save(
        filepath,
        save_all=True,
        append_images=frames[1:],
        duration=65,
        loop=0,
    )
    artifact = await register_artifact(
        title=prompt[:60],
        filename=filename,
        category="video",
        mime_type="image/gif",
        size_bytes=filepath.stat().st_size,
        preview_data={"prompt": prompt, "engine": "On-Device Motion Synthesis (24 frames)"},
        conversation_id=conversation_id,
    )
    return {
        "status": "success",
        "summary": f"Generated animated clip '{filename}'.",
        "artifact": artifact,
    }


async def tool_execute_python(
    script: str,
    description: str = "Execute Python script",
    target_filepath: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Antigravity-Style Universal Python Execution Primitive.
    - Executes Python code directly with access to pre-installed libraries (openpyxl, pandas, python-docx, reportlab, matplotlib, PIL).
    - If target_filepath is specified or referenced, creates a timestamped .bak backup prior to modification.
    - Captures stdout, stderr, return codes, and registers any created/modified artifacts.
    """
    bak_path = None
    target_path = None
    if target_filepath and str(target_filepath).strip():
        try:
            target_path = resolve_safe_path(target_filepath, allow_outside_workspace=True)
            if target_path.exists() and target_path.is_file():
                bak_path = create_file_backup(target_path)
        except Exception:
            pass

    before_files = {p.name: p.stat().st_mtime for p in ARTIFACTS_DIR.iterdir() if p.is_file()}
    script_file = ARTIFACTS_DIR / f"_orchestrator_exec_{int(time.time() * 1000)}.py"
    script_file.write_text(script, encoding="utf-8")

    cwd_dir = target_path.parent if (target_path and target_path.parent.exists()) else WORKSPACE_DIR

    start_t = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_file)],
            cwd=str(cwd_dir),
            capture_output=True,
            text=True,
            timeout=45.0,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )
        duration_ms = int((time.time() - start_t) * 1000)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        duration_ms = 45000
        stdout = ""
        stderr = "Execution timed out after 45 seconds."
        returncode = 124
    except Exception as exc:
        duration_ms = int((time.time() - start_t) * 1000)
        stdout = ""
        stderr = str(exc)
        returncode = 1
    finally:
        if script_file.exists():
            script_file.unlink(missing_ok=True)

    created_artifacts = []
    for p in ARTIFACTS_DIR.iterdir():
        if not p.is_file() or p.name.startswith("_orchestrator_exec_") or p.name.startswith("_sandbox_exec_") or p.name == ".gitkeep":
            continue
        if p.name not in before_files or p.stat().st_mtime > before_files[p.name]:
            ext = p.suffix.lower()
            mime, _ = mimetypes.guess_type(p.name)
            mime = mime or "application/octet-stream"
            category = "file"
            preview = {}
            if ext in (".xlsx", ".xls", ".csv"):
                category = "spreadsheet"
                preview = extract_excel_preview(p) if ext == ".xlsx" else {}
            elif ext in (".pdf", ".docx", ".doc", ".md", ".txt"):
                category = "document"
                preview = {"format": ext.lstrip(".")}
            elif ext in (".png", ".jpg", ".jpeg", ".svg", ".webp"):
                category = "image"
                preview = {"engine": "Python Orchestrator"}
            elif ext in (".gif", ".mp4", ".webm"):
                category = "video"
                preview = {"engine": "Python Orchestrator"}
            elif ext in (".html", ".htm"):
                category = "webapp"
                preview = {"code_snippet": p.read_text(encoding="utf-8", errors="ignore")[:1500]}

            art = await register_artifact(
                title=p.stem.replace("_", " ").title(),
                filename=p.name,
                category=category,
                mime_type=mime,
                size_bytes=p.stat().st_size,
                preview_data=preview,
                conversation_id=conversation_id,
            )
            created_artifacts.append(art)

    summary_items = []
    if returncode == 0:
        summary_items.append(f"Python script succeeded in {duration_ms}ms")
    else:
        summary_items.append(f"Python script exited with code {returncode}")
    if bak_path:
        summary_items.append(f"• Backup created at '{bak_path.name}'")
    if created_artifacts:
        summary_items.append(f"• Generated {len(created_artifacts)} artifact(s)")

    return {
        "status": "success" if returncode == 0 else "error",
        "returncode": returncode,
        "duration_ms": duration_ms,
        "stdout": stdout[:6000],
        "stderr": stderr[:3000],
        "backup_created": str(bak_path) if bak_path else None,
        "artifacts": created_artifacts,
        "summary": " ".join(summary_items),
    }


async def tool_run_python_sandbox(
    script: str,
    description: str = "Execute Python script in local sandbox",
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Legacy alias for tool_execute_python."""
    return await tool_execute_python(script=script, description=description, conversation_id=conversation_id)


async def tool_read_file(
    filepath: str,
    start_line: int = 1,
    max_lines: int = 250,
) -> Dict[str, Any]:
    """
    Antigravity-Style Universal File Reader.
    - Supports reading local code, text, JSON, and markdown files with line numbering.
    - Automatically parses Excel (.xlsx) workbooks into structured markdown tables and sheet listings.
    - Formats CSV files into structured table previews.
    """
    try:
        target = resolve_safe_path(filepath, allow_outside_workspace=True)
    except Exception as exc:
        return {"status": "error", "summary": str(exc), "content": ""}

    if not target.exists():
        return {"status": "error", "summary": f"File not found: '{filepath}'", "content": ""}

    if target.is_dir():
        return await tool_list_directory(directory_path=str(target))

    ext = target.suffix.lower()

    # 1. Excel Workbook (.xlsx / .xlsm)
    if ext in (".xlsx", ".xlsm"):
        try:
            wb = openpyxl.load_workbook(target, data_only=True, read_only=True)
            sheet_names = wb.sheetnames
            active_sheet = sheet_names[0] if sheet_names else "Sheet1"
            ws = wb[active_sheet]

            rows_data = []
            for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if r_idx > 35:
                    break
                rows_data.append([str(v if v is not None else "") for v in row[:15]])
            wb.close()

            lines = [
                f"# Excel Workbook: {target.name}",
                f"- **Sheets in Workbook**: {', '.join(sheet_names)}",
                f"- **Active Sheet Previewed**: `{active_sheet}` (first {len(rows_data)} rows)",
                "",
            ]
            if rows_data:
                headers = rows_data[0]
                lines.append("| " + " | ".join(headers) + " |")
                lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for r in rows_data[1:]:
                    lines.append("| " + " | ".join(r) + " |")
            else:
                lines.append("*(Sheet is empty)*")

            table_content = "\n".join(lines)
            return {
                "status": "success",
                "file_type": "excel",
                "sheets": sheet_names,
                "summary": f"Read Excel file '{target.name}' ({len(sheet_names)} sheets: {', '.join(sheet_names)}).",
                "content": table_content,
            }
        except Exception as exc:
            return {"status": "error", "summary": f"Failed reading Excel file: {exc}", "content": ""}

    # 2. CSV Table
    if ext == ".csv":
        try:
            lines = [f"# CSV File: {target.name}", ""]
            with open(target, mode="r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = [row for _, row in zip(range(40), reader)]
            if rows:
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                for r in rows[1:]:
                    lines.append("| " + " | ".join(r) + " |")
            return {
                "status": "success",
                "file_type": "csv",
                "summary": f"Read CSV table '{target.name}' ({len(rows)} preview rows).",
                "content": "\n".join(lines),
            }
        except Exception as exc:
            return {"status": "error", "summary": f"Failed reading CSV: {exc}", "content": ""}

    # 3. Standard Text / Code / JSON / Markdown
    try:
        content_bytes = target.read_bytes()
        if len(content_bytes) > 5 * 1024 * 1024:
            return {
                "status": "error",
                "summary": f"File '{target.name}' is too large ({len(content_bytes)//1024} KB) to read directly into context.",
                "content": "",
            }

        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="replace")

        all_lines = text.splitlines()
        total_lines = len(all_lines)
        start_idx = max(1, start_line) - 1
        end_idx = min(total_lines, start_idx + max_lines)
        slice_lines = all_lines[start_idx:end_idx]

        numbered = [f"{start_idx + i + 1:4d} | {line}" for i, line in enumerate(slice_lines)]
        summary = f"Read lines {start_idx + 1} to {end_idx} of {total_lines} from '{target.name}'."
        return {
            "status": "success",
            "file_type": ext.lstrip(".") or "text",
            "total_lines": total_lines,
            "lines_shown": len(slice_lines),
            "summary": summary,
            "content": "\n".join(numbered),
        }
    except Exception as exc:
        return {"status": "error", "summary": f"Failed reading file '{target.name}': {exc}", "content": ""}


async def tool_list_directory(
    directory_path: str = ".",
    max_entries: int = 100,
) -> Dict[str, Any]:
    """
    Antigravity-Style Directory Explorer.
    Lists files, directories, sizes, and file types inside any allowed local folder.
    """
    try:
        target = resolve_safe_path(directory_path, allow_outside_workspace=True)
    except Exception as exc:
        return {"status": "error", "summary": str(exc), "entries": []}

    if not target.exists():
        return {"status": "error", "summary": f"Directory not found: '{directory_path}'", "entries": []}
    if not target.is_dir():
        return {"status": "error", "summary": f"Path '{directory_path}' is a file, not a directory. Use read_file instead.", "entries": []}

    entries = []
    try:
        items = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:max_entries]
        table_lines = [
            f"# Directory: {target}",
            f"Total items shown: {len(items)}",
            "",
            "| Name | Type | Size |",
            "| --- | --- | --- |",
        ]
        for it in items:
            kind = "Folder" if it.is_dir() else "File"
            size_str = ""
            if it.is_file():
                sz = it.stat().st_size
                if sz < 1024:
                    size_str = f"{sz} B"
                elif sz < 1024 * 1024:
                    size_str = f"{sz/1024:.1f} KB"
                else:
                    size_str = f"{sz/(1024*1024):.1f} MB"
            entries.append({"name": it.name, "type": kind, "size": size_str, "path": str(it)})
            table_lines.append(f"| {it.name} | {kind} | {size_str or '-'} |")

        return {
            "status": "success",
            "directory": str(target),
            "count": len(entries),
            "summary": f"Listed {len(entries)} item(s) in '{target.name or target}'.",
            "content": "\n".join(table_lines),
            "entries": entries,
        }
    except Exception as exc:
        return {"status": "error", "summary": f"Failed listing directory: {exc}", "entries": []}


async def tool_edit_file_content(
    filepath: str,
    target_content: str,
    replacement_content: str,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Antigravity-Style Surgical Text / Code File Editor.
    Replaces an exact block of target content with replacement content, creating a .bak copy first.
    Calculates unified diff lines for interactive user preview and 1-click backup rollback.
    """
    try:
        target = resolve_safe_path(filepath, allow_outside_workspace=True, base_dir=base_dir)
    except Exception as exc:
        return {"status": "error", "summary": str(exc)}

    if not target.exists() or not target.is_file():
        return {"status": "error", "summary": f"Target file not found: '{filepath}'"}

    try:
        raw_text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            raw_text = target.read_text(encoding="latin-1")
        except Exception as exc:
            return {"status": "error", "summary": f"Cannot decode file as text: {exc}"}

    if target_content not in raw_text:
        return {
            "status": "error",
            "summary": "Target content not found in file. Make sure whitespace, indentation, and lines match exactly.",
        }

    bak_path = create_file_backup(target)
    new_text = raw_text.replace(target_content, replacement_content, 1)
    target.write_text(new_text, encoding="utf-8")

    diff_lines = list(difflib.unified_diff(
        raw_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{target.name}",
        tofile=f"b/{target.name}",
        n=3,
    ))
    diff_str = "".join(diff_lines)

    return {
        "status": "success",
        "summary": f"Successfully updated '{target.name}'.",
        "backup_path": str(bak_path) if bak_path else None,
        "backup_filename": bak_path.name if bak_path else None,
        "filepath": str(target),
        "filename": target.name,
        "diff": diff_str,
        "detail": f"File edited successfully. Backup saved at: {bak_path.name if bak_path else 'none'}",
    }


def tool_revert_file_backup(backup_filepath: str, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Restores an edited file from its .bak_* backup.
    """
    try:
        bak_target = resolve_safe_path(backup_filepath, allow_outside_workspace=True, base_dir=base_dir)
        if not bak_target.exists() or not bak_target.is_file():
            return {"status": "error", "summary": f"Backup file not found: '{backup_filepath}'"}

        name = bak_target.name
        if ".bak_" not in name:
            return {"status": "error", "summary": f"Not a valid backup file (.bak_* required): '{name}'"}

        orig_name = name.split(".bak_")[0]
        orig_target = bak_target.with_name(orig_name)

        shutil.copy2(bak_target, orig_target)
        return {
            "status": "success",
            "summary": f"Successfully restored '{orig_name}' from backup.",
            "restored_file": str(orig_target),
            "backup_file": str(bak_target),
        }
    except Exception as exc:
        return {"status": "error", "summary": f"Failed to restore backup: {exc}"}


async def tool_run_shell_command(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: float = 60.0,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Antigravity/Cursor-Style Shell & Terminal Command Runner.
    Runs commands in the active workspace directory.
    Guards against destructive system commands.
    """
    clean_cmd = command.strip()
    if not clean_cmd:
        return {"status": "error", "summary": "Command cannot be empty", "stdout": "", "stderr": "Empty command"}

    lower_cmd = clean_cmd.lower()
    blocked_patterns = [
        r"\bformat\s+[a-z]:",
        r"\brmdir\s+/[sq]\s+[a-z]:\\",
        r"\bdel\s+/[sqfa]\s+[a-z]:\\windows",
        r"\bdiskpart\b",
        r"\bmkfs\b",
        r"\bdd\s+if=",
        r"\brm\s+-rf\s+/\b",
    ]
    for pat in blocked_patterns:
        if re.search(pat, lower_cmd):
            return {
                "status": "error",
                "summary": "Command blocked by safety guard: potentially destructive system operation detected.",
                "stdout": "",
                "stderr": "Command blocked for system safety.",
            }

    resolved_cwd = (base_dir or WORKSPACE_DIR).resolve()
    if cwd and cwd.strip():
        try:
            target_cwd = resolve_safe_path(cwd, allow_outside_workspace=True, base_dir=base_dir)
            if target_cwd.exists() and target_cwd.is_dir():
                resolved_cwd = target_cwd
        except Exception:
            pass

    t0 = time.time()
    try:
        if platform.system() == "Windows":
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                clean_cmd,
                cwd=str(resolved_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                clean_cmd,
                cwd=str(resolved_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {
                "status": "error",
                "summary": f"Command timed out after {timeout_seconds} seconds.",
                "stdout": "",
                "stderr": f"Execution timed out ({timeout_seconds}s).",
                "duration_ms": int((time.time() - t0) * 1000),
                "cwd": str(resolved_cwd),
            }

        duration_ms = int((time.time() - t0) * 1000)
        status = "success" if exit_code == 0 else "error"
        summary = f"Command exited with code {exit_code} ({duration_ms}ms)"
        if exit_code == 0 and stdout:
            first_line = stdout.strip().splitlines()[0][:60]
            summary = f"Shell command succeeded: {first_line}"

        max_chars = 25000
        truncated_stdout = stdout if len(stdout) <= max_chars else stdout[:max_chars] + f"\n... [Output truncated: {len(stdout) - max_chars} characters omitted] ..."
        truncated_stderr = stderr if len(stderr) <= max_chars else stderr[:max_chars] + f"\n... [Stderr truncated: {len(stderr) - max_chars} characters omitted] ..."

        return {
            "status": status,
            "exit_code": exit_code,
            "summary": summary,
            "stdout": truncated_stdout,
            "stderr": truncated_stderr,
            "duration_ms": duration_ms,
            "cwd": str(resolved_cwd),
        }
    except Exception as exc:
        return {
            "status": "error",
            "exit_code": -1,
            "summary": f"Failed to execute command: {exc}",
            "stdout": "",
            "stderr": str(exc),
            "duration_ms": int((time.time() - t0) * 1000),
            "cwd": str(resolved_cwd),
        }


def get_tool_schemas(allow_web_search: bool = False) -> List[Dict[str, Any]]:
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": (
                    "Execute Python 3 code directly on the user's computer. "
                    "Use installed packages (openpyxl for Excel, pandas for dataframes, python-docx for Word, "
                    "reportlab for PDF, PIL for images, pathlib/os for files). "
                    "Target files modified will automatically have a .bak backup created by the system."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "Python 3 code to execute.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Short explanation of what the script accomplishes.",
                        },
                        "target_filepath": {
                            "type": "string",
                            "description": "Optional file path being inspected or modified, so the system creates an automatic .bak backup.",
                        },
                    },
                    "required": ["script", "description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_shell_command",
                "description": (
                    "Execute a terminal shell command (PowerShell on Windows, Bash on Linux/Mac) "
                    "in the active workspace directory. Use to run tests, build tools, inspect git status, "
                    "compile code, or run CLI utilities."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command line to execute (e.g. 'npm test', 'git status', 'python -m pytest', 'dir').",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Optional subdirectory or working folder path (defaults to active workspace).",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": (
                    "Read the contents of a local file on the computer. "
                    "Supports code, text, JSON, and markdown with line numbers. "
                    "For Excel (.xlsx) workbooks and CSV files, automatically returns sheet listings and data table previews."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {
                            "type": "string",
                            "description": "Local path of the file to inspect (e.g. C:\\Users\\...\\budget.xlsx).",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number for text files (1-indexed, default 1).",
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Maximum number of lines to return (default 250).",
                        },
                    },
                    "required": ["filepath"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file_content",
                "description": (
                    "Surgically edit a text, code, or configuration file by replacing an exact block of target content "
                    "with replacement content. Automatically creates a timestamped .bak backup."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {
                            "type": "string",
                            "description": "Path to the file to edit.",
                        },
                        "target_content": {
                            "type": "string",
                            "description": "The exact existing text block to find and replace.",
                        },
                        "replacement_content": {
                            "type": "string",
                            "description": "The new replacement text to insert.",
                        },
                    },
                    "required": ["filepath", "target_content", "replacement_content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files, subdirectories, and sizes in a local folder on the user's computer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "Path of the directory to list (defaults to current workspace).",
                        },
                        "max_entries": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 100).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_visual_media",
                "description": (
                    "Generate a photorealistic or artistic AI picture/image (media_type='image'), "
                    "a data chart (media_type='chart'), or an animation (media_type='video')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Detailed visual prompt for the image or chart title"},
                        "media_type": {"type": "string", "enum": ["image", "video", "chart"]},
                        "style": {
                            "type": "string",
                            "enum": ["auto", "photorealistic", "artistic", "anime"],
                            "description": "Visual aesthetic style: 'photorealistic' for real-life camera photos, 'anime' for Japanese anime/manga art, 'artistic' for fantasy/concept art/illustrations, or 'auto' to infer from prompt",
                        },
                        "chart_data": {"type": "object"},
                    },
                    "required": ["prompt", "media_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_excel_spreadsheet",
                "description": (
                    "Create a formatted Excel (.xlsx) spreadsheet with custom tabs, headers, rows, "
                    "and live Excel formulas (like =SUM(B2:E2))."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of the Excel workbook"},
                        "sheets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "headers": {"type": "array", "items": {"type": "string"}},
                                    "rows": {
                                        "type": "array",
                                        "items": {"type": "array", "items": {"type": ["string", "number"]}},
                                    },
                                },
                                "required": ["name", "headers", "rows"],
                            },
                        },
                    },
                    "required": ["title", "sheets"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_document",
                "description": "Create a formatted PDF (.pdf) or Word (.docx) document with structured sections.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "doc_format": {"type": "string", "enum": ["pdf", "docx", "md"]},
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "body": {"type": "string"},
                                    "bullets": {"type": "array", "items": {"type": "string"}},
                                },
                            },
                        },
                    },
                    "required": ["title", "doc_format", "sections"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "build_interactive_app",
                "description": "Build a self-contained HTML/CSS/JavaScript interactive web app or calculator.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "html_code": {"type": "string"},
                    },
                    "required": ["title", "html_code"],
                },
            },
        },
    ]

    if allow_web_search:
        schemas.append({
            "type": "function",
            "function": {
                "name": "search_web",
                "description": (
                    "Search the live web for up-to-date facts, news, documentation, or release info. "
                    "Returns structured sources with deep extracted article content and citations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Concise, keyword-focused search query (e.g. 'RTX 5090 release date 2026')",
                        },
                    },
                    "required": ["query"],
                },
            },
        })

    return schemas


TOOL_SCHEMAS = get_tool_schemas(allow_web_search=False)
