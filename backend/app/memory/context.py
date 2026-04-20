# =============================================================================
# memory/context.py
# Redis-based session management for Daraz Voice Assistant.
# Provides a shared, persistent key-value store for session history and state,
# enabling horizontal scaling across multiple backend workers.
#
# Session key format : "session:{session_id}" (JSON blob)
# TTL-based expiration ensures automatic cleanup of inactive sessions.
# =============================================================================

import json
import re
import logging
from typing import Optional

import redis

from app.core.config import (
    REDIS_URL,
    REDIS_SESSION_TTL,
    build_system_prompt,
    SLIDING_WINDOW_SIZE,
    MAX_TURNS,
    WELCOME_MESSAGE,
)
from app.memory.database import save_session, load_session, load_all_sessions_to_memory, init_db

logger = logging.getLogger(__name__)

# =============================================================================
# REDIS CLIENT
# Using the synchronous redis client to keep all context functions sync,
# matching the existing call patterns in engine.py and routes.py.
# =============================================================================
_redis: redis.Redis = redis.from_url(REDIS_URL, decode_responses=True)

_SESSION_PREFIX = "session:"


def _key(session_id: str) -> str:
    """Namespaced Redis key for a session."""
    return f"{_SESSION_PREFIX}{session_id}"


# =============================================================================
# REGEX PATTERNS (unchanged from A2)
# =============================================================================
_STATE_PATTERN = re.compile(r"<STATE>\s*(.*?)(?:</STATE>|$)", re.DOTALL | re.IGNORECASE)
_STATE_KV_PATTERN = re.compile(
    r"(Budget|Item|Preferences|Resolved)\s*:\s*([^,<]+)", re.IGNORECASE
)


# =============================================================================
# REDIS SESSION HELPERS
# =============================================================================

def _load_from_redis(session_id: str) -> Optional[dict]:
    """Deserialises a session JSON blob from Redis. Returns None if missing."""
    try:
        raw = _redis.get(_key(session_id))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.error(f"[context] Redis read error for {session_id}: {e}")
    return None


def _save_to_redis(session_id: str, session: dict) -> None:
    """Serialises and writes session to Redis with TTL refresh."""
    try:
        _redis.setex(_key(session_id), REDIS_SESSION_TTL, json.dumps(session))
    except Exception as e:
        logger.error(f"[context] Redis write error for {session_id}: {e}")


def _delete_from_redis(session_id: str) -> None:
    try:
        _redis.delete(_key(session_id))
    except Exception as e:
        logger.error(f"[context] Redis delete error for {session_id}: {e}")


# =============================================================================
# STARTUP
# =============================================================================

def init_sessions_from_db() -> None:
    """
    Loads all SQLite-persisted sessions into Redis at server startup.
    This means a server restart does not lose session history — sessions are
    read from SQLite (cold storage) and written to Redis (hot cache).
    """
    init_db()
    loaded = load_all_sessions_to_memory()
    for session_id, session in loaded.items():
        _save_to_redis(session_id, session)
    logger.info(f"[context] Loaded {len(loaded)} sessions from DB → Redis")


# =============================================================================
# PUBLIC SESSION API (same interface as A2 — callers are unchanged)
# =============================================================================

def get_or_create_session(session_id: str) -> dict:
    """
    Returns existing session from Redis, falls back to SQLite, then creates fresh.

    Args:
        session_id: Unique session identifier (UUID recommended).

    Returns:
        Session dict: {history, state, turns, status}
    """
    # 1. Hot path: Redis
    session = _load_from_redis(session_id)
    if session:
        return session

    # 2. Warm path: SQLite (e.g. Redis was flushed but SQLite still has it)
    db_session = load_session(session_id)
    if db_session:
        _save_to_redis(session_id, db_session)
        logger.info(f"[context] Loaded session from DB → Redis: {session_id}")
        return db_session

    # 3. Cold path: brand new session
    session = {
        "history": [],
        "state": {
            "budget":      None,
            "item":        None,
            "preferences": None,
            "resolved":    "no",
        },
        "turns":  0,
        "status": "active",
    }
    _save_to_redis(session_id, session)
    logger.info(f"[context] New session: {session_id}")
    return session


def add_message_to_chat(session_id: str, role: str, text: str) -> None:
    """
    Appends a message to session history and persists to Redis + SQLite.
    Call with clean text — STATE tag must be stripped before calling.
    """
    session = get_or_create_session(session_id)
    session["history"].append({"role": role, "content": text})
    _save_to_redis(session_id, session)
    _persist_to_sqlite(session_id, session)


def get_chat_history(session_id: str) -> list:
    return get_or_create_session(session_id)["history"]


def get_session_state(session_id: str) -> dict:
    return get_or_create_session(session_id)["state"]


def get_session_status(session_id: str) -> str:
    return get_or_create_session(session_id)["status"]


def set_session_status(session_id: str, status: str) -> None:
    session = get_or_create_session(session_id)
    session["status"] = status
    _save_to_redis(session_id, session)
    _persist_to_sqlite(session_id, session)


def increment_turn(session_id: str) -> None:
    session = get_or_create_session(session_id)
    session["turns"] += 1
    _save_to_redis(session_id, session)
    _persist_to_sqlite(session_id, session)


def is_session_maxed(session_id: str) -> bool:
    return get_or_create_session(session_id)["turns"] >= MAX_TURNS


def reset_session(session_id: str) -> None:
    """
    Wipes a session from Redis (SQLite record is kept for history).
    Called by /reset endpoint (New Chat button).
    """
    session = _load_from_redis(session_id)
    if session:
        _persist_to_sqlite(session_id, session)  # flush final state to SQLite
        _delete_from_redis(session_id)
    logger.info(f"[context] Session reset: {session_id}")


def list_active_sessions() -> list:
    """Returns all session IDs currently in Redis."""
    try:
        keys = _redis.keys(f"{_SESSION_PREFIX}*")
        return [k.replace(_SESSION_PREFIX, "") for k in keys]
    except Exception as e:
        logger.error(f"[context] Redis keys error: {e}")
        return []


def get_welcome_message(session_id: str) -> dict:
    get_or_create_session(session_id)
    return {
        "session_id": session_id,
        "response":   WELCOME_MESSAGE,
        "latency_ms": 0.0,
        "status":     "active",
        "turns_used": 0,
        "turns_max":  MAX_TURNS,
    }


# =============================================================================
# CONTEXT WINDOW BUILDER (unchanged logic — Redis transparent to callers)
# =============================================================================

def build_inference_payload(session_id: str, new_user_message: str, rag_context: str = "") -> list:
    """
    Assembles the prompt payload for the LLM engine.
    Sliding window keeps only the last SLIDING_WINDOW_SIZE messages;
    critical state facts are preserved via system prompt injection.
    """
    session = get_or_create_session(session_id)

    system_msg = {
        "role":    "system",
        "content": build_system_prompt(session["state"], rag_context=rag_context),
    }

    trimmed = session["history"][-SLIDING_WINDOW_SIZE:]

    payload = [system_msg] + trimmed + [{"role": "user", "content": new_user_message}]

    logger.debug(
        f"[context] [{session_id}] Payload: "
        f"1 system + {len(trimmed)} history + 1 user = {len(payload)} messages"
    )
    return payload



# =============================================================================
# STATE EXTRACTION (unchanged from A2)
# =============================================================================

def extract_and_strip_state(session_id: str, raw_response: str) -> str:
    """
    Extracts the <STATE> block from the LLM response, updates session state
    in Redis, and returns the clean conversational text for TTS/display.
    """
    session = get_or_create_session(session_id)

    logger.info(f"[context] RAW RESPONSE: {repr(raw_response)}")

    match = _STATE_PATTERN.search(raw_response)
    if match:
        _update_state_from_block(session["state"], match.group(1))
        _save_to_redis(session_id, session)
        logger.debug(f"[context] [{session_id}] State updated: {session['state']}")
    else:
        logger.warning(f"[context] [{session_id}] NO STATE TAG FOUND in response")

    # Strip <think> blocks (chain-of-thought models), STATE tag, and Resolved line
    clean = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
    clean = _STATE_PATTERN.sub("", clean).strip()
    clean = re.sub(r"Resolved\s*:\s*(yes|no)", "", clean, flags=re.IGNORECASE).strip()
    return clean


def is_conversation_resolved(session_id: str) -> bool:
    """
    Returns True if model flagged Resolved: yes in the last STATE block.
    Drives the session lifecycle transition to "closing".
    """
    state = get_or_create_session(session_id)["state"]
    return state.get("resolved", "no").lower().strip() == "yes"


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _update_state_from_block(state: dict, state_block: str) -> None:
    """Parses KV pairs from STATE block. Skips placeholder values."""
    for match in _STATE_KV_PATTERN.finditer(state_block):
        key   = match.group(1).strip().lower()
        value = match.group(2).strip()
        if value.lower() in ("unknown", "none", "n/a", ""):
            continue
        state[key] = value


def _persist_to_sqlite(session_id: str, session: dict) -> None:
    """Writes session to SQLite as cold storage. Called after mutations."""
    try:
        save_session(session_id, session)
    except Exception as e:
        logger.error(f"[context] SQLite persistence error for {session_id}: {e}")