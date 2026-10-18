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
import shutil
import subprocess
import time
import openpyxl
import qrcode
import aiosqlite
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

from .agent import (
    OLLAMA_BASE,
    PENDING_TOOL_APPROVALS,
    ensure_ollama_running,
    execute_tool_call,
    flush_ollama_vram,
    list_installed_models,
    list_running_models,
    run_agent_stream,
)
from .database import (
    DB_PATH,
    add_message,
    create_conversation,
    create_workspace,
    delete_artifact,
    delete_conversation,
    delete_workspace,
    get_conversation,
    get_settings,
    get_workspace,
    init_db,
    list_artifacts,
    list_conversations,
    list_workspaces,
    register_artifact,
    truncate_conversation_from_message,
    update_conversation_context,
    update_conversation_model,
    update_conversation_title,
    update_settings,
    update_workspace,
)
from .hardware import build_hardware_profile
from .tools import (
    ARTIFACTS_DIR,
    WORKSPACE_DIR,
    confine_to_workspace,
    create_file_backup,
    extract_excel_preview,
    list_available_sd_models,
    resolve_safe_path,
    tool_revert_file_backup,
    SD_MODEL_DIR,
)

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
    workspace_id: Optional[str] = None


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
    permission_mode: Optional[str] = None
    tool_permissions: Optional[Dict[str, str]] = None
    external_path_policy: Optional[str] = None


class DirectToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    conversation_id: Optional[str] = None


class WorkspaceCreateRequest(BaseModel):
    name: str
    path: Optional[str] = None
    is_external: bool = False
    instructions: Optional[str] = ""


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    instructions: Optional[str] = None
    is_external: Optional[bool] = None


class ToolApprovalRequest(BaseModel):
    approval_id: str
    decision: str  # "allow_once", "always_allow", "deny"
    tool_name: Optional[str] = None
    feedback: Optional[str] = None


class TruncateConversationRequest(BaseModel):
    message_id: str


class FileSaveRequest(BaseModel):
    path: str
    content: str
    workspace_id: Optional[str] = None


class RevertBackupRequest(BaseModel):
    backup_path: str
    workspace_id: Optional[str] = None


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


async def _resolve_workspace_base(workspace_id: Optional[str] = None) -> Path:
    if workspace_id:
        ws = await get_workspace(workspace_id)
        if ws and ws.get("path"):
            try:
                p = Path(ws["path"]).resolve()
                if p.exists() and p.is_dir():
                    return p
            except Exception:
                pass
    return WORKSPACE_DIR.resolve()


@app.get("/api/workspaces")
async def api_get_workspaces():
    return {"workspaces": await list_workspaces()}


@app.post("/api/workspaces")
async def api_create_workspace(req: WorkspaceCreateRequest):
    ws = await create_workspace(
        name=req.name,
        path=req.path,
        is_external=req.is_external,
        instructions=req.instructions or "",
    )
    return ws


@app.post("/api/workspaces/pick-folder")
async def api_pick_workspace_folder():
    """
    Spawns the native Windows/OS folder picker dialog on the host PC so the user can
    select any folder on their computer with a single click.
    """
    if platform.system() == "Windows":
        try:
            ps_cmd = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.Description = 'Select project folder to link with Local AI Studio'; "
                "$f.ShowNewFolderButton = $true; "
                "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
            )
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, _ = await proc.communicate()
            selected = stdout_b.decode("utf-8", errors="ignore").strip()
            if selected and Path(selected).exists():
                p = Path(selected).resolve()
                return {"status": "selected", "path": str(p), "name": p.name}
            return {"status": "cancelled", "path": None}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return {"status": "unsupported", "path": None}


@app.patch("/api/workspaces/{workspace_id}")
async def api_update_workspace(workspace_id: str, req: WorkspaceUpdateRequest):
    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.path is not None:
        updates["path"] = req.path
    if req.instructions is not None:
        updates["instructions"] = req.instructions
    if req.is_external is not None:
        updates["is_external"] = req.is_external

    ws = await update_workspace(workspace_id, updates)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@app.delete("/api/workspaces/{workspace_id}")
async def api_delete_workspace(workspace_id: str, delete_files: bool = False):
    res = await delete_workspace(workspace_id, delete_files=delete_files)
    return res


@app.post("/api/chat/tool-approval")
async def api_chat_tool_approval(req: ToolApprovalRequest):
    approval = PENDING_TOOL_APPROVALS.get(req.approval_id)
    if not approval:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "message": "Approval request expired or not found"},
        )

    if req.decision == "always_allow" and req.tool_name:
        settings = await get_settings()
        perms = settings.get("tool_permissions", {})
        perms[req.tool_name] = "allow"
        await update_settings({"tool_permissions": perms})

    approval["decision"] = req.decision
    approval["feedback"] = req.feedback or ""
    approval["event"].set()
    return {"status": "acknowledged", "approval_id": req.approval_id, "decision": req.decision}


@app.post("/api/conversations/{conversation_id}/truncate")
async def api_truncate_conversation(conversation_id: str, req: TruncateConversationRequest):
    res = await truncate_conversation_from_message(conversation_id, req.message_id)
    return res


@app.put("/api/workspace/file-content")
async def api_save_workspace_file_content(req: FileSaveRequest):
    base_dir = await _resolve_workspace_base(req.workspace_id)
    try:
        target = resolve_safe_path(req.path, allow_outside_workspace=True, base_dir=base_dir)
        bak_path = None
        if target.exists() and target.is_file():
            bak_path = create_file_backup(target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        target.write_text(req.content, encoding="utf-8")
        return {
            "status": "success",
            "path": str(target),
            "filename": target.name,
            "backup_filename": bak_path.name if bak_path else None,
            "size_bytes": target.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/workspace/revert-backup")
async def api_revert_backup(req: RevertBackupRequest):
    base_dir = await _resolve_workspace_base(req.workspace_id)
    res = tool_revert_file_backup(req.backup_path, base_dir=base_dir)
    return res


@app.get("/api/conversations")
async def api_list_conversations():
    return {"conversations": await list_conversations()}


@app.post("/api/conversations")
async def api_create_conversation(payload: Dict[str, Any]):
    title = payload.get("title") or "New Chat"
    model = payload.get("model") or "llama3.2:3b"
    mode = payload.get("mode") or "chat"
    context = payload.get("context") or ""
    workspace_id = payload.get("workspace_id")
    await flush_ollama_vram()
    conv = await create_conversation(
        title=title,
        model=model,
        mode=mode,
        context=context,
        workspace_id=workspace_id,
    )
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
    effective_workspace_id = req.workspace_id

    if not conv_id:
        short_title = req.prompt.strip()[:46] or "New Chat"
        conv = await create_conversation(
            title=short_title,
            model=req.model,
            mode=req.mode,
            context=active_context,
            workspace_id=effective_workspace_id,
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
                workspace_id=effective_workspace_id,
            )
            conv_id = conv["id"]
            history_messages = []
        else:
            if not effective_workspace_id:
                effective_workspace_id = existing.get("workspace_id")
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
            permission_mode=settings.get("permission_mode", "ask"),
            tool_permissions=settings.get("tool_permissions"),
            external_path_policy=settings.get("external_path_policy", "ask"),
            workspace_id=effective_workspace_id,
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
        # Fallback check across uploads, workspace root, or any workspace folder
        candidate = None
        for p in [WORKSPACE_DIR / "uploads" / safe_name, WORKSPACE_DIR / safe_name]:
            if p.exists() and p.is_file():
                candidate = p
                break
        if not candidate and WORKSPACE_DIR.exists():
            for p in WORKSPACE_DIR.rglob(safe_name):
                if p.is_file():
                    candidate = p
                    break
        if candidate:
            filepath = candidate
        else:
            raise HTTPException(status_code=404, detail="Artifact file not found")

    if filepath.suffix.lower() in (".html", ".htm") and not download:
        return HTMLResponse(filepath.read_text(encoding="utf-8", errors="ignore"))

    disposition = "attachment" if download or filepath.suffix.lower() in (".xlsx", ".docx") else "inline"
    return FileResponse(
        filepath,
        filename=safe_name,
        content_disposition_type=disposition,
    )


@app.get("/api/workspace/raw-file")
async def api_serve_workspace_raw_file(path: str, workspace_id: Optional[str] = None, download: bool = False):
    """
    Directly streams any workspace file (image, PDF, spreadsheet, document, code)
    with accurate MIME types and Content-Disposition.
    """
    try:
        base_dir = await _resolve_workspace_base(workspace_id)
        safe_rel = path.replace("\\", "/").strip().lstrip("/")
        target = resolve_safe_path(safe_rel, allow_outside_workspace=True, base_dir=base_dir)
        if not target.exists() or not target.is_file():
            # Fallback: check in ARTIFACTS_DIR or search workspace
            safe_name = Path(safe_rel).name
            if (ARTIFACTS_DIR / safe_name).exists():
                target = ARTIFACTS_DIR / safe_name
            elif WORKSPACE_DIR.exists():
                for p in WORKSPACE_DIR.rglob(safe_name):
                    if p.is_file():
                        target = p
                        break
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        if target.suffix.lower() in (".html", ".htm") and not download:
            return HTMLResponse(target.read_text(encoding="utf-8", errors="ignore"))

        disposition = "attachment" if download or target.suffix.lower() in (".xlsx", ".docx") else "inline"
        return FileResponse(
            target,
            filename=target.name,
            content_disposition_type=disposition,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@app.post("/api/workspace/upload")
async def api_upload_workspace(
    files: List[UploadFile] = File(...),
    conversation_id: Optional[str] = Form(None),
    workspace_id: Optional[str] = Form(None),
):
    """
    Accepts one or more uploaded files or clipboard images, saves them to the workspace artifacts
    directory, registers them in the database, and returns metadata for chat attachment and preview.
    """
    uploaded = []
    base_dir = await _resolve_workspace_base(workspace_id)
    uploads_dir = base_dir / "uploads"
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
        if ext in (".xlsx", ".xlsm", ".xls", ".csv"):
            try:
                preview_data = extract_excel_preview(dest_path)
            except Exception:
                preview_data = {}

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
async def api_list_workspace_files(workspace_id: Optional[str] = None):
    """
    Returns all files across the user's workspace for the workspace explorer and multi-file projects.
    """
    base_dir = await _resolve_workspace_base(workspace_id)
    file_entries = []
    if base_dir.exists():
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
            for file in files:
                if file.startswith(".") or ".bak" in file:
                    continue
                full_p = Path(root) / file
                rel_p = full_p.relative_to(base_dir)
                stat = full_p.stat()
                ext = full_p.suffix.lower()
                cat = "document"
                if ext in (".xlsx", ".xls", ".csv"):
                    cat = "spreadsheet"
                elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    cat = "image"
                elif ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".sql", ".sh", ".md", ".txt"):
                    cat = "code"
                file_entries.append({
                    "name": file,
                    "relative_path": str(rel_p).replace("\\", "/"),
                    "category": cat,
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                })

    return {
        "workspace_root": str(base_dir.resolve()),
        "workspace_id": workspace_id,
        "files": sorted(file_entries, key=lambda x: x["modified_at"], reverse=True),
    }


@app.post("/api/workspace/open-folder")
async def api_open_workspace_folder(workspace_id: Optional[str] = None):
    """
    Opens the local workspace directory directly in the host OS File Explorer.
    """
    try:
        base_dir = await _resolve_workspace_base(workspace_id)
        ws_path = str(base_dir.resolve())
        if platform.system() == "Windows":
            os.startfile(ws_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", ws_path])
        else:
            subprocess.Popen(["xdg-open", ws_path])
        return {"status": "success", "path": ws_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/workspace/file-content")
async def api_get_workspace_file_content(path: str, workspace_id: Optional[str] = None):
    """
    Reads and returns the text, code, or media preview data of any workspace file.
    """
    try:
        base_dir = await _resolve_workspace_base(workspace_id)
        safe_rel = path.replace("\\", "/").strip().lstrip("/")
        target = resolve_safe_path(safe_rel, allow_outside_workspace=True, base_dir=base_dir)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        ext = target.suffix.lower()
        stat = target.stat()
        raw_url = f"/api/workspace/raw-file?path={safe_rel}"
        if workspace_id:
            raw_url += f"&workspace_id={workspace_id}"

        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg"):
            return {
                "type": "image",
                "name": target.name,
                "relative_path": safe_rel,
                "url": raw_url,
                "size_bytes": stat.st_size,
            }
        elif ext in (".xlsx", ".xls", ".csv"):
            preview_data = extract_excel_preview(target)
            return {
                "type": "spreadsheet",
                "name": target.name,
                "relative_path": safe_rel,
                "url": raw_url,
                "size_bytes": stat.st_size,
                "preview_data": preview_data,
            }
        elif ext in (".pdf", ".docx"):
            return {
                "type": "document",
                "name": target.name,
                "relative_path": safe_rel,
                "url": raw_url,
                "size_bytes": stat.st_size,
            }
        elif ext in (".html", ".htm"):
            return {
                "type": "webapp",
                "name": target.name,
                "relative_path": safe_rel,
                "url": raw_url,
                "size_bytes": stat.st_size,
                "content": target.read_text(encoding="utf-8", errors="ignore"),
            }

        # Text / code file reading
        max_bytes = 2 * 1024 * 1024
        raw_text = target.read_text(encoding="utf-8", errors="ignore")
        if len(raw_text) > max_bytes:
            content = raw_text[:50000] + "\n\n... [Content truncated: file exceeds 2MB] ..."
        else:
            content = raw_text

        return {
            "type": "code",
            "name": target.name,
            "relative_path": safe_rel,
            "extension": ext.lstrip("."),
            "size_bytes": stat.st_size,
            "content": content,
            "url": raw_url,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/workspace/file")
async def api_delete_workspace_file(path: str, workspace_id: Optional[str] = None):
    """
    Physically deletes any file in the workspace directory and purges any corresponding
    artifact entries from SQLite.
    """
    try:
        base_dir = await _resolve_workspace_base(workspace_id)
        safe_rel = path.replace("\\", "/").strip().lstrip("/")
        target = resolve_safe_path(safe_rel, allow_outside_workspace=True, base_dir=base_dir)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")

        safe_name = target.name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
            (ARTIFACTS_DIR / safe_name).unlink(missing_ok=True)
            (base_dir / "uploads" / safe_name).unlink(missing_ok=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM artifacts WHERE filename = ?", (safe_name,))
            await db.commit()

        return {"status": "success", "path": safe_rel}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



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
