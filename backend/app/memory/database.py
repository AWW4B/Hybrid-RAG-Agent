# =============================================================================
# memory/database.py
# Awwab — A3 addition: bleach sanitization applied to all message content
#         before it is written to SQLite, preventing stored XSS.
#
# All other logic (schema, CRUD, session loading) is unchanged from A2.
# =============================================================================

import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional

import bleach

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE PATH
# =============================================================================
_DB_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
)
_DB_PATH = os.path.join(_DB_DIR, "sessions.db")


def _get_connection() -> sqlite3.Connection:
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _sanitize(text: str) -> str:
    """
    Strips all HTML/JS from a string before it enters SQLite.
    bleach.clean() with empty tag/attr sets removes all markup.
    Called on every message content value at write time.
    """
    return bleach.clean(text, tags=[], attributes={}, strip=True)


# =============================================================================
# SCHEMA
# =============================================================================

def init_db() -> None:
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  TEXT PRIMARY KEY,
                title       TEXT DEFAULT 'New Chat',
                state       TEXT DEFAULT '{}',
                turns       INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'active',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_updated
                ON sessions(updated_at DESC);
        """)
        conn.commit()
        logger.info(f"[database] Initialized SQLite at {_DB_PATH}")
    finally:
        conn.close()


# =============================================================================
# SESSION CRUD
# =============================================================================

def save_session(session_id: str, session_data: dict) -> None:
    """
    Upserts a session and all its messages.
    Message content is sanitized with bleach before insertion.
    """
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Title from first user message
        title = "New Chat"
        for msg in session_data.get("history", []):
            if msg["role"] == "user":
                raw_title = _sanitize(msg["content"])[:50]
                title = raw_title + ("..." if len(msg["content"]) > 50 else "")
                break

        conn.execute(
            """
            INSERT INTO sessions (session_id, title, state, turns, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                title      = excluded.title,
                state      = excluded.state,
                turns      = excluded.turns,
                status     = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                title,
                json.dumps(session_data.get("state", {})),
                session_data.get("turns", 0),
                session_data.get("status", "active"),
                now,
                now,
            ),
        )

        # Sanitize all message content before writing
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        for msg in session_data.get("history", []):
            safe_content = _sanitize(msg["content"])
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, msg["role"], safe_content, now),
            )

        conn.commit()
        logger.debug(
            f"[database] Saved session {session_id} "
            f"({len(session_data.get('history', []))} messages)"
        )

    except Exception as e:
        logger.error(f"[database] Error saving session {session_id}: {e}")
    finally:
        conn.close()


def load_session(session_id: str) -> Optional[dict]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

        if not row:
            return None

        messages = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        return {
            "history": [{"role": m["role"], "content": m["content"]} for m in messages],
            "state":   json.loads(row["state"]) if row["state"] else {},
            "turns":   row["turns"],
            "status":  row["status"],
        }

    except Exception as e:
        logger.error(f"[database] Error loading session {session_id}: {e}")
        return None
    finally:
        conn.close()


def list_sessions() -> list:
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.session_id, s.title, s.status, s.turns,
                   s.created_at, s.updated_at,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            """
        ).fetchall()

        sessions = []
        for row in rows:
            last_msg = conn.execute(
                "SELECT content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (row["session_id"],),
            ).fetchone()

            preview = ""
            if last_msg:
                preview = last_msg["content"][:80]
                if len(last_msg["content"]) > 80:
                    preview += "..."

            sessions.append({
                "session_id":    row["session_id"],
                "title":         row["title"],
                "status":        row["status"],
                "turns":         row["turns"],
                "message_count": row["message_count"],
                "created_at":    row["created_at"],
                "updated_at":    row["updated_at"],
                "preview":       preview,
            })

        return sessions

    except Exception as e:
        logger.error(f"[database] Error listing sessions: {e}")
        return []
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    conn = _get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        logger.info(f"[database] Deleted session {session_id}")
        return True
    except Exception as e:
        logger.error(f"[database] Error deleting session {session_id}: {e}")
        return False
    finally:
        conn.close()


def load_all_sessions_to_memory() -> dict:
    """Loads all sessions from SQLite on startup (for Redis warm-up)."""
    conn = _get_connection()
    result = {}
    try:
        rows = conn.execute("SELECT session_id FROM sessions").fetchall()
        for row in rows:
            session = load_session(row["session_id"])
            if session:
                result[row["session_id"]] = session
        logger.info(f"[database] Loaded {len(result)} sessions into memory")
        return result
    except Exception as e:
        logger.error(f"[database] Error loading sessions: {e}")
        return {}
    finally:
        conn.close()