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
    get_tool_schemas,
    tool_build_interactive_app,
    tool_create_document,
    tool_create_excel_spreadsheet,
    tool_generate_visual_media,
    tool_run_python_sandbox,
    tool_search_web,
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


SYSTEM_PROMPT_AGENT = """You are Local AI Studio, a personal AI assistant and file creator running 100% on the user's computer.

You can answer general questions conversationally AND you have local tools to create real files when asked:
1. `create_excel_spreadsheet`: Build formatted `.xlsx` Excel spreadsheets with tabs, columns, rows, and live Excel formulas (`=SUM(...)`, `=AVERAGE(...)`).
2. `create_document`: Create structured `.pdf` or `.docx` (Word) documents.
3. `build_interactive_app`: Build complete, self-contained HTML5/CSS/JS interactive mini-apps or calculators.
4. `generate_visual_media`: Create charts, visual graphics, illustrations, or animated motion clips.
5. `run_python_sandbox`: Run Python 3 code locally for calculations, data processing, or custom file creation.
6. `search_web`: Search the live internet via DuckDuckGo (only available when Web Search is enabled by the user).

Guidelines:
- For normal questions or conversation, simply reply naturally and clearly without calling any tools.
- Whenever the user asks you to make an Excel spreadsheet, a PDF or Word document, a chart, a picture, a video/animation, or an interactive app, call the matching tool so the real file is created for them.
"""

SYSTEM_PROMPT_CHAT = """You are Local AI Studio, a fast, private AI assistant running 100% on the user's computer. Provide clear, helpful, well-structured answers."""


async def execute_tool_call(
    func_name: str,
    args: Dict[str, Any],
    conversation_id: str,
    active_model: str,
    vram_handoff: bool,
    offline_mode: bool = True,
) -> Dict[str, Any]:
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
        elif func_name == "search_web":
            res = await tool_search_web(
                query=args.get("query", ""),
                offline_mode=offline_mode,
            )
        else:
            res = {"status": "error", "summary": f"Unknown tool: {func_name}"}
    except Exception as exc:
        res = {"status": "error", "summary": f"Tool execution error: {exc}"}

    res["duration_ms"] = int((time.time() - start_t) * 1000)
    return res


def detect_proactive_artifact_intent(user_prompt: str) -> Optional[Dict[str, Any]]:
    p_low = user_prompt.lower()
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
    offline_mode: bool = True,
) -> AsyncGenerator[Dict[str, Any], None]:
    await ensure_ollama_running()
    tuning = hw_profile.get("tuning", {})
    num_ctx = tuning.get("recommended_num_ctx", 8192)
    keep_alive = tuning.get("keep_alive", "10m")
    vram_handoff = tuning.get("vram_handoff_before_media", True)
    allow_web_search = not offline_mode

    sys_prompt = SYSTEM_PROMPT_AGENT if mode == "agent" else SYSTEM_PROMPT_CHAT
    ollama_messages = [{"role": "system", "content": sys_prompt}]
    # Full conversation history is passed regardless of which model generated earlier turns
    for m in history_messages[-16:]:
        if m["role"] in ("user", "assistant"):
            ollama_messages.append({"role": m["role"], "content": m["content"]})
    ollama_messages.append({"role": "user", "content": user_prompt})

    tool_traces: List[Dict[str, Any]] = []
    collected_artifacts: List[Dict[str, Any]] = []

    if mode == "agent":
        yield {"type": "status", "message": f"Thinking with {model}..."}
        try:
            active_schemas = get_tool_schemas(allow_web_search=allow_web_search)
            async with httpx.AsyncClient(timeout=120.0) as client:
                probe_resp = await client.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={
                        "model": model,
                        "messages": ollama_messages,
                        "tools": active_schemas,
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
                                offline_mode=offline_mode,
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
                            tool_payload = {
                                "status": exec_res.get("status"),
                                "summary": trace_entry["summary"],
                                "artifacts_created": [a["filename"] for a in new_arts],
                            }
                            if exec_res.get("results"):
                                tool_payload["web_results"] = exec_res["results"]
                            ollama_messages.append({
                                "role": "tool",
                                "content": json.dumps(tool_payload),
                            })
                    else:
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
                                offline_mode=offline_mode,
                            )
                            trace_entry["status"] = exec_res.get("status", "success")
                            trace_entry["duration_ms"] = exec_res.get("duration_ms", 0)
                            trace_entry["summary"] = exec_res.get("summary", "Generated visual media")
                            tool_traces.append(trace_entry)
                            if exec_res.get("artifact"):
                                collected_artifacts.append(exec_res["artifact"])
                                yield {"type": "tool_end", "tool": trace_entry, "artifacts": [exec_res["artifact"]]}

                        direct_content = msg_obj.get("content", "")
                        if direct_content and not tool_traces:
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
        except Exception:
            pass

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
