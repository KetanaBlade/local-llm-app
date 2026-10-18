"""
Local SQLite Database Layer (100% On-Device Data Residency & Secure Obliteration).

Stores:
- Conversations (including per-chat `context` background instructions)
- Streaming message history
- Generated Artifacts
- Privacy & Hardware Settings

Deletion Policy:
- `delete_conversation` enables `PRAGMA secure_delete = ON`, deletes all messages,
  physically unlinks/deletes all associated artifact files from disk, removes artifact
  records, deletes the conversation record, and runs `VACUUM` to purge unallocated pages.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "local_ai_studio.db"
WORKSPACE_DIR = ROOT_DIR / "workspace"
ARTIFACTS_DIR = WORKSPACE_DIR / "artifacts"
PROJECTS_DIR = WORKSPACE_DIR / "projects"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TOOL_PERMISSIONS: Dict[str, str] = {
    "read_file": "allow",
    "list_directory": "allow",
    "search_web": "allow",
    "edit_file_content": "ask",
    "execute_python": "ask",
    "run_shell_command": "ask",
    "create_excel_spreadsheet": "ask",
    "create_document": "ask",
    "build_interactive_app": "ask",
    "generate_visual_media": "ask",
}


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("PRAGMA busy_timeout = 5000")
        await db.execute("PRAGMA secure_delete = ON")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                is_external INTEGER NOT NULL DEFAULT 0,
                instructions TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'chat',
                context TEXT NOT NULL DEFAULT '',
                workspace_id TEXT DEFAULT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        # Ensure `context` and `workspace_id` columns exist on older databases
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN context TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN workspace_id TEXT DEFAULT NULL")
        except Exception:
            pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                thinking TEXT DEFAULT '',
                tool_calls TEXT DEFAULT '[]',
                artifacts TEXT DEFAULT '[]',
                model TEXT DEFAULT '',
                tokens_per_sec REAL DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                workspace_id TEXT DEFAULT NULL,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                category TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                preview_data TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            )
            """
        )
        try:
            await db.execute("ALTER TABLE artifacts ADD COLUMN workspace_id TEXT DEFAULT NULL")
        except Exception:
            pass

        defaults = {
            "air_gap_mode": "true",
            "hardware_profile_override": "auto",
            "default_model": "qwen2.5-coder:7b",
            "agent_mode": "antigravity",
            "auto_vram_handoff": "true",
            "gaming_mode": "false",
            "brave_search_api_key": "",
            "permission_mode": "ask",
            "tool_permissions": json.dumps(DEFAULT_TOOL_PERMISSIONS),
            "external_path_policy": "ask",
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v),
            )
        await db.commit()


async def get_settings() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        raw = {r["key"]: r["value"] for r in rows}
        raw_perms = raw.get("tool_permissions")
        try:
            parsed_perms = json.loads(raw_perms) if raw_perms else DEFAULT_TOOL_PERMISSIONS
        except Exception:
            parsed_perms = DEFAULT_TOOL_PERMISSIONS

        return {
            "air_gap_mode": raw.get("air_gap_mode", "true") == "true",
            "hardware_profile_override": raw.get("hardware_profile_override", "auto"),
            "default_model": raw.get("default_model", "qwen2.5-coder:7b"),
            "agent_mode": raw.get("agent_mode", "antigravity"),
            "auto_vram_handoff": raw.get("auto_vram_handoff", "true") == "true",
            "gaming_mode": raw.get("gaming_mode", "false") == "true",
            "brave_search_api_key": raw.get("brave_search_api_key", ""),
            "permission_mode": raw.get("permission_mode", "ask"),
            "tool_permissions": parsed_perms,
            "external_path_policy": raw.get("external_path_policy", "ask"),
        }


async def update_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        for k, v in updates.items():
            if k == "tool_permissions" and isinstance(v, dict):
                val_str = json.dumps(v)
            else:
                val_str = "true" if v is True else ("false" if v is False else str(v))
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (k, val_str),
            )
        await db.commit()
    return await get_settings()


def _slugify_workspace_name(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower()).strip("_")
    return s[:40] or f"project_{int(time.time())}"


async def create_workspace(
    name: str,
    path: Optional[str] = None,
    is_external: bool = False,
    instructions: str = "",
) -> Dict[str, Any]:
    wid = str(uuid.uuid4())
    now = time.time()
    clean_name = name.strip() or "Untitled Workspace"

    if path and path.strip():
        resolved_path = str(Path(path.strip()).resolve())
        is_ext = 1 if is_external else 0
    else:
        slug = _slugify_workspace_name(clean_name)
        folder = PROJECTS_DIR / slug
        folder.mkdir(parents=True, exist_ok=True)
        resolved_path = str(folder.resolve())
        is_ext = 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO workspaces (id, name, path, is_external, instructions, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (wid, clean_name, resolved_path, is_ext, instructions.strip(), now, now),
        )
        await db.commit()

    return {
        "id": wid,
        "name": clean_name,
        "path": resolved_path,
        "is_external": bool(is_ext),
        "instructions": instructions.strip(),
        "created_at": now,
        "updated_at": now,
    }


async def list_workspaces() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT w.id, w.name, w.path, w.is_external, w.instructions, w.created_at, w.updated_at,
                   COUNT(c.id) as conversation_count
            FROM workspaces w
            LEFT JOIN conversations c ON w.id = c.workspace_id
            GROUP BY w.id
            ORDER BY w.updated_at DESC
            """
        )
        rows = await cursor.fetchall()
        workspaces = []
        for r in rows:
            d = dict(r)
            d["is_external"] = bool(d["is_external"])
            workspaces.append(d)
        return workspaces


async def get_workspace(workspace_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, path, is_external, instructions, created_at, updated_at FROM workspaces WHERE id = ?",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["is_external"] = bool(d["is_external"])
        return d


async def update_workspace(workspace_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ws = await get_workspace(workspace_id)
    if not ws:
        return None
    now = time.time()
    name = updates.get("name", ws["name"])
    path = updates.get("path", ws["path"])
    instructions = updates.get("instructions", ws["instructions"])
    is_external = 1 if updates.get("is_external", ws["is_external"]) else 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE workspaces
            SET name = ?, path = ?, is_external = ?, instructions = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, path, is_external, instructions, now, workspace_id),
        )
        await db.commit()
    return await get_workspace(workspace_id)


async def delete_workspace(workspace_id: str, delete_files: bool = False) -> Dict[str, Any]:
    ws = await get_workspace(workspace_id)
    if not ws:
        return {"status": "not_found", "id": workspace_id}

    if delete_files and not ws["is_external"]:
        p = Path(ws["path"])
        if PROJECTS_DIR.resolve() in p.resolve().parents and p.exists() and p.is_dir():
            try:
                import shutil
                shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET workspace_id = NULL WHERE workspace_id = ?",
            (workspace_id,),
        )
        await db.execute(
            "UPDATE artifacts SET workspace_id = NULL WHERE workspace_id = ?",
            (workspace_id,),
        )
        await db.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
        await db.commit()

    return {"status": "deleted", "id": workspace_id}


async def create_conversation(
    title: str,
    model: str,
    mode: str = "chat",
    context: str = "",
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    cid = str(uuid.uuid4())
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id, title, model, mode, context, workspace_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, title, model, mode, context, workspace_id, now, now),
        )
        await db.commit()
    return {
        "id": cid,
        "title": title,
        "model": model,
        "mode": mode,
        "context": context,
        "workspace_id": workspace_id,
        "created_at": now,
        "updated_at": now,
    }


async def update_conversation_context(conversation_id: str, context: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET context = ?, updated_at = ? WHERE id = ?",
            (context, time.time(), conversation_id),
        )
        await db.commit()


async def update_conversation_model(conversation_id: str, model: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET model = ?, updated_at = ? WHERE id = ?",
            (model, time.time(), conversation_id),
        )
        await db.commit()


async def list_conversations() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, model, mode, context, workspace_id, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, model, mode, context, workspace_id, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        conv = await cursor.fetchone()
        if not conv:
            return None
        msg_cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        msg_rows = await msg_cursor.fetchall()

        # Cross-reference active artifacts that exist both in DB and on disk
        art_cursor = await db.execute(
            "SELECT id, filename FROM artifacts WHERE conversation_id = ?",
            (conversation_id,),
        )
        art_rows = await art_cursor.fetchall()
        active_art_ids = {r["id"] for r in art_rows}
        active_filenames = {r["filename"] for r in art_rows if r["filename"]}

        messages = []
        for r in msg_rows:
            d = dict(r)
            d["tool_calls"] = json.loads(d.get("tool_calls") or "[]")
            raw_arts = json.loads(d.get("artifacts") or "[]")
            # Only retain artifacts that are still in the database AND exist on disk
            valid_arts = []
            for a in raw_arts:
                if isinstance(a, dict):
                    aid = a.get("id")
                    fname = a.get("filename")
                    fpath = ARTIFACTS_DIR / Path(fname).name if fname else None
                    if (aid in active_art_ids or fname in active_filenames) and fpath and fpath.exists():
                        valid_arts.append(a)
            d["artifacts"] = valid_arts
            messages.append(d)
        res = dict(conv)
        res["messages"] = messages
        return res


async def truncate_conversation_from_message(conversation_id: str, message_id: str) -> Dict[str, Any]:
    """
    Truncates conversation messages starting from `message_id` onward.
    Allows user prompt editing/resubmission and assistant regeneration.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, created_at FROM messages WHERE id = ? AND conversation_id = ?",
            (message_id, conversation_id),
        )
        row = await cursor.fetchone()
        if not row:
            return {"status": "not_found", "message_id": message_id}

        target_time = row["created_at"]
        del_cursor = await db.execute(
            "SELECT id FROM messages WHERE conversation_id = ? AND created_at >= ?",
            (conversation_id, target_time),
        )
        del_rows = await del_cursor.fetchall()
        del_ids = [r["id"] for r in del_rows]

        await db.execute(
            "DELETE FROM messages WHERE conversation_id = ? AND created_at >= ?",
            (conversation_id, target_time),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (time.time(), conversation_id),
        )
        await db.commit()
    return {"status": "truncated", "deleted_message_ids": del_ids, "conversation_id": conversation_id}


async def delete_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Totally obliterate a conversation, all its messages, all associated artifact rows,
    and physically overwrite & delete any files created during that conversation from disk,
    followed by SQLite secure_delete + VACUUM so zero residual bytes remain.
    """
    deleted_files: List[str] = []
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA secure_delete = ON")
        db.row_factory = aiosqlite.Row

        # 1. Find all artifacts tied to this conversation (both in artifacts table and message JSON)
        art_cursor = await db.execute(
            "SELECT id, filename FROM artifacts WHERE conversation_id = ?",
            (conversation_id,),
        )
        art_rows = await art_cursor.fetchall()
        filenames_to_wipe = {r["filename"] for r in art_rows if r["filename"]}

        msg_cursor = await db.execute(
            "SELECT artifacts FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        msg_rows = await msg_cursor.fetchall()
        for mr in msg_rows:
            try:
                arts = json.loads(mr["artifacts"] or "[]")
                for a in arts:
                    if isinstance(a, dict) and a.get("filename"):
                        filenames_to_wipe.add(a["filename"])
            except Exception:
                pass

        # 2. Physically overwrite and unlink files on disk
        for fname in filenames_to_wipe:
            safe_name = Path(fname).name
            fpath = ARTIFACTS_DIR / safe_name
            if fpath.exists() and fpath.is_file():
                try:
                    size = fpath.stat().st_size
                    if size > 0:
                        with open(fpath, "ba+", buffering=0) as f:
                            f.seek(0)
                            f.write(b"\x00" * min(size, 1024 * 1024))
                    fpath.unlink(missing_ok=True)
                    deleted_files.append(safe_name)
                except Exception:
                    fpath.unlink(missing_ok=True)

            await db.execute("DELETE FROM artifacts WHERE filename = ?", (safe_name,))

        # 3. Delete all DB rows for artifacts, messages, and conversation
        await db.execute("DELETE FROM artifacts WHERE conversation_id = ?", (conversation_id,))
        await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await db.commit()

        # 4. Reclaim and zero out SQLite pages
        await db.execute("VACUUM")

    return {"status": "obliterated", "deleted_files": deleted_files}


async def delete_artifact(artifact_id: str) -> Dict[str, Any]:
    """Obliterate a single generated file from disk and SQLite, purging it from message history."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA secure_delete = ON")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, filename FROM artifacts WHERE id = ? OR filename = ?",
            (artifact_id, artifact_id),
        )
        rows = await cursor.fetchall()
        target_ids = {r["id"] for r in rows}
        target_ids.add(artifact_id)
        target_filenames = {r["filename"] for r in rows if r["filename"]}

        for fname in target_filenames:
            fpath = ARTIFACTS_DIR / Path(fname).name
            if fpath.exists() and fpath.is_file():
                try:
                    size = fpath.stat().st_size
                    if size > 0:
                        with open(fpath, "ba+", buffering=0) as f:
                            f.seek(0)
                            f.write(b"\x00" * min(size, 1024 * 1024))
                    fpath.unlink(missing_ok=True)
                except Exception:
                    fpath.unlink(missing_ok=True)

        for tid in target_ids:
            await db.execute("DELETE FROM artifacts WHERE id = ?", (tid,))
        for fname in target_filenames:
            await db.execute("DELETE FROM artifacts WHERE filename = ?", (fname,))

        # Purge deleted artifact from all message history records
        msg_cursor = await db.execute("SELECT id, artifacts FROM messages WHERE artifacts IS NOT NULL AND artifacts != '[]'")
        msg_rows = await msg_cursor.fetchall()
        for mr in msg_rows:
            try:
                arts = json.loads(mr["artifacts"] or "[]")
                filtered = [
                    a for a in arts
                    if isinstance(a, dict) and a.get("id") not in target_ids and a.get("filename") not in target_filenames
                ]
                if len(filtered) != len(arts):
                    await db.execute(
                        "UPDATE messages SET artifacts = ? WHERE id = ?",
                        (json.dumps(filtered), mr["id"]),
                    )
            except Exception:
                pass

        await db.commit()
    return {"status": "obliterated", "id": artifact_id}


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    thinking: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    model: str = "",
    tokens_per_sec: float = 0.0,
) -> Dict[str, Any]:
    mid = str(uuid.uuid4())
    now = time.time()
    tc_json = json.dumps(tool_calls or [])
    art_json = json.dumps(artifacts or [])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO messages
            (id, conversation_id, role, content, thinking, tool_calls, artifacts, model, tokens_per_sec, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (mid, conversation_id, role, content, thinking, tc_json, art_json, model, tokens_per_sec, now),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await db.commit()
    return {
        "id": mid,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "thinking": thinking,
        "tool_calls": tool_calls or [],
        "artifacts": artifacts or [],
        "model": model,
        "tokens_per_sec": tokens_per_sec,
        "created_at": now,
    }


async def update_conversation_title(conversation_id: str, title: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), conversation_id),
        )
        await db.commit()


async def register_artifact(
    title: str,
    filename: str,
    category: str,
    mime_type: str,
    size_bytes: int,
    preview_data: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    aid = str(uuid.uuid4())
    now = time.time()
    prev_json = json.dumps(preview_data or {})
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO artifacts
            (id, conversation_id, title, filename, category, mime_type, size_bytes, preview_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (aid, conversation_id, title, filename, category, mime_type, size_bytes, prev_json, now),
        )
        await db.commit()
    return {
        "id": aid,
        "conversation_id": conversation_id,
        "title": title,
        "filename": filename,
        "url": f"/api/artifacts/file/{filename}",
        "category": category,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "preview_data": preview_data or {},
        "created_at": now,
    }


async def list_artifacts() -> List[Dict[str, Any]]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout = 5000")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM artifacts ORDER BY created_at DESC LIMIT 200")
        rows = await cursor.fetchall()
        items = []
        dead_ids = []
        known_filenames = set()

        for r in rows:
            d = dict(r)
            fname = d["filename"]
            known_filenames.add(fname)
            fpath = ARTIFACTS_DIR / Path(fname).name

            # If user deleted the file from disk (e.g. in Windows Explorer), prune from DB!
            if not fpath.exists():
                dead_ids.append(d["id"])
                continue

            d["url"] = f"/api/artifacts/file/{d['filename']}"
            d["preview_data"] = json.loads(d.get("preview_data") or "{}")
            items.append(d)

        if dead_ids:
            for did in dead_ids:
                await db.execute("DELETE FROM artifacts WHERE id = ?", (did,))
            await db.commit()

        # Auto-discover any unindexed files on disk (e.g. test images or copied files)
        newly_indexed = []
        for disk_file in ARTIFACTS_DIR.iterdir():
            if not disk_file.is_file() or disk_file.name.startswith(".") or disk_file.name in known_filenames:
                continue

            raw_name = disk_file.name
            ext = disk_file.suffix.lower()
            cat = "document"
            mime = "application/octet-stream"
            if ext in (".xlsx", ".xls", ".csv"):
                cat = "spreadsheet"
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if ext.startswith(".xls") else "text/csv"
            elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                cat = "image"
                mime = f"image/{ext.lstrip('.')}"
            elif ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".sql", ".sh"):
                cat = "code"
                mime = "text/plain"
            elif ext in (".mp4", ".webm"):
                cat = "video"
                mime = f"video/{ext.lstrip('.')}"

            stat = disk_file.stat()
            aid = str(uuid.uuid4())
            now = stat.st_mtime
            prev_json = "{}"

            await db.execute(
                """
                INSERT INTO artifacts
                (id, conversation_id, title, filename, category, mime_type, size_bytes, preview_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, None, raw_name, raw_name, cat, mime, stat.st_size, prev_json, now),
            )
            newly_indexed.append({
                "id": aid,
                "conversation_id": None,
                "title": raw_name,
                "filename": raw_name,
                "url": f"/api/artifacts/file/{raw_name}",
                "category": cat,
                "mime_type": mime,
                "size_bytes": stat.st_size,
                "preview_data": {},
                "created_at": now,
            })

        if newly_indexed:
            await db.commit()
            items = sorted(items + newly_indexed, key=lambda x: x["created_at"], reverse=True)

        return items
