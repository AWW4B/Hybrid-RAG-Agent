"""
db.py — Async SQLite database layer (WAL mode, zero-latency writes).

Tables: users, sessions, messages, session_context, user_crm.
Every public function is an async coroutine; the module manages its own
connection pool via a single WAL-mode aiosqlite connection.
"""

import uuid
import json
import logging
import aiosqlite
from datetime import datetime
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

# ── Module-level connection (initialized once at startup) ───────────
_db: Optional[aiosqlite.Connection] = None


async def init_db() -> None:
    """Open the WAL-mode connection and create tables if they don't exist."""
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row

    # WAL + performance pragmas
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA synchronous=NORMAL")
    await _db.execute("PRAGMA cache_size=-8000")        # 8 MB page cache
    await _db.execute("PRAGMA temp_store=MEMORY")
    await _db.execute("PRAGMA mmap_size=67108864")       # 64 MB mmap

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    TEXT PRIMARY KEY,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            title      TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS session_context (
            session_id      TEXT PRIMARY KEY,
            context_summary TEXT DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_crm (
            user_id    TEXT PRIMARY KEY,
            crm_json   TEXT DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
    """)
    await _db.commit()
    logger.info("[db] Database initialized (WAL mode).")


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


def _now() -> str:
    return datetime.utcnow().isoformat()


# ════════════════════════════════════════════════════════════════════
#  USERS
# ════════════════════════════════════════════════════════════════════

async def create_user(username: str, password: str) -> str:
    """Insert a new user and return user_id."""
    user_id = uuid.uuid4().hex
    await _db.execute(
        "INSERT INTO users (user_id, username, password) VALUES (?, ?, ?)",
        (user_id, username, password),
    )
    await _db.commit()
    return user_id


async def get_user_by_username(username: str) -> Optional[dict]:
    cursor = await _db.execute(
        "SELECT user_id, username, password FROM users WHERE username = ?",
        (username,),
    )
    row = await cursor.fetchone()
    if row:
        return {"user_id": row["user_id"], "username": row["username"], "password": row["password"]}
    return None


# ════════════════════════════════════════════════════════════════════
#  SESSIONS
# ════════════════════════════════════════════════════════════════════

async def create_session(user_id: str, title: str = "") -> str:
    session_id = uuid.uuid4().hex
    now = _now()
    await _db.execute(
        "INSERT INTO sessions (session_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, user_id, title, now, now),
    )
    # Also create the 1-to-1 context row
    await _db.execute(
        "INSERT INTO session_context (session_id, context_summary, updated_at) VALUES (?, '', ?)",
        (session_id, now),
    )
    await _db.commit()
    return session_id


async def get_sessions_for_user(user_id: str) -> list[dict]:
    cursor = await _db.execute(
        "SELECT session_id, title, created_at, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def touch_session(session_id: str) -> None:
    """Update the updated_at timestamp."""
    await _db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (_now(), session_id),
    )
    await _db.commit()


async def delete_session(session_id: str) -> None:
    """Delete a session and all its related data."""
    await _db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    await _db.execute("DELETE FROM session_context WHERE session_id = ?", (session_id,))
    await _db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    await _db.commit()


# ════════════════════════════════════════════════════════════════════
#  MESSAGES
# ════════════════════════════════════════════════════════════════════

async def save_message(session_id: str, role: str, content: str) -> None:
    await _db.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, _now()),
    )
    await _db.commit()


async def get_messages(session_id: str, limit: int = 200) -> list[dict]:
    cursor = await _db.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY message_id ASC LIMIT ?",
        (session_id, limit),
    )
    rows = await cursor.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


# ════════════════════════════════════════════════════════════════════
#  SESSION CONTEXT (compaction summaries)
# ════════════════════════════════════════════════════════════════════

async def get_session_context(session_id: str) -> str:
    cursor = await _db.execute(
        "SELECT context_summary FROM session_context WHERE session_id = ?",
        (session_id,),
    )
    row = await cursor.fetchone()
    return row["context_summary"] if row else ""


async def update_session_context(session_id: str, summary: str) -> None:
    await _db.execute(
        "INSERT INTO session_context (session_id, context_summary, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET context_summary = excluded.context_summary, updated_at = excluded.updated_at",
        (session_id, summary, _now()),
    )
    await _db.commit()


# ════════════════════════════════════════════════════════════════════
#  USER CRM
# ════════════════════════════════════════════════════════════════════

async def get_crm(user_id: str) -> dict:
    cursor = await _db.execute(
        "SELECT crm_json FROM user_crm WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    if row and row["crm_json"]:
        try:
            return json.loads(row["crm_json"])
        except json.JSONDecodeError:
            return {}
    return {}


async def upsert_crm(user_id: str, crm_data: dict) -> None:
    await _db.execute(
        "INSERT INTO user_crm (user_id, crm_json, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET crm_json = excluded.crm_json, updated_at = excluded.updated_at",
        (user_id, json.dumps(crm_data, ensure_ascii=False), _now()),
    )
    await _db.commit()


# ════════════════════════════════════════════════════════════════════
#  BULK LOAD (login hook)
# ════════════════════════════════════════════════════════════════════

async def load_user_context_bulk(user_id: str) -> dict:
    """
    Called once on login.  Returns everything needed to hydrate the RAM cache:
    {
        "crm": {...},
        "sessions": [
            {"session_id": "...", "title": "...", "context_summary": "..."},
            ...
        ]
    }
    """
    crm = await get_crm(user_id)

    cursor = await _db.execute(
        """
        SELECT s.session_id, s.title, COALESCE(sc.context_summary, '') AS context_summary
        FROM sessions s
        LEFT JOIN session_context sc ON s.session_id = sc.session_id
        WHERE s.user_id = ?
        ORDER BY s.updated_at DESC
        """,
        (user_id,),
    )
    rows = await cursor.fetchall()
    sessions = [
        {"session_id": r["session_id"], "title": r["title"], "context_summary": r["context_summary"]}
        for r in rows
    ]

    return {"crm": crm, "sessions": sessions}
