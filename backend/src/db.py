# =============================================================================
# backend/src/db.py
# Async database access layer. ALL SQL lives here — no raw SQL outside this module.
# Uses aiosqlite for async access, compatible with FastAPI's async handlers.
# =============================================================================

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB path — same data directory used by the legacy sync layer
# ---------------------------------------------------------------------------
_DB_DIR = os.getenv("DB_DIR", "/data")
_DB_PATH = os.path.join(_DB_DIR, "sessions.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _connect() -> aiosqlite.Connection:
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = await aiosqlite.connect(_DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


# =============================================================================
# SCHEMA MIGRATION — adds new tables without dropping existing ones
# =============================================================================
async def init_db() -> None:
    """Run once at startup. Safe to call repeatedly (IF NOT EXISTS guards)."""
    conn = await _connect()
    try:
        await conn.executescript("""
            -- Existing tables (kept intact)
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
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);

            -- NEW: User accounts
            CREATE TABLE IF NOT EXISTS users (
                id               TEXT PRIMARY KEY,
                username         TEXT UNIQUE NOT NULL,
                email            TEXT UNIQUE NOT NULL,
                password_hash    TEXT NOT NULL,
                created_at       TEXT NOT NULL,
                last_login       TEXT,
                is_active        INTEGER DEFAULT 1,
                is_admin         INTEGER DEFAULT 0,
                failed_attempts  INTEGER DEFAULT 0,
                locked_until     TEXT
            );

            -- NEW: CRM profiles (one per user)
            CREATE TABLE IF NOT EXISTS crm_profiles (
                user_id              TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                name                 TEXT,
                preferred_categories TEXT,
                budget_range         TEXT,
                liked_brands         TEXT,
                disliked_brands      TEXT,
                last_session_summary TEXT,
                notes                TEXT,
                updated_at           TEXT
            );

            -- NEW: Session memory (compacted message state)
            CREATE TABLE IF NOT EXISTS session_memory (
                session_id    TEXT PRIMARY KEY,
                user_id       TEXT REFERENCES users(id) ON DELETE CASCADE,
                messages_json TEXT NOT NULL,
                turn_count    INTEGER DEFAULT 0,
                last_active   TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            -- NEW: Compaction audit log
            CREATE TABLE IF NOT EXISTS compaction_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT,
                user_id         TEXT,
                compaction_type TEXT,
                tokens_before   INTEGER,
                tokens_after    INTEGER,
                triggered_at    TEXT
            );

            -- NEW: Benchmark results
            CREATE TABLE IF NOT EXISTS benchmark_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at      TEXT NOT NULL,
                test_name   TEXT NOT NULL,
                metric      TEXT NOT NULL,
                value       REAL NOT NULL,
                session_id  TEXT,
                notes       TEXT
            );
        """)
        await conn.commit()
        logger.info(f"[db] Schema initialized at {_DB_PATH}")
    finally:
        await conn.close()


# =============================================================================
# USER ACCOUNTS
# =============================================================================
async def get_user_by_username(username: str) -> Optional[dict]:
    conn = await _connect()
    try:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = await _connect()
    try:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_user_by_email(email: str) -> Optional[dict]:
    conn = await _connect()
    try:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def create_user(username: str, email: str, password_hash: str) -> str:
    """Creates a new user and returns their UUID."""
    user_id = str(uuid.uuid4())
    now = _now()
    conn = await _connect()
    try:
        await conn.execute(
            """INSERT INTO users (id, username, email, password_hash, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (user_id, username, email, password_hash, now),
        )
        await conn.commit()
        return user_id
    finally:
        await conn.close()


async def update_login_attempt(user_id: str, success: bool, max_attempts: int = 5, lockout_minutes: int = 15) -> None:
    """
    On success: resets failed_attempts, sets last_login, clears locked_until.
    On failure: increments failed_attempts; locks account if threshold reached.
    """
    conn = await _connect()
    try:
        if success:
            await conn.execute(
                """UPDATE users SET failed_attempts = 0, last_login = ?, locked_until = NULL
                   WHERE id = ?""",
                (_now(), user_id),
            )
        else:
            # Atomically increment and conditionally set lock
            cursor = await conn.execute(
                "SELECT failed_attempts FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            current = (row["failed_attempts"] if row else 0) + 1
            locked_until = None
            if current >= max_attempts:
                locked_until = (
                    datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
                ).isoformat()
            await conn.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                (current, locked_until, user_id),
            )
        await conn.commit()
    finally:
        await conn.close()


async def unlock_user(user_id: str) -> None:
    """Admin action: clear lockout and reset failed attempts."""
    conn = await _connect()
    try:
        await conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (user_id,),
        )
        await conn.commit()
    finally:
        await conn.close()


async def list_users(page: int = 1, page_size: int = 20) -> list[dict]:
    conn = await _connect()
    offset = (page - 1) * page_size
    try:
        cursor = await conn.execute(
            """SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                      u.is_active, u.is_admin, u.failed_attempts, u.locked_until,
                      CASE WHEN c.user_id IS NOT NULL THEN 1 ELSE 0 END as has_crm
               FROM users u
               LEFT JOIN crm_profiles c ON u.id = c.user_id
               ORDER BY u.created_at DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# =============================================================================
# CRM PROFILES
# =============================================================================
async def get_crm_profile(user_id: str) -> Optional[dict]:
    conn = await _connect()
    try:
        cursor = await conn.execute(
            "SELECT * FROM crm_profiles WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        profile = dict(row)
        # Deserialize JSON array fields
        for field in ("preferred_categories", "liked_brands", "disliked_brands"):
            raw = profile.get(field)
            if raw:
                try:
                    profile[field] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    profile[field] = []
            else:
                profile[field] = []
        return profile
    finally:
        await conn.close()


async def upsert_crm_profile(user_id: str, updates: dict) -> None:
    """
    Creates or merges the CRM profile for user_id.
    Array fields (preferred_categories, liked_brands, disliked_brands) are
    merged with existing values rather than overwritten.
    """
    conn = await _connect()
    try:
        # Fetch current
        cursor = await conn.execute(
            "SELECT * FROM crm_profiles WHERE user_id = ?", (user_id,)
        )
        existing_row = await cursor.fetchone()
        existing = dict(existing_row) if existing_row else {}

        def _merge_list(field: str) -> str:
            old = []
            if existing.get(field):
                try:
                    old = json.loads(existing[field])
                except Exception:
                    old = []
            new_vals = updates.get(field, [])
            if isinstance(new_vals, str):
                new_vals = [new_vals]
            merged = list(dict.fromkeys(old + new_vals))  # deduplicate, preserve order
            return json.dumps(merged)

        now = _now()

        await conn.execute(
            """INSERT INTO crm_profiles (
                user_id, name, preferred_categories, budget_range,
                liked_brands, disliked_brands, last_session_summary, notes, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                name                 = COALESCE(excluded.name, name),
                preferred_categories = excluded.preferred_categories,
                budget_range         = COALESCE(excluded.budget_range, budget_range),
                liked_brands         = excluded.liked_brands,
                disliked_brands      = excluded.disliked_brands,
                last_session_summary = COALESCE(excluded.last_session_summary, last_session_summary),
                notes                = COALESCE(excluded.notes, notes),
                updated_at           = excluded.updated_at
            """,
            (
                user_id,
                updates.get("name", existing.get("name")),
                _merge_list("preferred_categories"),
                updates.get("budget_range", existing.get("budget_range")),
                _merge_list("liked_brands"),
                _merge_list("disliked_brands"),
                updates.get("last_session_summary", existing.get("last_session_summary")),
                updates.get("notes", existing.get("notes")),
                now,
            ),
        )
        await conn.commit()
    finally:
        await conn.close()


# =============================================================================
# SESSION MEMORY (compacted state persistence)
# =============================================================================
async def save_session_memory(
    session_id: str, user_id: str, messages: list, turn_count: int
) -> None:
    now = _now()
    conn = await _connect()
    try:
        await conn.execute(
            """INSERT INTO session_memory (session_id, user_id, messages_json, turn_count, last_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                user_id       = excluded.user_id,
                messages_json = excluded.messages_json,
                turn_count    = excluded.turn_count,
                last_active   = excluded.last_active
            """,
            (session_id, user_id, json.dumps(messages), turn_count, now, now),
        )
        await conn.commit()
    except Exception as e:
        logger.error(f"[db] save_session_memory failed for {session_id}: {e}")
    finally:
        await conn.close()


async def load_session_memory(session_id: str) -> Optional[dict]:
    conn = await _connect()
    try:
        cursor = await conn.execute(
            "SELECT * FROM session_memory WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "user_id":    row["user_id"],
            "messages":   json.loads(row["messages_json"]),
            "turn_count": row["turn_count"],
            "last_active": row["last_active"],
        }
    except Exception as e:
        logger.error(f"[db] load_session_memory failed for {session_id}: {e}")
        return None
    finally:
        await conn.close()


# =============================================================================
# COMPACTION LOG
# =============================================================================
async def log_compaction(
    session_id: str,
    user_id: str,
    comp_type: str,     # 'auto' | 'micro' | 'extraction'
    tokens_before: int,
    tokens_after: int,
) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """INSERT INTO compaction_log
               (session_id, user_id, compaction_type, tokens_before, tokens_after, triggered_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, comp_type, tokens_before, tokens_after, _now()),
        )
        await conn.commit()
    except Exception as e:
        logger.error(f"[db] log_compaction failed: {e}")
    finally:
        await conn.close()


async def get_compaction_stats(hours: int = 24) -> dict:
    """Returns counts and averages for the admin dashboard."""
    conn = await _connect()
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cursor = await conn.execute(
            """SELECT compaction_type,
                      COUNT(*) as count,
                      AVG(tokens_before) as avg_before,
                      AVG(tokens_after) as avg_after
               FROM compaction_log
               WHERE triggered_at >= ?
               GROUP BY compaction_type""",
            (since,),
        )
        rows = await cursor.fetchall()
        return {r["compaction_type"]: dict(r) for r in rows}
    finally:
        await conn.close()


# =============================================================================
# BENCHMARK RESULTS
# =============================================================================
async def insert_benchmark(
    test_name: str,
    metric: str,
    value: float,
    session_id: Optional[str] = None,
    notes: str = "",
) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """INSERT INTO benchmark_results (run_at, test_name, metric, value, session_id, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (_now(), test_name, metric, value, session_id, notes),
        )
        await conn.commit()
    except Exception as e:
        logger.error(f"[db] insert_benchmark failed: {e}")
    finally:
        await conn.close()


async def get_benchmark_history(limit: int = 100) -> list[dict]:
    conn = await _connect()
    try:
        cursor = await conn.execute(
            "SELECT * FROM benchmark_results ORDER BY run_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()
