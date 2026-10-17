"""
Local AI Studio — FastAPI Server & Unified LAN Gateway.

Binds to 0.0.0.0:8000 for seamless access across:
- Desktop PC: http://localhost:8000
- Mobile Phone on Home Wi-Fi: http://<LAN_IP>:8000

Enforces Strict Local Privacy / Air-Gap middleware ensuring only localhost and private LAN
subnets can connect, and zero external telemetry ever leaves the machine.
"""

from __future__ import annotations

import asyncio
import base64
import io
import ipaddress
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import platform
import subprocess
import time
import openpyxl
import qrcode
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

from .agent import (
    OLLAMA_BASE,
    ensure_ollama_running,
    execute_tool_call,
    flush_ollama_vram,
    list_installed_models,
    list_running_models,
    run_agent_stream,
)
from .database import (
    add_message,
    create_conversation,
    delete_artifact,
    delete_conversation,
    get_conversation,
    get_settings,
    init_db,
    list_artifacts,
    list_conversations,
    register_artifact,
    update_conversation_context,
    update_conversation_model,
    update_conversation_title,
    update_settings,
)
from .hardware import build_hardware_profile
from .tools import ARTIFACTS_DIR, WORKSPACE_DIR, list_available_sd_models, SD_MODEL_DIR

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def _generate_qr_data_uri(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#F3F4F6", back_color="#111317")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _is_private_or_local_ip(host: str) -> bool:
    if host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await ensure_ollama_running()
    yield


app = FastAPI(
    title="Local AI Studio",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def lan_and_privacy_guard(request: Request, call_next):
    client_host = request.client.host if request.client else "127.0.0.1"
    if not _is_private_or_local_ip(client_host):
        return JSONResponse(
            status_code=403,
            content={"detail": "Blocked by Local AI Studio Privacy Guard: Only LAN/localhost allowed."},
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Privacy-Policy"] = "100%-Local-Zero-Telemetry"
    return response


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    prompt: str
    model: str = "llama3.2:3b"
    mode: str = "chat"
    context: Optional[str] = None
    image_style: Optional[str] = "auto"
    attached_files: Optional[List[Dict[str, Any]]] = None


class ContextUpdateRequest(BaseModel):
    context: str


class PullModelRequest(BaseModel):
    model: str


class UnloadModelRequest(BaseModel):
    model: str


class FlushVramRequest(BaseModel):
    except_model: Optional[str] = None


class DeleteModelRequest(BaseModel):
    name: str
    model_type: str = "llm"  # "llm" or "image"


class DownloadImageModelRequest(BaseModel):
    url: str
    filename: str


class SettingsUpdateRequest(BaseModel):
    air_gap_mode: Optional[bool] = None
    hardware_profile_override: Optional[str] = None
    default_model: Optional[str] = None
    agent_mode: Optional[str] = None
    auto_vram_handoff: Optional[bool] = None
    gaming_mode: Optional[bool] = None
    brave_search_api_key: Optional[str] = None


class DirectToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    conversation_id: Optional[str] = None


@app.get("/api/system/status")
async def api_system_status(request: Request):
    await init_db()
    settings = await get_settings()
    hw = build_hardware_profile(override_profile=settings.get("hardware_profile_override", "auto"))
    installed = await list_installed_models()
    running = await list_running_models()

    port = request.url.port or 8000
    lan_url = f"http://{hw['lan_ip']}:{port}"
    qr_data_uri = _generate_qr_data_uri(lan_url)
    sd_models = list_available_sd_models()

    return {
        "hardware": hw,
        "installed_models": installed,
        "running_models": running,
        "image_models": [
            {
                "filename": m["filename"],
                "style": m["style"],
                "label": m["label"],
                "size_gb": m["size_gb"],
            }
            for m in sd_models.values()
        ],
        "settings": settings,
        "network": {
            "lan_ip": hw["lan_ip"],
            "port": port,
            "lan_url": lan_url,
            "local_url": f"http://localhost:{port}",
            "qr_code": qr_data_uri,
        },
    }


@app.get("/api/settings")
async def api_get_settings():
    return await get_settings()


@app.post("/api/settings")
async def api_update_settings(req: SettingsUpdateRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    new_settings = await update_settings(updates)
    hw = build_hardware_profile(override_profile=new_settings.get("hardware_profile_override", "auto"))
    return {"settings": new_settings, "hardware": hw}


@app.post("/api/models/pull")
async def api_pull_model(req: PullModelRequest):
    await ensure_ollama_running()

    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_BASE}/api/pull",
                    json={"name": req.model, "stream": True},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            total = data.get("total", 0)
                            completed = data.get("completed", 0)
                            pct = round((completed / total) * 100, 1) if total else 0
                            payload = {
                                "status": data.get("status", "downloading"),
                                "completed": completed,
                                "total": total,
                                "percent": pct,
                            }
                            yield f"data: {json.dumps(payload)}\n\n"
                        except Exception:
                            continue
            yield f"data: {json.dumps({'status': 'success', 'percent': 100})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/models/unload")
async def api_unload_model(req: UnloadModelRequest):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{OLLAMA_BASE}/api/generate",
                json={"model": req.model, "keep_alive": 0},
            )
        return {"status": "unloaded", "model": req.model}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.post("/api/models/delete")
async def api_delete_model(req: DeleteModelRequest):
    if req.model_type == "image":
        clean_name = Path(req.name).name
        target = SD_MODEL_DIR / clean_name
        if target.exists() and target.is_file():
            target.unlink()
            return {"status": "deleted", "name": req.name, "type": "image"}
        return JSONResponse(status_code=404, content={"status": "error", "detail": "Image model file not found"})
    else:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.request(
                    "DELETE",
                    f"{OLLAMA_BASE}/api/delete",
                    json={"name": req.name},
                )
                if r.status_code == 200:
                    return {"status": "deleted", "name": req.name, "type": "llm"}
                return JSONResponse(status_code=r.status_code, content={"status": "error", "detail": r.text})
        except Exception as exc:
            return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@app.post("/api/models/image/download")
async def api_download_image_model(req: DownloadImageModelRequest):
    raw_filename = Path(req.filename).name.strip()
    if not raw_filename or raw_filename.lower() in ("model.safetensors", "custom_model.safetensors"):
        clean_url_stem = req.url.split("?")[0].rstrip("/").split("/")[-1]
        if clean_url_stem and ("." in clean_url_stem or len(clean_url_stem) > 4):
            raw_filename = clean_url_stem
    if not raw_filename:
        raw_filename = "downloaded_model.safetensors"
    if not raw_filename.endswith((".safetensors", ".gguf", ".ckpt")):
        raw_filename += ".safetensors"

    target_file = SD_MODEL_DIR / raw_filename
    part_file = SD_MODEL_DIR / f"{raw_filename}.part"

    async def event_generator():
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
                async with client.stream("GET", req.url.strip(), headers=headers) as resp:
                    if resp.status_code >= 400:
                        yield f"data: {json.dumps({'status': 'error', 'error': f'Download failed: HTTP {resp.status_code}'})}\n\n"
                        return

                    total_bytes = int(resp.headers.get("content-length") or 0)
                    downloaded = 0
                    last_pct = 0.0

                    with open(part_file, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            f.write(chunk)
                            downloaded += len(chunk)
                            pct = round((downloaded / total_bytes) * 100, 1) if total_bytes else 0
                            if pct - last_pct >= 0.5 or pct >= 100.0:
                                last_pct = pct
                                yield f"data: {json.dumps({'status': 'downloading', 'completed': downloaded, 'total': total_bytes, 'percent': pct})}\n\n"

            if part_file.exists():
                part_file.replace(target_file)
            yield f"data: {json.dumps({'status': 'success', 'percent': 100, 'filename': raw_filename})}\n\n"
        except Exception as exc:
            if part_file.exists():
                try:
                    part_file.unlink()
                except Exception:
                    pass
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/models/flush")
async def api_flush_vram(req: FlushVramRequest = FlushVramRequest()):
    unloaded = await flush_ollama_vram(except_model=req.except_model)
    settings = await get_settings()
    hw = build_hardware_profile(override_profile=settings.get("hardware_profile_override", "auto"))
    running = await list_running_models()
    return {
        "status": "flushed",
        "unloaded_models": unloaded,
        "hardware": hw,
        "running_models": running,
    }


@app.post("/api/system/sleep")
async def api_system_sleep():
    """
    Enter Sleep Mode: evict 100% of LLM and Diffusion models from GPU VRAM.
    Returns VRAM consumption to 0 MB until the next user prompt is sent.
    """
    unloaded = await flush_ollama_vram()
    settings = await get_settings()
    hw = build_hardware_profile(override_profile=settings.get("hardware_profile_override", "auto"))
    return {
        "status": "sleeping",
        "unloaded_models": unloaded,
        "message": "All models evicted from GPU VRAM. Studio is in sleep mode (0 MB VRAM). Send any prompt to wake up automatically.",
        "hardware": hw,
        "running_models": [],
    }


@app.post("/api/system/shutdown")
async def api_system_shutdown():
    """
    Gracefully terminate the backend server process and release all system handles.
    """
    await flush_ollama_vram()

    async def _delayed_kill():
        await asyncio.sleep(0.5)
        os._exit(0)

    asyncio.create_task(_delayed_kill())
    return {
        "status": "shutting_down",
        "message": "Local AI Studio backend process is stopping cleanly. You can safely close this window.",
    }


@app.get("/api/conversations")
async def api_list_conversations():
    return {"conversations": await list_conversations()}


@app.post("/api/conversations")
async def api_create_conversation(payload: Dict[str, Any]):
    title = payload.get("title") or "New Chat"
    model = payload.get("model") or "llama3.2:3b"
    mode = payload.get("mode") or "chat"
    context = payload.get("context") or ""
    await flush_ollama_vram()
    conv = await create_conversation(title=title, model=model, mode=mode, context=context)
    return conv


@app.get("/api/conversations/{conversation_id}")
async def api_get_conversation(conversation_id: str):
    conv = await get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.patch("/api/conversations/{conversation_id}/context")
async def api_update_conversation_context(conversation_id: str, req: ContextUpdateRequest):
    await update_conversation_context(conversation_id, req.context)
    return {"status": "updated", "context": req.context}


@app.delete("/api/conversations/{conversation_id}")
async def api_delete_conversation(conversation_id: str):
    await flush_ollama_vram()
    res = await delete_conversation(conversation_id)
    return res


@app.delete("/api/artifacts/{artifact_id}")
async def api_delete_artifact(artifact_id: str):
    return await delete_artifact(artifact_id)


@app.post("/api/chat/stream")
async def api_chat_stream(req: ChatRequest, request: Request):
    settings = await get_settings()
    hw = build_hardware_profile(override_profile=settings.get("hardware_profile_override", "auto"))

    conv_id = req.conversation_id
    active_context = req.context or ""

    if not conv_id:
        short_title = req.prompt.strip()[:46] or "New Chat"
        conv = await create_conversation(
            title=short_title,
            model=req.model,
            mode=req.mode,
            context=active_context,
        )
        conv_id = conv["id"]
        history_messages = []
    else:
        existing = await get_conversation(conv_id)
        if not existing:
            short_title = req.prompt.strip()[:46] or "New Chat"
            conv = await create_conversation(
                title=short_title,
                model=req.model,
                mode=req.mode,
                context=active_context,
            )
            conv_id = conv["id"]
            history_messages = []
        else:
            history_messages = existing.get("messages", [])
            saved_ctx = existing.get("context", "")
            # Preserve background context: never overwrite with blank text
            if req.context and req.context.strip():
                if req.context.strip() != saved_ctx.strip():
                    await update_conversation_context(conv_id, req.context.strip())
                active_context = req.context.strip()
            else:
                active_context = saved_ctx

            # Update conversation active model if it changed and not in pure image mode
            if req.model and not req.model.startswith("sd:") and req.model != existing.get("model"):
                await update_conversation_model(conv_id, req.model)

            if len(history_messages) == 0 and existing.get("title") in ("New Studio Session", "Studio Session", "New Chat"):
                await update_conversation_title(conv_id, req.prompt.strip()[:46])

    user_msg = await add_message(
        conversation_id=conv_id,
        role="user",
        content=req.prompt,
        model=req.model,
    )

    async def sse_generator():
        yield f"data: {json.dumps({'type': 'session', 'conversation_id': conv_id, 'user_message': user_msg, 'context': active_context})}\n\n"
        async for ev in run_agent_stream(
            conversation_id=conv_id,
            history_messages=history_messages,
            user_prompt=req.prompt,
            model=req.model,
            mode=req.mode,
            hw_profile=hw,
            offline_mode=settings.get("air_gap_mode", True),
            chat_context=active_context,
            gaming_mode=settings.get("gaming_mode", False),
            image_style=req.image_style or "auto",
            brave_api_key=settings.get("brave_search_api_key", ""),
            attached_files=req.attached_files,
        ):
            if await request.is_disconnected():
                await flush_ollama_vram()
                break
            if ev["type"] == "done":
                saved_msg = await add_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=ev.get("content", ""),
                    thinking=ev.get("thinking", ""),
                    tool_calls=ev.get("tool_calls", []),
                    artifacts=ev.get("artifacts", []),
                    model=req.model,
                    tokens_per_sec=ev.get("tokens_per_sec", 0.0),
                )
                yield f"data: {json.dumps({'type': 'done', 'message': saved_msg, 'conversation_id': conv_id})}\n\n"
            else:
                yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.post("/api/chat/stop")
async def api_chat_stop():
    """
    Immediately stop ongoing generation and release any blocked Ollama inference locks.
    """
    await flush_ollama_vram()
    return {"status": "stopped"}


@app.post("/api/tools/execute")
async def api_direct_tool_execute(req: DirectToolRequest):
    settings = await get_settings()
    res = await execute_tool_call(
        func_name=req.tool_name,
        args=req.arguments,
        conversation_id=req.conversation_id or "",
        active_model=settings.get("default_model", ""),
        vram_handoff=settings.get("auto_vram_handoff", True),
        offline_mode=settings.get("air_gap_mode", True),
        brave_api_key=settings.get("brave_search_api_key", ""),
    )
    return res


@app.get("/api/artifacts")
async def api_list_artifacts():
    return {"artifacts": await list_artifacts()}


@app.get("/api/artifacts/file/{filename}")
async def api_serve_artifact_file(filename: str, download: bool = False):
    safe_name = Path(filename).name
    filepath = ARTIFACTS_DIR / safe_name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")

    if filepath.suffix.lower() in (".html", ".htm") and not download:
        return HTMLResponse(filepath.read_text(encoding="utf-8", errors="ignore"))

    disposition = "attachment" if download or filepath.suffix.lower() in (".xlsx", ".docx") else "inline"
    return FileResponse(
        filepath,
        filename=safe_name,
        content_disposition_type=disposition,
    )


@app.post("/api/workspace/upload")
async def api_upload_workspace(
    files: List[UploadFile] = File(...),
    conversation_id: Optional[str] = Form(None),
):
    """
    Accepts one or more uploaded files or clipboard images, saves them to the workspace artifacts
    directory, registers them in the database, and returns metadata for chat attachment and preview.
    """
    uploaded = []
    uploads_dir = WORKSPACE_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    for f in files:
        raw_name = Path(f.filename or "uploaded_file").name
        ext = Path(raw_name).suffix.lower()
        stem = Path(raw_name).stem.replace(" ", "_")
        safe_name = f"{stem}_{int(time.time() * 1000)}{ext}" if (ARTIFACTS_DIR / raw_name).exists() else raw_name

        dest_path = ARTIFACTS_DIR / safe_name
        content_bytes = await f.read()
        dest_path.write_bytes(content_bytes)

        # Also store copy in workspace/uploads/ for direct file discovery
        (uploads_dir / safe_name).write_bytes(content_bytes)

        # Determine category & mime_type
        category = "document"
        mime = f.content_type or "application/octet-stream"
        if ext in (".xlsx", ".xls", ".csv"):
            category = "spreadsheet"
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
            category = "image"
        elif ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".sql", ".sh"):
            category = "code"
        elif ext in (".zip", ".tar", ".gz", ".7z"):
            category = "archive"

        preview_data = {}
        if ext in (".xlsx", ".xlsm"):
            try:
                wb = openpyxl.load_workbook(dest_path, read_only=True)
                preview_data["sheets"] = wb.sheetnames
                wb.close()
            except Exception:
                pass

        art = await register_artifact(
            title=raw_name,
            filename=safe_name,
            category=category,
            mime_type=mime,
            size_bytes=len(content_bytes),
            preview_data=preview_data,
            conversation_id=conversation_id,
        )
        uploaded.append({
            **art,
            "path": f"workspace/artifacts/{safe_name}",
            "url": f"/api/artifacts/file/{safe_name}",
        })

    return {"status": "success", "files": uploaded}


@app.get("/api/workspace/files")
async def api_list_workspace_files():
    """
    Returns all files across the user's workspace for the workspace explorer and multi-file projects.
    """
    file_entries = []
    if WORKSPACE_DIR.exists():
        for root, dirs, files in os.walk(WORKSPACE_DIR):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
            for file in files:
                if file.startswith(".") or ".bak" in file:
                    continue
                full_p = Path(root) / file
                rel_p = full_p.relative_to(WORKSPACE_DIR)
                stat = full_p.stat()
                ext = full_p.suffix.lower()
                cat = "document"
                if ext in (".xlsx", ".xls", ".csv"):
                    cat = "spreadsheet"
                elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    cat = "image"
                elif ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json"):
                    cat = "code"
                file_entries.append({
                    "name": file,
                    "relative_path": str(rel_p).replace("\\", "/"),
                    "category": cat,
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                })

    return {
        "workspace_root": str(WORKSPACE_DIR.resolve()),
        "files": sorted(file_entries, key=lambda x: x["modified_at"], reverse=True),
    }


@app.post("/api/workspace/open-folder")
async def api_open_workspace_folder():
    """
    Opens the local workspace directory directly in the host OS File Explorer.
    """
    try:
        ws_path = str(WORKSPACE_DIR.resolve())
        if platform.system() == "Windows":
            os.startfile(ws_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", ws_path])
        else:
            subprocess.Popen(["xdg-open", ws_path])
        return {"status": "success", "path": ws_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}



if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        "<html><body style='background:#0B0C0E;color:#F3F4F6;font-family:sans-serif;padding:3rem'>"
        "<h2>Local AI Studio Backend Active</h2><p>Building frontend assets...</p></body></html>"
    )
