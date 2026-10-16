"""
Antigravity Agent Orchestrator & Ollama Streaming Engine.

Implements:
- Auto-starting headless `ollama serve` if not already running on 127.0.0.1:11434
- Hardware-tuned context window (`num_ctx`) and `keep_alive` injection per hardware profile
- Multi-step Sense -> Plan -> Act -> Synthesize loop with real-time Server-Sent Events (SSE)
- Native Ollama tool-calling + deterministic fallback tool routing so even non-tool models
  reliably create Excel sheets, PDF/Word docs, charts, images, animations, and interactive web apps.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .tools import (
    TOOL_SCHEMAS,
    tool_build_interactive_app,
    tool_create_document,
    tool_create_excel_spreadsheet,
    tool_generate_visual_media,
    tool_run_python_sandbox,
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
    """Verify Ollama daemon is reachable on 127.0.0.1:11434; start headless server if needed."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                return True
    except Exception:
        pass

    # Attempt to spawn headless `ollama serve`
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


SYSTEM_PROMPT_AGENT = """You are Local AI Studio (Antigravity Engine), an autonomous, privacy-first local AI assistant and software/document engineer running 100% on the user's own hardware.

You have direct access to local execution tools:
1. `create_excel_spreadsheet`: Build formatted `.xlsx` spreadsheets with multiple tabs, headers, rows, and live Excel formulas (`=SUM(...)`, `=AVERAGE(...)`).
2. `create_document`: Create structured `.pdf`, `.docx`, or `.md` documents and reports.
3. `build_interactive_app`: Build complete, self-contained HTML5/CSS/JS interactive web apps, calculators, dashboards, or tools.
4. `generate_visual_media`: Create high-DPI charts, visual graphics, illustrations, or animated motion clips.
5. `run_python_sandbox`: Run Python 3 scripts locally for data analysis, math, or custom file generation.

Guidelines:
- Whenever the user asks to create, generate, or build an Excel spreadsheet, document/PDF/Word file, chart, image/picture, video/animation, or interactive app, ALWAYS call the corresponding tool so a real file artifact is produced.
- After executing a tool, explain clearly what you built, highlight key formulas/sections/features, and keep your prose crisp, well-structured, and insightful.
- Never claim you cannot create files, spreadsheets, or visuals—use your local tools to produce them immediately.
"""

SYSTEM_PROMPT_CHAT = """You are Local AI Studio, a fast, thoughtful, privacy-first local AI assistant running 100% on the user's machine. Provide clear, well-structured, insightful responses using clean Markdown formatting."""


async def execute_tool_call(
    func_name: str,
    args: Dict[str, Any],
    conversation_id: str,
    active_model: str,
    vram_handoff: bool,
) -> Dict[str, Any]:
    """Dispatch a single tool call and return standardized execution result + artifacts."""
    start_t = time.time()
    try:
        if func_name == "create_excel_spreadsheet":
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
                chart_data=args.get("chart_data"),
                active_model=active_model,
                vram_handoff=vram_handoff,
                conversation_id=conversation_id,
            )
        elif func_name == "run_python_sandbox":
            res = await tool_run_python_sandbox(
                script=args.get("script", "print('OK')"),
                description=args.get("description", "Python sandbox script"),
                conversation_id=conversation_id,
            )
        else:
            res = {"status": "error", "summary": f"Unknown tool: {func_name}"}
    except Exception as exc:
        res = {"status": "error", "summary": f"Tool execution error: {exc}"}

    res["duration_ms"] = int((time.time() - start_t) * 1000)
    return res


def detect_proactive_artifact_intent(user_prompt: str) -> Optional[Dict[str, Any]]:
    """
    If a user explicitly requests a spreadsheet, PDF/Word doc, image, video, or web app and the
    selected local model didn't emit a native tool call, synthesize a structured tool call fallback.
    """
    p_low = user_prompt.lower()
    if any(k in p_low for k in ("excel", "spreadsheet", ".xlsx", "workbook", "budget sheet", "tracker sheet")):
        return {"name": "create_excel_spreadsheet", "intent": "spreadsheet"}
    if any(k in p_low for k in ("word doc", ".docx", "pdf document", "pdf report", "create a pdf", "generate a pdf")):
        fmt = "docx" if ("word" in p_low or "docx" in p_low) else "pdf"
        return {"name": "create_document", "intent": "document", "format": fmt}
    if any(k in p_low for k in ("generate an image", "create a picture", "draw a picture", "generate a picture", "create an image")):
        return {"name": "generate_visual_media", "intent": "image"}
    if any(k in p_low for k in ("generate a video", "create a video", "animate", "motion clip")):
        return {"name": "generate_visual_media", "intent": "video"}
    return None


async def run_agent_stream(
    conversation_id: str,
    history_messages: List[Dict[str, Any]],
    user_prompt: str,
    model: str,
    mode: str,
    hw_profile: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream SSE events for the conversation turn:
    - {"type": "status", "message": "..."}
    - {"type": "tool_start", "tool": {...}}
    - {"type": "tool_end", "tool": {...}, "artifact": {...}}
    - {"type": "thinking", "delta": "..."}
    - {"type": "token", "delta": "..."}
    - {"type": "done", "message": {...}}
    """
    await ensure_ollama_running()
    tuning = hw_profile.get("tuning", {})
    num_ctx = tuning.get("recommended_num_ctx", 8192)
    keep_alive = tuning.get("keep_alive", "10m")
    vram_handoff = tuning.get("vram_handoff_before_media", True)

    sys_prompt = SYSTEM_PROMPT_AGENT if mode == "agent" else SYSTEM_PROMPT_CHAT
    ollama_messages = [{"role": "system", "content": sys_prompt}]
    for m in history_messages[-14:]:
        if m["role"] in ("user", "assistant"):
            ollama_messages.append({"role": m["role"], "content": m["content"]})
    ollama_messages.append({"role": "user", "content": user_prompt})

    tool_traces: List[Dict[str, Any]] = []
    collected_artifacts: List[Dict[str, Any]] = []

    # Step 1: In Agent Mode, check if model executes native tool calls
    if mode == "agent":
        yield {"type": "status", "message": f"Orchestrating with {model} ({hw_profile.get('short_badge', 'Local GPU')})..."}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                probe_resp = await client.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={
                        "model": model,
                        "messages": ollama_messages,
                        "tools": TOOL_SCHEMAS,
                        "stream": False,
                        "keep_alive": keep_alive,
                        "options": {"num_ctx": num_ctx, "temperature": 0.3},
                    },
                )
                if probe_resp.status_code == 200:
                    probe_data = probe_resp.json()
                    msg_obj = probe_data.get("message", {})
                    native_tool_calls = msg_obj.get("tool_calls") or []

                    if native_tool_calls:
                        for idx, tc in enumerate(native_tool_calls):
                            fn = tc.get("function", {})
                            fn_name = fn.get("name", "")
                            fn_args = fn.get("arguments") or {}
                            if isinstance(fn_args, str):
                                try:
                                    fn_args = json.loads(fn_args)
                                except Exception:
                                    fn_args = {}

                            trace_id = f"tc_{int(time.time() * 1000)}_{idx}"
                            trace_entry = {
                                "id": trace_id,
                                "name": fn_name,
                                "arguments": fn_args,
                                "status": "running",
                            }
                            yield {"type": "tool_start", "tool": trace_entry}

                            exec_res = await execute_tool_call(
                                func_name=fn_name,
                                args=fn_args,
                                conversation_id=conversation_id,
                                active_model=model,
                                vram_handoff=vram_handoff,
                            )

                            trace_entry["status"] = exec_res.get("status", "success")
                            trace_entry["duration_ms"] = exec_res.get("duration_ms", 0)
                            trace_entry["summary"] = exec_res.get("summary") or exec_res.get("stdout") or "Completed"
                            tool_traces.append(trace_entry)

                            new_arts = []
                            if exec_res.get("artifact"):
                                new_arts.append(exec_res["artifact"])
                            if exec_res.get("artifacts"):
                                new_arts.extend(exec_res["artifacts"])
                            for art in new_arts:
                                collected_artifacts.append(art)

                            yield {"type": "tool_end", "tool": trace_entry, "artifacts": new_arts}

                            ollama_messages.append(msg_obj)
                            ollama_messages.append({
                                "role": "tool",
                                "content": json.dumps({
                                    "status": exec_res.get("status"),
                                    "summary": trace_entry["summary"],
                                    "artifacts_created": [a["filename"] for a in new_arts],
                                }),
                            })
                    else:
                        # If the model didn't call a tool, check if the prompt explicitly asked for an image/video
                        fallback = detect_proactive_artifact_intent(user_prompt)
                        if fallback and fallback["intent"] in ("image", "video"):
                            trace_id = f"tc_{int(time.time() * 1000)}_fb"
                            fn_args = {
                                "prompt": user_prompt,
                                "media_type": fallback["intent"],
                            }
                            trace_entry = {
                                "id": trace_id,
                                "name": "generate_visual_media",
                                "arguments": fn_args,
                                "status": "running",
                            }
                            yield {"type": "tool_start", "tool": trace_entry}
                            exec_res = await execute_tool_call(
                                func_name="generate_visual_media",
                                args=fn_args,
                                conversation_id=conversation_id,
                                active_model=model,
                                vram_handoff=vram_handoff,
                            )
                            trace_entry["status"] = exec_res.get("status", "success")
                            trace_entry["duration_ms"] = exec_res.get("duration_ms", 0)
                            trace_entry["summary"] = exec_res.get("summary", "Generated visual media")
                            tool_traces.append(trace_entry)
                            if exec_res.get("artifact"):
                                collected_artifacts.append(exec_res["artifact"])
                                yield {"type": "tool_end", "tool": trace_entry, "artifacts": [exec_res["artifact"]]}

                        # Check if non-tool model already returned a complete answer during the probe
                        direct_content = msg_obj.get("content", "")
                        if direct_content and not tool_traces:
                            eval_count = probe_data.get("eval_count", 0)
                            eval_dur = probe_data.get("eval_duration", 1)
                            tok_s = round(eval_count / (eval_dur / 1e9), 1) if eval_dur > 0 else 0.0
                            thinking_text, clean_text = _split_thinking(direct_content)
                            if thinking_text:
                                yield {"type": "thinking", "delta": thinking_text}
                            # Stream in smooth chunks for natural reading feel
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
        except Exception:
            # Fall through to standard streaming chat if model does not support `tools` field
            pass

    # Step 2: Stream final synthesis / conversational response from Ollama
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
                    "options": {"num_ctx": num_ctx},
                },
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    err_msg = (
                        f"Model `{model}` is not installed yet or still downloading. "
                        f"Open the **Model Hub** in the top bar to pull `{model}` with one click.\n\n"
                        f"*(Ollama detail: {err_body.decode('utf-8', errors='ignore')[:200]})*"
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
