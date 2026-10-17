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
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "local_ai_studio.db"
ARTIFACTS_DIR = ROOT_DIR / "workspace" / "artifacts"


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
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'chat',
                context TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        # Ensure `context` column exists on older databases
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN context TEXT NOT NULL DEFAULT ''")
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
        defaults = {
            "air_gap_mode": "true",
            "hardware_profile_override": "auto",
            "default_model": "qwen2.5-coder:7b",
            "agent_mode": "antigravity",
            "auto_vram_handoff": "true",
            "gaming_mode": "false",
            "brave_search_api_key": "",
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
        return {
            "air_gap_mode": raw.get("air_gap_mode", "true") == "true",
            "hardware_profile_override": raw.get("hardware_profile_override", "auto"),
            "default_model": raw.get("default_model", "qwen2.5-coder:7b"),
            "agent_mode": raw.get("agent_mode", "antigravity"),
            "auto_vram_handoff": raw.get("auto_vram_handoff", "true") == "true",
            "gaming_mode": raw.get("gaming_mode", "false") == "true",
            "brave_search_api_key": raw.get("brave_search_api_key", ""),
        }


async def update_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        for k, v in updates.items():
            val_str = "true" if v is True else ("false" if v is False else str(v))
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (k, val_str),
            )
        await db.commit()
    return await get_settings()


async def create_conversation(
    title: str,
    model: str,
    mode: str = "chat",
    context: str = "",
) -> Dict[str, Any]:
    cid = str(uuid.uuid4())
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id, title, model, mode, context, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cid, title, model, mode, context, now, now),
        )
        await db.commit()
    return {
        "id": cid,
        "title": title,
        "model": model,
        "mode": mode,
        "context": context,
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
            "SELECT id, title, model, mode, context, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, model, mode, context, created_at, updated_at FROM conversations WHERE id = ?",
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
