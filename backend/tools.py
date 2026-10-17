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
import html
import math
import mimetypes
import os
import platform
import random
import re
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


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip().lower()).strip("_")
    return s[:48] or f"file_{int(time.time())}"


def _find_local_sd_model() -> Optional[Path]:
    if not SD_MODEL_DIR.exists():
        return None
    for ext in ("*.safetensors", "*.gguf", "*.ckpt"):
        matches = sorted(SD_MODEL_DIR.glob(ext))
        if matches:
            return matches[0]
    return None


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


async def tool_search_web(query: str, offline_mode: bool = True) -> Dict[str, Any]:
    if offline_mode:
        return {
            "status": "blocked",
            "summary": "Blocked by Offline Mode: Web search is disabled while 'Offline Only' privacy lock is active.",
            "results": [],
        }

    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            body = resp.text

        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', body, flags=re.DOTALL)
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>',
            body,
            flags=re.DOTALL,
        )

        clean_results = []
        for idx, raw_title in enumerate(titles[:5]):
            t_clean = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            s_clean = ""
            if idx < len(snippets):
                raw_s = snippets[idx][0] or snippets[idx][1]
                s_clean = html.unescape(re.sub(r"<[^>]+>", "", raw_s)).strip()
            if t_clean:
                clean_results.append({"title": t_clean, "snippet": s_clean})

        return {
            "status": "success",
            "summary": f"Found {len(clean_results)} web results for '{query}'.",
            "results": clean_results,
        }
    except Exception as exc:
        return {
            "status": "error",
            "summary": f"Web search failed: {exc}",
            "results": [],
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
    chart_data: Optional[Dict[str, Any]] = None,
    active_model: str = "",
    vram_handoff: bool = True,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a real neural AI image (via built-in Vulkan GPU Stable Diffusion `sd-cli.exe` + `DreamShaper 8`),
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

    # 2. Built-in Real Neural Diffusion Image Generation (`sd-cli.exe` + `DreamShaper 8` on Vulkan GPU)
    local_sd_model = _find_local_sd_model()
    if not is_video and SD_CLI_PATH.exists() and local_sd_model:
        await _evict_ollama_vram_if_needed(active_model, vram_handoff)
        filename = f"img_{slug}_{int(time.time()) % 10000}.png"
        filepath = confine_to_workspace(ARTIFACTS_DIR / filename)
        seed = random.randint(1, 999999999)
        enhanced_prompt = f"{prompt}, masterpiece, high resolution, detailed, sharp focus, natural lighting"
        negative_prompt = "blurry, low quality, deformed, watermark, text, signature, ugly, bad anatomy"

        cmd = [
            str(SD_CLI_PATH),
            "-m",
            str(local_sd_model),
            "-p",
            enhanced_prompt,
            "-n",
            negative_prompt,
            "-W",
            "512",
            "-H",
            "512",
            "--steps",
            "16",
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
                    "engine": f"Local Neural GPU Diffusion ({local_sd_model.stem} • Vulkan)",
                },
                conversation_id=conversation_id,
            )
            return {
                "status": "success",
                "summary": f"Generated AI image '{filename}' using {local_sd_model.name} on your local GPU.",
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


async def tool_run_python_sandbox(
    script: str,
    description: str = "Execute Python script in local sandbox",
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    before_files = {p.name: p.stat().st_mtime for p in ARTIFACTS_DIR.iterdir() if p.is_file()}
    script_file = confine_to_workspace(ARTIFACTS_DIR / f"_sandbox_exec_{int(time.time() * 1000)}.py")
    script_file.write_text(script, encoding="utf-8")

    start_t = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_file)],
            cwd=str(ARTIFACTS_DIR),
            capture_output=True,
            text=True,
            timeout=30.0,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )
        duration_ms = int((time.time() - start_t) * 1000)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        returncode = proc.returncode
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
        if not p.is_file() or p.name.startswith("_sandbox_exec_") or p.name == ".gitkeep":
            continue
        if p.name not in before_files or p.stat().st_mtime > before_files[p.name]:
            ext = p.suffix.lower()
            mime, _ = mimetypes.guess_type(p.name)
            mime = mime or "application/octet-stream"
            if ext in (".xlsx", ".xls", ".csv"):
                category = "spreadsheet"
                preview = extract_excel_preview(p) if ext == ".xlsx" else {}
            elif ext in (".pdf", ".docx", ".doc", ".md", ".txt"):
                category = "document"
                preview = {"format": ext.lstrip(".")}
            elif ext in (".png", ".jpg", ".jpeg", ".svg", ".webp"):
                category = "image"
                preview = {"engine": "Python Sandbox"}
            elif ext in (".gif", ".mp4", ".webm"):
                category = "video"
                preview = {"engine": "Python Sandbox"}
            elif ext in (".html", ".htm"):
                category = "webapp"
                preview = {"code_snippet": p.read_text(encoding="utf-8", errors="ignore")[:1500]}
            else:
                category = "file"
                preview = {}

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

    return {
        "status": "success" if returncode == 0 else "error",
        "returncode": returncode,
        "duration_ms": duration_ms,
        "stdout": stdout[:4000],
        "stderr": stderr[:2000],
        "artifacts": created_artifacts,
    }


def get_tool_schemas(allow_web_search: bool = False) -> List[Dict[str, Any]]:
    schemas = [
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
                        "chart_data": {"type": "object"},
                    },
                    "required": ["prompt", "media_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_python_sandbox",
                "description": "Run a custom Python 3 script locally for calculations or file creation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "script": {"type": "string"},
                    },
                    "required": ["description", "script"],
                },
            },
        },
    ]

    if allow_web_search:
        schemas.append({
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the live internet via DuckDuckGo for current events, facts, or documentation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        })

    return schemas


TOOL_SCHEMAS = get_tool_schemas(allow_web_search=False)
