"""
memory.py — RAM-first session & user memory cache.

On login the bulk loader hydrates this cache from the DB.
During chat, everything reads/writes here first; DB persistence
happens asynchronously via fire-and-forget tasks.
"""

import logging
from typing import Optional
from tools.crm import format_crm_block, EMPTY_CRM
from config import SYSTEM_PROMPT_BASE

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
#  IN-MEMORY STORES  (keyed by user_id / session_id)
# ════════════════════════════════════════════════════════════════════

# user_id → full CRM dict
_crm_cache: dict[str, dict] = {}

# session_id → compaction summary string
_context_cache: dict[str, str] = {}

# session_id → list[{"role": ..., "content": ...}]
_history_cache: dict[str, list[dict]] = {}

# session_id → user_id  (reverse lookup)
_session_owner: dict[str, str] = {}


# ════════════════════════════════════════════════════════════════════
#  HYDRATION  (called once on login)
# ════════════════════════════════════════════════════════════════════

def hydrate_user(user_id: str, bulk: dict) -> None:
    """
    Populate the RAM caches from the dict returned by db.load_user_context_bulk().
    """
    _crm_cache[user_id] = bulk.get("crm") or {**EMPTY_CRM}

    for sess in bulk.get("sessions", []):
        sid = sess["session_id"]
        _context_cache[sid] = sess.get("context_summary", "")
        _session_owner[sid] = user_id
        # History is NOT loaded here — loaded lazily on first chat in that session
    logger.info(f"[memory] Hydrated user {user_id}: CRM + {len(bulk.get('sessions', []))} session contexts")


# ════════════════════════════════════════════════════════════════════
#  CRM ACCESSORS
# ════════════════════════════════════════════════════════════════════

def get_crm(user_id: str) -> dict:
    return _crm_cache.get(user_id, {**EMPTY_CRM})


def set_crm(user_id: str, crm: dict) -> None:
    _crm_cache[user_id] = crm


# ════════════════════════════════════════════════════════════════════
#  SESSION CONTEXT (compaction summaries)
# ════════════════════════════════════════════════════════════════════

def get_context(session_id: str) -> str:
    return _context_cache.get(session_id, "")


def set_context(session_id: str, summary: str) -> None:
    _context_cache[session_id] = summary


# ════════════════════════════════════════════════════════════════════
#  CONVERSATION HISTORY
# ════════════════════════════════════════════════════════════════════

def get_history(session_id: str) -> list[dict]:
    return _history_cache.setdefault(session_id, [])


def set_history(session_id: str, history: list[dict]) -> None:
    _history_cache[session_id] = history


def append_message(session_id: str, role: str, content: str) -> None:
    _history_cache.setdefault(session_id, []).append({"role": role, "content": content})


def register_session(session_id: str, user_id: str) -> None:
    """Track which user owns a session (for CRM lookups)."""
    _session_owner[session_id] = user_id
    _history_cache.setdefault(session_id, [])
    _context_cache.setdefault(session_id, "")


def get_session_owner(session_id: str) -> Optional[str]:
    return _session_owner.get(session_id)


# ════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT BUILDER
# ════════════════════════════════════════════════════════════════════

def build_system_prompt(session_id: str) -> str:
    """
    Assemble the full system prompt by combining:
      1. Base persona
      2. CRM profile block  (if any)
      3. Session compaction summary  (if any)
    """
    parts = [SYSTEM_PROMPT_BASE]

    # Inject CRM
    user_id = _session_owner.get(session_id)
    if user_id:
        crm_block = format_crm_block(get_crm(user_id))
        if crm_block:
            parts.append(crm_block)

    # Inject compaction context
    ctx = get_context(session_id)
    if ctx:
        parts.append(f"[Previous Conversation Summary]\n{ctx}\n")

    return "\n\n".join(parts)


def build_prompt_messages(
    session_id: str,
    tool_context: str = "",
) -> list[dict]:
    """
    Build the full message array ready for the Chat LLM:
      [system, ...history, (tool_context if present is appended to last user msg)]
    """
    system_content = build_system_prompt(session_id)
    messages: list[dict] = [{"role": "system", "content": system_content}]

    history = get_history(session_id)

    if tool_context and history:
        # Clone history so we don't mutate the cache
        history = [msg.copy() for msg in history]
        # Append tool context to the last user message
        for i in range(len(history) - 1, -1, -1):
            if history[i]["role"] == "user":
                history[i]["content"] += f"\n\n{tool_context}"
                break

    messages.extend(history)
    return messages
