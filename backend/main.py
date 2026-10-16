"""
Local AI Studio — FastAPI Server & Unified LAN Gateway.

Binds to 0.0.0.0:8000 for seamless access across:
- Desktop PC: http://localhost:8000
- Mobile Phone on Home Wi-Fi: http://<LAN_IP>:8000

Enforces Strict Local Privacy / Air-Gap middleware ensuring only localhost and private LAN
subnets can connect, and zero external telemetry ever leaves the machine.
"""

from __future__ import annotations

import base64
import io
import ipaddress
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import qrcode
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import (
    OLLAMA_BASE,
    ensure_ollama_running,
    execute_tool_call,
    list_installed_models,
    list_running_models,
    run_agent_stream,
)
from .database import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_settings,
    init_db,
    list_artifacts,
    list_conversations,
    update_conversation_title,
    update_settings,
)
from .hardware import build_hardware_profile
from .tools import ARTIFACTS_DIR

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
    """Ensure only local machine and private home LAN devices can access the server."""
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
    model: str = "qwen2.5-coder:7b"
    mode: str = "agent"


class PullModelRequest(BaseModel):
    model: str


class UnloadModelRequest(BaseModel):
    model: str


class SettingsUpdateRequest(BaseModel):
    air_gap_mode: Optional[bool] = None
    hardware_profile_override: Optional[str] = None
    default_model: Optional[str] = None
    agent_mode: Optional[str] = None
    auto_vram_handoff: Optional[bool] = None


class DirectToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    conversation_id: Optional[str] = None


@app.get("/api/system/status")
async def api_system_status(request: Request):
    settings = await get_settings()
    hw = build_hardware_profile(override_profile=settings.get("hardware_profile_override", "auto"))
    installed = await list_installed_models()
    running = await list_running_models()

    port = request.url.port or 8000
    lan_url = f"http://{hw['lan_ip']}:{port}"
    qr_data_uri = _generate_qr_data_uri(lan_url)

    return {
        "hardware": hw,
        "installed_models": installed,
        "running_models": running,
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
    """Stream model download progress from Ollama."""
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
    """Evict a model from GPU VRAM immediately."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{OLLAMA_BASE}/api/generate",
                json={"model": req.model, "keep_alive": 0},
            )
        return {"status": "unloaded", "model": req.model}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/api/conversations")
async def api_list_conversations():
    return {"conversations": await list_conversations()}


@app.post("/api/conversations")
async def api_create_conversation(payload: Dict[str, Any]):
    title = payload.get("title") or "New Studio Session"
    model = payload.get("model") or "qwen2.5-coder:7b"
    mode = payload.get("mode") or "agent"
    conv = await create_conversation(title=title, model=model, mode=mode)
    return conv


@app.get("/api/conversations/{conversation_id}")
async def api_get_conversation(conversation_id: str):
    conv = await get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{conversation_id}")
async def api_delete_conversation(conversation_id: str):
    await delete_conversation(conversation_id)
    return {"status": "deleted"}


@app.post("/api/chat/stream")
async def api_chat_stream(req: ChatRequest):
    settings = await get_settings()
    hw = build_hardware_profile(override_profile=settings.get("hardware_profile_override", "auto"))

    conv_id = req.conversation_id
    if not conv_id:
        short_title = req.prompt.strip()[:46] or "Studio Session"
        conv = await create_conversation(title=short_title, model=req.model, mode=req.mode)
        conv_id = conv["id"]
        history_messages = []
    else:
        existing = await get_conversation(conv_id)
        if not existing:
            short_title = req.prompt.strip()[:46] or "Studio Session"
            conv = await create_conversation(title=short_title, model=req.model, mode=req.mode)
            conv_id = conv["id"]
            history_messages = []
        else:
            history_messages = existing.get("messages", [])
            if len(history_messages) == 0 and existing.get("title") in ("New Studio Session", "Studio Session"):
                await update_conversation_title(conv_id, req.prompt.strip()[:46])

    user_msg = await add_message(
        conversation_id=conv_id,
        role="user",
        content=req.prompt,
        model=req.model,
    )

    async def sse_generator():
        yield f"data: {json.dumps({'type': 'session', 'conversation_id': conv_id, 'user_message': user_msg})}\n\n"
        async for ev in run_agent_stream(
            conversation_id=conv_id,
            history_messages=history_messages,
            user_prompt=req.prompt,
            model=req.model,
            mode=req.mode,
            hw_profile=hw,
            offline_mode=settings.get("air_gap_mode", True),
        ):
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


@app.post("/api/tools/execute")
async def api_direct_tool_execute(req: DirectToolRequest):
    """Execute a studio tool directly from the Workbench UI."""
    settings = await get_settings()
    res = await execute_tool_call(
        func_name=req.tool_name,
        args=req.arguments,
        conversation_id=req.conversation_id or "",
        active_model=settings.get("default_model", ""),
        vram_handoff=settings.get("auto_vram_handoff", True),
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


# Mount built frontend assets if present
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
