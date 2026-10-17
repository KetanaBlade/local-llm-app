"""
Antigravity Agent Orchestrator & Ollama Streaming Engine.

Implements:
- Auto-starting headless `ollama serve` if not already running on 127.0.0.1:11434
- Hardware-tuned context window (`num_ctx`) and `keep_alive` injection per hardware profile
- Multi-step Sense -> Plan -> Act -> Synthesize loop with real-time Server-Sent Events (SSE)
- Full conversation context preservation when switching between models mid-chat
- Optional live DuckDuckGo Web Search when the user switches from "Offline Only" to "Web Search On"
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .hardware import detect_nvidia_gpu
from .tools import (
    ARTIFACTS_DIR,
    get_tool_schemas,
    resolve_sd_model_and_prompts,
    tool_build_interactive_app,
    tool_create_document,
    tool_create_excel_spreadsheet,
    tool_edit_file_content,
    tool_execute_python,
    tool_generate_visual_media,
    tool_list_directory,
    tool_read_file,
    tool_run_python_sandbox,
    tool_search_web,
    WORKSPACE_DIR,
)

OLLAMA_BASE = "http://127.0.0.1:11434"


def find_ollama_binary() -> str:
    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        candidate = Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.exists():
            return str(candidate)
    return "ollama"


async def ensure_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                return True
    except Exception:
        pass

    try:
        binary = find_ollama_binary()
        subprocess.Popen(
            [binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )
        for _ in range(10):
            await asyncio.sleep(0.5)
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    r = await client.get(f"{OLLAMA_BASE}/api/tags")
                    if r.status_code == 200:
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


async def list_installed_models() -> List[Dict[str, Any]]:
    await ensure_ollama_running()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code != 200:
                return []
            data = r.json()
            models = []
            for m in data.get("models", []):
                size_bytes = m.get("size", 0)
                details = m.get("details", {})
                models.append({
                    "id": m.get("name"),
                    "name": m.get("name"),
                    "size_gb": round(size_bytes / (1024 ** 3), 2) if size_bytes else 0,
                    "family": details.get("family", ""),
                    "parameter_size": details.get("parameter_size", ""),
                    "quantization": details.get("quantization_level", ""),
                    "modified_at": m.get("modified_at", ""),
                })
            # Sort conversational models first (ahead of coding-specialized models)
            models.sort(key=lambda x: (1 if "coder" in (x.get("id") or "").lower() else 0, x.get("id") or ""))
            return models
    except Exception:
        return []


async def list_running_models() -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/ps")
            if r.status_code != 200:
                return []
            data = r.json()
            running = []
            for m in data.get("models", []):
                vram_bytes = m.get("size_vram", 0)
                total_bytes = m.get("size", 0)
                vram_pct = round((vram_bytes / total_bytes) * 100) if total_bytes else 100
                running.append({
                    "name": m.get("name"),
                    "size_gb": round(total_bytes / (1024 ** 3), 2),
                    "vram_gb": round(vram_bytes / (1024 ** 3), 2),
                    "vram_pct": vram_pct,
                })
            return running
    except Exception:
        return []


async def flush_ollama_vram(except_model: Optional[str] = None) -> List[str]:
    """
    Evict loaded Ollama models from GPU VRAM.
    If `except_model` is provided, evicts all loaded models EXCEPT `except_model`
    so two models never stack in VRAM simultaneously.
    """
    unloaded: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/ps")
            if r.status_code != 200:
                return []
            for m in r.json().get("models", []):
                name = m.get("name")
                if not name:
                    continue
                if except_model and name == except_model:
                    continue
                await client.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={"model": name, "keep_alive": 0},
                )
                unloaded.append(name)
    except Exception:
        pass
    return unloaded


def get_current_date_context() -> str:
    """
    Date Grounding Preamble (inspired by Odysseus).
    Grounds local LLM queries, plans, spreadsheets, and timeframes in the real world date,
    preventing models from defaulting to historical pre-training cutoff years.
    """
    now = datetime.now()
    return (
        f"Today's date is {now.strftime('%A, %B %d, %Y')} ({now.strftime('%Y-%m-%d')}). "
        f"Ground all time-sensitive plans, documents, spreadsheets, and relative dates in {now.year} "
        f"rather than historical pre-training cutoff years."
    )


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def compact_conversation_history(
    history_messages: List[Dict[str, Any]],
    num_ctx: int = 8192,
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Cursor-Style Context Auto-Compactor (inspired by Odysseus).
    When total accumulated messages exceed 8 turns OR ~60% of the model's context window,
    older turns are densely summarized into a structured recap, preserving key goals,
    files, and decisions while keeping the active prompt lean and avoiding context overflow.
    """
    valid_msgs = [m for m in history_messages if m.get("role") in ("user", "assistant") and m.get("content")]
    if len(valid_msgs) <= 6:
        return valid_msgs, None

    total_toks = sum(estimate_text_tokens(m.get("content", "")) for m in valid_msgs)
    threshold = int(num_ctx * 0.60)

    # If within safe budget and under 10 turns, no compaction needed
    if total_toks < threshold and len(valid_msgs) <= 10:
        return valid_msgs, None

    # Split into older turns to archive, and recent turns to preserve verbatim
    recent_count = 4
    older = valid_msgs[:-recent_count]
    recent = valid_msgs[-recent_count:]

    # Build dense structured archive
    turn_summaries = []
    artifacts_created = []
    for idx, m in enumerate(older, start=1):
        role = "User" if m["role"] == "user" else "Assistant"
        content_preview = m["content"].strip().replace("\n", " ")
        if len(content_preview) > 160:
            content_preview = content_preview[:160] + "..."
        turn_summaries.append(f"- Turn {idx} ({role}): {content_preview}")
        for art in m.get("artifacts") or []:
            if isinstance(art, dict) and art.get("filename"):
                artifacts_created.append(f"{art['filename']} ({art.get('category', 'file')})")

    archive_lines = [
        "=== CONVERSATION ARCHIVE & RECAP (AUTO-COMPACTED TO PRESERVE CONTEXT) ===",
        f"Archived {len(older)} earlier turn(s):",
        "\n".join(turn_summaries),
    ]
    if artifacts_created:
        archive_lines.append(f"Files / Artifacts Created in Earlier Turns: {', '.join(sorted(set(artifacts_created)))}")
    archive_lines.append("Continue the conversation seamlessly with full awareness of the above context.")
    archive_lines.append("=========================================================================")

    compaction_block = "\n".join(archive_lines)

    compacted = [
        {"role": "system", "content": compaction_block},
        *recent,
    ]
    return compacted, f"Auto-compacted {len(older)} earlier message turns ({total_toks} tokens preserved)"


SYSTEM_PROMPT_AGENT = """You are Local AI Studio, an autonomous local coding and orchestration agent running 100% on the user's computer. You operate like Antigravity, Cursor, and Claude Code: you converse, plan, and brainstorm freely, while also possessing full tool autonomy to inspect, edit, and create files directly on the user's computer.

CAPABILITIES:
You have direct local access to Python runtime and filesystem tools:
1. `execute_python`: Run Python 3 code directly on the user's computer. Pre-equipped with:
   - `openpyxl`: Inspect, read, modify, and format Excel (.xlsx) workbooks, update cells, add formulas, and save back to disk.
   - `pandas`: Process, clean, filter, and transform CSV, tabular data, and spreadsheets.
   - `python-docx`: Read and create Word (.docx) documents.
   - `reportlab`: Build executive PDF reports.
   - `matplotlib` & `PIL`: Generate high-DPI charts, edit or resize images.
   - `pathlib`, `os`, `shutil`: Search, inspect, and organize files and directories.
   Any file you modify on disk is automatically backed up (.bak) safely by the harness.
2. `read_file`: Inspect contents of local files on disk. Automatically previews spreadsheets (.xlsx/.csv) as formatted tables and reads text/code/json/markdown with line numbers.
3. `edit_file_content`: Surgically replace lines of code or text in a file with automatic backup.
4. `list_directory`: Explore files and folders on the user's computer.
5. `generate_visual_media`: Render neural images on local GPU via Stable Diffusion, high-DPI charts, or motion clips.
6. `search_web`: Search the web with shielded cloud proxy (when web search is enabled).

CRITICAL INTERACTION PROTOCOL:
- CONVERSATIONAL / PLANNING REQUESTS: When the user asks a question, plans, brainstorms, or asks about your capabilities (e.g. 'Can you edit an excel file?', 'How would you build this app?', 'What packages are installed?'):
  * DO NOT call tools with invented, imaginary, or dummy filenames (never invent dummy files like budget.xlsx).
  * Answer directly in clear, helpful natural language with Markdown formatting.
  * Explain your tools and approach enthusiastically, and ask the user for their file path, requirements, or next steps.
- ACTIONABLE DIRECTIVES: When the user asks you to perform a specific action (e.g. 'Create an excel sheet called sales.xlsx with columns A, B, C', 'Read data.csv and plot a histogram', 'Search for latest news on X'):
  * Autonomously invoke the appropriate tool (`execute_python`, `read_file`, `search_web`, etc.).
  * Inspect outputs, verify the result, and summarize what you did in your final response.
- If a tool encounters an error, inspect the traceback, fix the code or parameters, and re-execute.
"""

SYSTEM_PROMPT_CHAT = """You are Local AI Studio, a fast, private AI assistant running 100% on the user's computer. Provide clear, helpful, well-structured answers."""


def extract_tool_calls(msg_obj: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str]:
    """
    Extracts tool calls from an Ollama response object.
    Supports:
    1. Native `msg_obj['tool_calls']`
    2. Raw JSON objects in `msg_obj['content']`
    3. Markdown-fenced JSON blocks (```json ... ```)
    4. `<tool_call> ... </tool_call>` tags
    5. Formats with `parameters` or `arguments`

    Returns:
        (tool_calls, remaining_content)
    """
    native_calls = msg_obj.get("tool_calls") or []
    if native_calls:
        normalized = []
        for tc in native_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            normalized.append({
                "id": tc.get("id"),
                "function": {
                    "name": fn.get("name"),
                    "arguments": args
                }
            })
        return normalized, msg_obj.get("content", "")

    content = msg_obj.get("content", "")
    if not content:
        return [], ""

    valid_tool_names = {
        "execute_python", "run_python_sandbox",
        "read_file", "edit_file_content",
        "list_directory", "generate_visual_media",
        "create_excel_spreadsheet", "create_document",
        "build_interactive_app", "search_web"
    }

    found_calls = []
    clean_text = content

    # Check for <tool_call>...</tool_call>
    tool_call_tags = re.findall(r"<tool_call>([\s\S]*?)</tool_call>", content)
    for tag_body in tool_call_tags:
        try:
            parsed = json.loads(tag_body.strip())
            name = parsed.get("name")
            args = parsed.get("arguments") or parsed.get("parameters") or {}
            if name in valid_tool_names:
                found_calls.append({"function": {"name": name, "arguments": args}})
                clean_text = clean_text.replace(f"<tool_call>{tag_body}</tool_call>", "")
        except Exception:
            pass

    if found_calls:
        return found_calls, clean_text.strip()

    # Check for markdown code fences ```json ... ``` or ``` ... ```
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    for block in code_blocks:
        block_trimmed = block.strip()
        if block_trimmed.startswith("{") and block_trimmed.endswith("}"):
            try:
                parsed = json.loads(block_trimmed)
                name = parsed.get("name")
                args = parsed.get("arguments") or parsed.get("parameters") or {}
                if name in valid_tool_names:
                    found_calls.append({"function": {"name": name, "arguments": args}})
                    clean_text = clean_text.replace(f"```{block}```", "")
            except Exception:
                pass

    if found_calls:
        return found_calls, clean_text.strip()

    # Check for raw JSON object in content (e.g. `{"name":"execute_python","parameters":{...}}`)
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            name = parsed.get("name")
            args = parsed.get("arguments") or parsed.get("parameters") or {}
            if name in valid_tool_names:
                found_calls.append({"function": {"name": name, "arguments": args}})
                return found_calls, ""
        except Exception:
            pass

    # Regex find any JSON object containing "name": "<tool_name>"
    json_candidates = re.finditer(r"(\{[\s\S]*?\"name\"\s*:\s*\"([a-zA-Z0-9_-]+)\"[\s\S]*?\})", content)
    for m in json_candidates:
        full_match = m.group(1)
        name = m.group(2)
        if name in valid_tool_names:
            try:
                parsed = json.loads(full_match)
                args = parsed.get("arguments") or parsed.get("parameters") or {}
                found_calls.append({"function": {"name": name, "arguments": args}})
                clean_text = clean_text.replace(full_match, "")
            except Exception:
                pass

    return found_calls, clean_text.strip()



async def execute_tool_call(
    func_name: str,
    args: Dict[str, Any],
    conversation_id: str,
    active_model: str,
    vram_handoff: bool,
    offline_mode: bool = True,
    brave_api_key: str = "",
) -> Dict[str, Any]:
    start_t = time.time()
    try:
        if func_name in ("execute_python", "run_python_sandbox"):
            res = await tool_execute_python(
                script=args.get("script", "print('OK')"),
                description=args.get("description", "Python execution"),
                target_filepath=args.get("target_filepath"),
                conversation_id=conversation_id,
            )
        elif func_name == "read_file":
            res = await tool_read_file(
                filepath=args.get("filepath", ""),
                start_line=int(args.get("start_line", 1)),
                max_lines=int(args.get("max_lines", 250)),
            )
        elif func_name == "edit_file_content":
            res = await tool_edit_file_content(
                filepath=args.get("filepath", ""),
                target_content=args.get("target_content", ""),
                replacement_content=args.get("replacement_content", ""),
            )
        elif func_name == "list_directory":
            res = await tool_list_directory(
                directory_path=args.get("directory_path", "."),
                max_entries=int(args.get("max_entries", 100)),
            )
        elif func_name == "create_excel_spreadsheet":
            res = await tool_create_excel_spreadsheet(
                title=args.get("title", "Custom Workbook"),
                sheets=args.get("sheets") or [],
                conversation_id=conversation_id,
            )
        elif func_name == "create_document":
            res = await tool_create_document(
                title=args.get("title", "Document Report"),
                doc_format=args.get("doc_format", "pdf"),
                sections=args.get("sections") or [],
                conversation_id=conversation_id,
            )
        elif func_name == "build_interactive_app":
            res = await tool_build_interactive_app(
                title=args.get("title", "Interactive App"),
                html_code=args.get("html_code", "<h1>Interactive App</h1>"),
                conversation_id=conversation_id,
            )
        elif func_name == "generate_visual_media":
            res = await tool_generate_visual_media(
                prompt=args.get("prompt", "Visual Synthesis"),
                media_type=args.get("media_type", "image"),
                style=args.get("style", "auto"),
                chart_data=args.get("chart_data"),
                active_model=active_model,
                vram_handoff=vram_handoff,
                conversation_id=conversation_id,
            )
        elif func_name == "search_web":
            res = await tool_search_web(
                query=args.get("query", ""),
                offline_mode=offline_mode,
                brave_api_key=brave_api_key,
            )
        else:
            res = {"status": "error", "summary": f"Unknown tool: {func_name}"}
    except Exception as exc:
        res = {"status": "error", "summary": f"Tool execution error: {exc}"}

    res["duration_ms"] = int((time.time() - start_t) * 1000)
    return res


def detect_proactive_artifact_intent(user_prompt: str) -> Optional[Dict[str, Any]]:
    p_low = user_prompt.lower()

    # 1. Video / Motion Clip
    if any(k in p_low for k in ("generate a video", "create a video", "animate", "motion clip", "animated gif")):
        return {"name": "generate_visual_media", "intent": "video"}

    # 2. Explicit image model names
    if any(k in p_low for k in ("cyberrealistic", "meinamix", "dreamshaper", "stable diffusion")):
        return {"name": "generate_visual_media", "intent": "image"}

    # 3. Direct visual phrases
    direct_phrases = (
        "generate an image", "create an image", "make an image", "render an image",
        "create a picture", "generate a picture", "make a picture", "render a picture",
        "generate a photo", "create a photo", "make a photo", "render a photo",
        "draw a ", "draw an ", "paint a ", "paint an ", "sketch a ", "sketch an ",
        "photo of ", "picture of ", "image of ", "portrait of ", "illustration of ",
        "painting of ", "render of ", "artwork of ", "visualize ", "depict "
    )
    if any(k in p_low for k in direct_phrases):
        return {"name": "generate_visual_media", "intent": "image"}

    # 4. Pattern: Creation verb + visual noun (e.g. "generate a realistic portrait", "create adult art")
    visual_nouns = (
        "image", "picture", "photo", "photograph", "portrait", "drawing",
        "illustration", "render", "painting", "artwork", "wallpaper",
        "pinup", "visual", "graphic", "sketch", "art"
    )
    creation_verbs = (
        "generate", "create", "make", "draw", "render", "paint",
        "show me", "give me", "produce", "craft", "sketch", "depict", "visualize"
    )
    has_noun = any(re.search(rf"\b{re.escape(n)}s?\b", p_low) for n in visual_nouns)
    has_verb = any(re.search(rf"\b{re.escape(v)}\b", p_low) for v in creation_verbs)
    if has_noun and has_verb:
        return {"name": "generate_visual_media", "intent": "image"}

    return None


async def run_agent_stream(
    conversation_id: str,
    history_messages: List[Dict[str, Any]],
    user_prompt: str,
    model: str,
    mode: str,
    hw_profile: Dict[str, Any],
    offline_mode: bool = True,
    chat_context: str = "",
    gaming_mode: bool = False,
    image_style: str = "auto",
    brave_api_key: str = "",
    attached_files: Optional[List[Dict[str, Any]]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    # Direct Image Generation Mode: 100% bypass of LLM parsing & zero corporate moralizing
    if mode == "image" or model.startswith("sd:"):
        selected_style = image_style
        if model.startswith("sd:"):
            selected_style = model[3:]

        model_path, resolved_style, _, _, engine_label = resolve_sd_model_and_prompts(
            prompt=user_prompt,
            requested_style=selected_style,
        )
        yield {"type": "status", "message": f"Rendering on local GPU using {engine_label.split('(')[0].strip()}..."}
        trace_id = f"tc_{int(time.time() * 1000)}_direct"
        fn_args = {"prompt": user_prompt, "media_type": "image", "style": selected_style}
        trace_entry = {
            "id": trace_id,
            "name": "generate_visual_media",
            "arguments": fn_args,
            "status": "running",
            "engine_label": engine_label,
            "summary": f"Rendering {resolved_style} image using {engine_label.split('(')[0].strip()}",
        }
        yield {"type": "tool_start", "tool": trace_entry}
        exec_res = await execute_tool_call(
            func_name="generate_visual_media",
            args=fn_args,
            conversation_id=conversation_id,
            active_model="",
            vram_handoff=True,
            offline_mode=offline_mode,
            brave_api_key=brave_api_key,
        )
        trace_entry["status"] = exec_res.get("status", "success")
        trace_entry["duration_ms"] = exec_res.get("duration_ms", 0)
        trace_entry["summary"] = exec_res.get("summary", "Generated visual media")
        direct_arts = []
        if exec_res.get("artifact"):
            direct_arts.append(exec_res["artifact"])
        yield {"type": "tool_end", "tool": trace_entry, "artifacts": direct_arts}

        yield {
            "type": "done",
            "content": f"Rendered image via local **{engine_label.split('(')[0].strip()}** on your local GPU.",
            "thinking": "",
            "tool_calls": [trace_entry],
            "artifacts": direct_arts,
            "tokens_per_sec": 0.0,
        }
        return

    await ensure_ollama_running()
    # Ensure no other model is simultaneously hogging VRAM alongside `model`
    await flush_ollama_vram(except_model=model)

    gpu_info = detect_nvidia_gpu()
    free_vram_gb = gpu_info.get("vram_free_gb", 12.0) if gpu_info else 12.0
    auto_game_active = (free_vram_gb < 4.5)
    use_cpu_ram = gaming_mode or auto_game_active

    tuning = hw_profile.get("tuning", {})
    num_ctx = tuning.get("recommended_num_ctx", 8192)
    keep_alive = tuning.get("keep_alive", "10m")
    vram_handoff = tuning.get("vram_handoff_before_media", True)
    allow_web_search = not offline_mode

    if use_cpu_ram:
        # Offload 100% of LLM to 64GB System RAM so running games have full GPU VRAM
        num_ctx = min(num_ctx, 4096)
        ollama_options: Dict[str, Any] = {"num_ctx": num_ctx, "num_gpu": 0, "temperature": 0.3}
        stream_options: Dict[str, Any] = {"num_ctx": num_ctx, "num_gpu": 0}
        keep_alive = 0
        probe_timeout = 25.0
        reason = "🎮 Gaming Mode active" if gaming_mode else f"🎮 Auto-VRAM Guard active ({free_vram_gb:.1f}GB free)"
        yield {"type": "status", "message": f"{reason} • Offloading {model} to 64GB System RAM (0% GPU VRAM)..."}
    else:
        ollama_options = {"num_ctx": num_ctx, "temperature": 0.3}
        stream_options = {"num_ctx": num_ctx}
        probe_timeout = 30.0

    sys_prompt = SYSTEM_PROMPT_AGENT if mode == "agent" else SYSTEM_PROMPT_CHAT
    # 1. Date Grounding (inspired by Odysseus): stops models from defaulting to historical training-cutoff years
    sys_prompt = f"{get_current_date_context()}\n\n{sys_prompt}"

    if chat_context and chat_context.strip():
        sys_prompt += (
            "\n\n=== USER BACKGROUND CONTEXT & INSTRUCTIONS FOR THIS CONVERSATION ===\n"
            f"{chat_context.strip()}\n"
            "===================================================================="
        )

    if attached_files:
        attachment_lines = []
        for af in attached_files:
            fname = af.get("filename") or af.get("title", "")
            fpath = af.get("path") or f"workspace/artifacts/{fname}"
            fcat = af.get("category", "file")
            attachment_lines.append(f"- `{fname}` (Category: {fcat}, Location: `{fpath}`)")
        sys_prompt += (
            "\n\n=== ATTACHED WORKSPACE FILES FOR THIS REQUEST ===\n"
            + "\n".join(attachment_lines)
            + "\nYou can inspect and process these files directly using your tools (such as `read_file`, or `execute_python` with openpyxl/pandas).\n"
            + "=================================================="
        )

    if mode == "agent":
        try:
            ws_files = []
            for item in sorted(WORKSPACE_DIR.glob("**/*"))[:30]:
                if item.is_file() and not item.name.startswith(".") and ".bak" not in item.name:
                    rel_p = str(item.relative_to(WORKSPACE_DIR)).replace("\\", "/")
                    size_kb = round(item.stat().st_size / 1024, 1)
                    ws_files.append(f"- `{rel_p}` ({size_kb} KB)")
            if ws_files:
                sys_prompt += (
                    f"\n\n=== LOCAL WORKSPACE DIRECTORY ({WORKSPACE_DIR.resolve()}) ===\n"
                    + "\n".join(ws_files)
                    + "\nYou have direct filesystem tools (`read_file`, `edit_file_content`, `list_directory`, `execute_python`) to inspect, edit, or create files in this workspace.\n"
                    + "================================================================"
                )
        except Exception:
            pass

    ollama_messages = [{"role": "system", "content": sys_prompt}]

    # 2. Context Auto-Compaction (Cursor-style self-summarizing context window guard)
    compacted_history, compaction_notice = compact_conversation_history(history_messages, num_ctx=num_ctx)
    if compaction_notice:
        yield {"type": "status", "message": f"Context compact: {compaction_notice}"}

    for m in compacted_history:
        if m["role"] in ("system", "user", "assistant"):
            ollama_messages.append({"role": m["role"], "content": m["content"]})
    user_msg_payload: Dict[str, Any] = {"role": "user", "content": user_prompt}
    if attached_files:
        img_b64s = []
        for af in attached_files:
            if af.get("category") == "image":
                fname = af.get("filename")
                if fname:
                    img_path = ARTIFACTS_DIR / fname
                    if img_path.exists():
                        try:
                            b64_val = base64.b64encode(img_path.read_bytes()).decode("utf-8")
                            img_b64s.append(b64_val)
                        except Exception:
                            pass
        if img_b64s:
            user_msg_payload["images"] = img_b64s
    ollama_messages.append(user_msg_payload)

    tool_traces: List[Dict[str, Any]] = []
    collected_artifacts: List[Dict[str, Any]] = []

    if mode == "agent":
        max_agent_steps = 5
        current_step = 0
        active_schemas = get_tool_schemas(allow_web_search=allow_web_search)

        while current_step < max_agent_steps:
            yield {
                "type": "status",
                "message": f"Orchestrating with {model} (step {current_step + 1}/{max_agent_steps})...",
            }
            try:
                async with httpx.AsyncClient(timeout=probe_timeout) as client:
                    probe_resp = await client.post(
                        f"{OLLAMA_BASE}/api/chat",
                        json={
                            "model": model,
                            "messages": ollama_messages,
                            "tools": active_schemas,
                            "stream": False,
                            "keep_alive": keep_alive,
                            "options": ollama_options,
                        },
                    )
                    if probe_resp.status_code != 200:
                        break

                    probe_data = probe_resp.json()
                    msg_obj = probe_data.get("message", {})
                    extracted_calls, remaining_content = extract_tool_calls(msg_obj)

                    if not extracted_calls:
                        # If tools were already executed in prior steps, break out so the final synthesis streams live
                        if tool_traces:
                            break

                        direct_content = remaining_content or msg_obj.get("content", "")
                        if not direct_content:
                            break

                        # Check for moralizing refusal bypass if user asked for visual media
                        refusal_markers = (
                            "i can't fulfill", "i cannot fulfill", "i can't assist", "i cannot assist",
                            "i'm sorry, but i cannot", "i am sorry, but i cannot", "as an ai language model",
                            "unable to fulfill this request", "cannot fulfill this request",
                            "i'm unable to fulfill", "i am unable to fulfill", "cannot assist with that",
                            "i can't help with that", "i cannot help with that", "i'm sorry, but i can't",
                            "i am sorry, but i can't", "sorry, but i can't fulfill", "sorry, i cannot"
                        )
                        is_refusal = any(m in direct_content.lower() for m in refusal_markers)
                        if is_refusal:
                            img_intent = detect_proactive_artifact_intent(user_prompt)
                            if img_intent and img_intent.get("intent") in ("image", "video"):
                                trace_id = f"tc_{int(time.time() * 1000)}_bypass"
                                fn_args = {"prompt": user_prompt, "media_type": img_intent["intent"]}
                                _, resolved_style, _, _, engine_label = resolve_sd_model_and_prompts(user_prompt, "auto")
                                trace_entry = {
                                    "id": trace_id,
                                    "name": "generate_visual_media",
                                    "arguments": fn_args,
                                    "status": "running",
                                    "engine_label": engine_label,
                                    "summary": f"Rendering {resolved_style} image using {engine_label.split('(')[0].strip()}",
                                }
                                yield {"type": "status", "message": f"Dispatching image to local {engine_label.split('(')[0].strip()} on GPU..."}
                                yield {"type": "tool_start", "tool": trace_entry}
                                exec_res = await execute_tool_call(
                                    func_name="generate_visual_media",
                                    args=fn_args,
                                    conversation_id=conversation_id,
                                    active_model=model,
                                    vram_handoff=vram_handoff,
                                    offline_mode=offline_mode,
                                )
                                trace_entry["status"] = exec_res.get("status", "success")
                                trace_entry["duration_ms"] = exec_res.get("duration_ms", 0)
                                trace_entry["summary"] = exec_res.get("summary", "Generated visual media")
                                tool_traces.append(trace_entry)
                                if exec_res.get("artifact"):
                                    collected_artifacts.append(exec_res["artifact"])
                                    yield {"type": "tool_end", "tool": trace_entry, "artifacts": [exec_res["artifact"]]}

                                bypass_text = f"Rendered image via local **{engine_label.split('(')[0].strip()}** on your local GPU."
                                yield {
                                    "type": "done",
                                    "content": bypass_text,
                                    "thinking": "",
                                    "tool_calls": tool_traces,
                                    "artifacts": collected_artifacts,
                                    "tokens_per_sec": 0.0,
                                }
                                return

                        eval_count = probe_data.get("eval_count", 0)
                        eval_dur = probe_data.get("eval_duration", 1)
                        tok_s = round(eval_count / (eval_dur / 1e9), 1) if eval_dur > 0 else 0.0
                        thinking_text, clean_text = _split_thinking(direct_content)
                        if thinking_text:
                            yield {"type": "thinking", "delta": thinking_text}
                        chunk_size = 28
                        for i in range(0, len(clean_text), chunk_size):
                            yield {"type": "token", "delta": clean_text[i : i + chunk_size]}
                            await asyncio.sleep(0.008)
                        yield {
                            "type": "done",
                            "content": clean_text,
                            "thinking": thinking_text,
                            "tool_calls": tool_traces,
                            "artifacts": collected_artifacts,
                            "tokens_per_sec": tok_s,
                        }
                        return

                    # Record assistant message with tool calls in history
                    ollama_messages.append({
                        "role": "assistant",
                        "content": remaining_content,
                        "tool_calls": extracted_calls,
                    })

                    # Execute all tools returned in this step
                    for idx, tc in enumerate(extracted_calls):
                        fn = tc.get("function", {})
                        fn_name = fn.get("name", "")
                        fn_args = fn.get("arguments") or {}
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}

                        trace_id = f"tc_{int(time.time() * 1000)}_{current_step}_{idx}"
                        trace_entry = {
                            "id": trace_id,
                            "name": fn_name,
                            "arguments": fn_args,
                            "status": "running",
                            "summary": f"Executing {fn_name}...",
                        }
                        if fn_name == "generate_visual_media":
                            p_in = fn_args.get("prompt", "")
                            st_in = fn_args.get("style", "auto")
                            _, resolved_style, _, _, engine_label = resolve_sd_model_and_prompts(p_in, st_in)
                            trace_entry["engine_label"] = engine_label
                            trace_entry["summary"] = f"Rendering {resolved_style} image using {engine_label.split('(')[0].strip()}"
                        elif fn_name in ("execute_python", "run_python_sandbox"):
                            trace_entry["summary"] = f"Running Python: {fn_args.get('description', 'script')[:60]}"
                        elif fn_name == "read_file":
                            trace_entry["summary"] = f"Reading file: {Path(fn_args.get('filepath', '')).name}"
                        elif fn_name == "edit_file_content":
                            trace_entry["summary"] = f"Editing file: {Path(fn_args.get('filepath', '')).name}"
                        elif fn_name == "list_directory":
                            trace_entry["summary"] = f"Listing folder: {fn_args.get('directory_path', '.')}"
                        elif fn_name == "create_excel_spreadsheet":
                            trace_entry["summary"] = f"Building Excel workbook: {fn_args.get('title', 'Workbook')}"
                        elif fn_name == "create_document":
                            trace_entry["summary"] = f"Building Document: {fn_args.get('title', 'Document')}"

                        yield {"type": "tool_start", "tool": trace_entry}

                        exec_res = await execute_tool_call(
                            func_name=fn_name,
                            args=fn_args,
                            conversation_id=conversation_id,
                            active_model=model,
                            vram_handoff=vram_handoff,
                            offline_mode=offline_mode,
                            brave_api_key=brave_api_key,
                        )

                        trace_entry["status"] = exec_res.get("status", "success")
                        trace_entry["duration_ms"] = exec_res.get("duration_ms", 0)
                        trace_entry["stdout"] = exec_res.get("stdout")
                        trace_entry["stderr"] = exec_res.get("stderr")
                        trace_entry["summary"] = exec_res.get("summary") or exec_res.get("stdout") or "Completed"
                        if exec_res.get("backup_created"):
                            trace_entry["backup_created"] = exec_res["backup_created"]
                        if fn_name == "search_web":
                            trace_entry["sources"] = exec_res.get("results", [])
                            trace_entry["summary"] = f"Searched '{fn_args.get('query', '')}' • {len(exec_res.get('results', []))} sources retrieved"

                        tool_traces.append(trace_entry)

                        new_arts = []
                        if exec_res.get("artifact"):
                            new_arts.append(exec_res["artifact"])
                        if exec_res.get("artifacts"):
                            new_arts.extend(exec_res["artifacts"])
                        for art in new_arts:
                            collected_artifacts.append(art)

                        yield {"type": "tool_end", "tool": trace_entry, "artifacts": new_arts}

                        tool_payload = {
                            "status": exec_res.get("status"),
                            "summary": trace_entry["summary"],
                        }
                        if exec_res.get("stdout"):
                            tool_payload["stdout"] = exec_res["stdout"]
                        if exec_res.get("stderr"):
                            tool_payload["stderr"] = exec_res["stderr"]
                        if exec_res.get("content"):
                            tool_payload["content"] = exec_res["content"]
                        if exec_res.get("backup_created"):
                            tool_payload["backup_created"] = exec_res["backup_created"]
                        if new_arts:
                            tool_payload["artifacts_created"] = [a["filename"] for a in new_arts]
                        if exec_res.get("results"):
                            tool_payload["web_results"] = exec_res["results"]

                        ollama_messages.append({
                            "role": "tool",
                            "content": json.dumps(tool_payload),
                        })

                    current_step += 1
            except Exception:
                break

    full_content = ""
    thinking_content = ""
    in_think_block = False
    tok_s = 0.0
    start_stream_t = time.time()
    token_count = 0

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "stream": True,
                    "keep_alive": keep_alive,
                    "options": stream_options,
                },
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    err_msg = (
                        f"Model `{model}` is not installed yet. "
                        f"Click **Add / Manage Models** to download `{model}`.\n\n"
                        f"*(Detail: {err_body.decode('utf-8', errors='ignore')[:200]})*"
                    )
                    yield {"type": "token", "delta": err_msg}
                    yield {
                        "type": "done",
                        "content": err_msg,
                        "thinking": "",
                        "tool_calls": tool_traces,
                        "artifacts": collected_artifacts,
                        "tokens_per_sec": 0.0,
                    }
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    delta = msg.get("content", "")
                    if delta:
                        token_count += 1
                        if "<think>" in delta:
                            in_think_block = True
                            delta = delta.replace("<think>", "")
                        if "</think>" in delta:
                            parts = delta.split("</think>", 1)
                            thinking_content += parts[0]
                            yield {"type": "thinking", "delta": parts[0]}
                            in_think_block = False
                            delta = parts[1]
                        if in_think_block:
                            thinking_content += delta
                            yield {"type": "thinking", "delta": delta}
                        elif delta:
                            full_content += delta
                            yield {"type": "token", "delta": delta}

                    if chunk.get("done"):
                        eval_count = chunk.get("eval_count", token_count)
                        eval_dur = chunk.get("eval_duration", 0)
                        if eval_dur > 0:
                            tok_s = round(eval_count / (eval_dur / 1e9), 1)
                        else:
                            elapsed = max(0.1, time.time() - start_stream_t)
                            tok_s = round(token_count / elapsed, 1)
    except Exception as exc:
        err_text = f"\n\n*Connection note: Local Ollama engine responded with: {exc}*"
        full_content += err_text
        yield {"type": "token", "delta": err_text}

    yield {
        "type": "done",
        "content": full_content.strip(),
        "thinking": thinking_content.strip(),
        "tool_calls": tool_traces,
        "artifacts": collected_artifacts,
        "tokens_per_sec": tok_s,
    }


def _split_thinking(text: str) -> tuple[str, str]:
    match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
    if not match:
        return "", text
    thinking = match.group(1).strip()
    clean = (text[: match.start()] + text[match.end() :]).strip()
    return thinking, clean
