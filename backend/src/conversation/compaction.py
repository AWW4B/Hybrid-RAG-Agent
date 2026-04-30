# =============================================================================
# backend/src/conversation/compaction.py
# Layer 2 (Micro-Compaction) + Layer 3 (Auto-Compaction) + Layer 4 (Background Extraction)
# =============================================================================

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from src import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LAYER 2 — MICRO-COMPACTION
# ---------------------------------------------------------------------------
MICRO_COMPACTABLE_TOOLS = {
    "retrieve_documents",   # RAG output — potentially large
    "get_crm_profile",      # CRM fetch result
}

CLEARED_PLACEHOLDER = "[Tool result cleared — response already incorporates this output]"


def micro_compact(messages: list[dict]) -> list[dict]:
    """
    For each tool result message where:
      (a) the tool name is in MICRO_COMPACTABLE_TOOLS, AND
      (b) a subsequent assistant message already exists (LLM has processed it)
    → Replace content with CLEARED_PLACEHOLDER.

    INVARIANT: Never alter structure. Only replace content strings.
    Never remove messages — the message array must stay valid for the model API.
    Handles both legacy {role, content} dicts and tool-call-style dicts gracefully.
    """
    result = []
    for i, msg in enumerate(messages):
        is_clearable = (
            msg.get("role") == "tool"
            and msg.get("name") in MICRO_COMPACTABLE_TOOLS
            # Already cleared — don't double-process
            and msg.get("content") != CLEARED_PLACEHOLDER
        )
        already_processed = any(
            m.get("role") == "assistant" for m in messages[i + 1:]
        )
        if is_clearable and already_processed:
            result.append({**msg, "content": CLEARED_PLACEHOLDER})
        else:
            result.append(msg)
    return result


# ---------------------------------------------------------------------------
# LAYER 3 — AUTO-COMPACTION (Threshold-Based Summarization)
# ---------------------------------------------------------------------------
# Config — also referenced in config.py as constants
AUTO_COMPACT_THRESHOLD_PCT = 0.78   # Trigger when history ≥ 78% of context window
KEEP_RECENT_TURNS          = 3      # Never summarize the last N user+assistant pairs


def estimate_tokens(messages: list[dict]) -> int:
    """
    Conservative character-based estimate.
    1 token ≈ 3.5 chars for English. Undercount is dangerous (context blow), so
    we use 3.5 (rounds down) to *over*-estimate tokens = safer.
    """
    total = sum(len(str(m.get("content") or "")) for m in messages)
    return int(total / 3.5)


async def auto_compact_if_needed(
    session: dict,
    llm_generate_fn,   # Callable: async (messages: list) -> str
    context_window: int,
    session_id: str = "",
) -> bool:
    """
    Mutates session["history"] in-place if compaction runs.
    Returns True if compaction ran, False if skipped.

    Args:
        session:          The session dict (contains "history", "user_id", etc.)
        llm_generate_fn:  Non-streaming LLM callable for summarization.
        context_window:   N_CTX from config.
        session_id:       For logging/audit.
    """
    history = session.get("history", [])
    threshold = int(context_window * AUTO_COMPACT_THRESHOLD_PCT)
    current_tokens = estimate_tokens(history)

    if current_tokens < threshold:
        return False

    # -------------------------------------------------------------------------
    # Find split point: keep last KEEP_RECENT_TURNS user+assistant pairs verbatim
    # -------------------------------------------------------------------------
    pairs_kept = 0
    split_index = len(history)
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "assistant":
            pairs_kept += 1
        if pairs_kept >= KEEP_RECENT_TURNS:
            split_index = i
            break

    old_messages = history[:split_index]
    recent_messages = history[split_index:]

    if not old_messages:
        return False  # Nothing old enough to compact

    # -------------------------------------------------------------------------
    # Build summarization prompt — internal call, never streamed to user
    # -------------------------------------------------------------------------
    history_text = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')}"
        for m in old_messages
        if m.get("role") in ("user", "assistant")
        and not str(m.get("content", "")).startswith("[")  # skip placeholders
    )

    summary_prompt = [
        {
            "role": "user",
            "content": (
                "Summarize this shopping assistant conversation. Preserve:\n"
                "- Products the user asked about (with names/prices if mentioned)\n"
                "- User's stated preferences, budget, and constraints\n"
                "- Recommendations made and whether the user accepted them\n"
                "- Any unresolved questions or pending actions\n"
                "Be specific. One dense paragraph.\n\n"
                f"Conversation:\n{history_text}"
            ),
        }
    ]

    tokens_before = current_tokens
    summary_text = await llm_generate_fn(summary_prompt, max_tokens=400)

    summary_message = {
        "role":    "system",
        "content": f"[Earlier conversation — compacted]\n{summary_text}",
    }
    session["history"] = [summary_message] + recent_messages
    tokens_after = estimate_tokens(session["history"])

    logger.info(
        f"[compaction] Auto-compact ran for session={session_id} | "
        f"tokens {tokens_before} → {tokens_after}"
    )

    # Persist to CRM for cross-session recall
    user_id = session.get("user_id")
    if user_id:
        try:
            from src.tools.crm import update_profile
            await update_profile(user_id, {"last_session_summary": summary_text})
        except Exception as e:
            logger.warning(f"[compaction] CRM summary update failed: {e}")

        # Audit log (fire-and-forget, errors must not propagate)
        try:
            await db.log_compaction(session_id, user_id, "auto", tokens_before, tokens_after)
        except Exception as e:
            logger.warning(f"[compaction] log_compaction failed: {e}")

    return True


# ---------------------------------------------------------------------------
# LAYER 4 — BACKGROUND CRM EXTRACTION (Async, Non-Blocking)
# ---------------------------------------------------------------------------
EXTRACTION_EVERY_N_TURNS = 1


async def maybe_extract_to_crm(session: dict, llm_generate_fn, session_id: str = None) -> None:
    """
    Increment turn counter. Every N turns, fire background CRM extraction.
    Uses asyncio.create_task — never awaited from the main turn handler.
    session_id is passed so the background task can refresh the CRM cache
    block immediately after writing new data to the DB.
    """
    session["turn_count"] = session.get("turn_count", 0) + 1
    user_id = session.get("user_id")
    if not user_id:
        return  # Anonymous session — nothing to extract to

    # CRITICAL: Persist updated turn_count back to Redis or it resets every call
    if session_id:
        from src.conversation.memory import _save_to_redis
        _save_to_redis(session_id, session)

    if session["turn_count"] % EXTRACTION_EVERY_N_TURNS != 0:
        return

    # Snapshot recent messages before task runs (avoid mutation races)
    recent_snapshot = list(session.get("history", [])[-10:])
    logger.info(f"[extraction] Triggering background CRM extraction for user={user_id}, turn={session['turn_count']}")
    asyncio.create_task(
        _background_extract(user_id, recent_snapshot, llm_generate_fn, session_id=session_id)
    )


def _extract_json_object(raw: str) -> dict:
    """Extract the first valid {...} JSON object from LLM output, ignoring markdown fences and prose."""
    import re
    # Strip markdown fences
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    raw = re.sub(r"```\s*$", "", raw).strip()
    # Try direct parse first
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    # Brace-depth matching to extract first {...}
    start = raw.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except (json.JSONDecodeError, ValueError):
                    return {}
    return {}


_VALID_CRM_KEYS = {"name", "preferred_categories", "budget_range", "liked_brands", "disliked_brands", "notes"}


async def _background_extract(
    user_id: str,
    messages: list[dict],
    llm_generate_fn,
    session_id: str = None,
) -> None:
    """
    Runs silently in background. ALL exceptions are caught and logged.
    Never allowed to propagate — must never crash the session.
    After a successful update, refreshes the session's CRM cache block
    so the next turn immediately has the updated preferences in context.
    """
    history = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')}"
        for m in messages
        if m.get("role") in ("user", "assistant")
        and not str(m.get("content", "")).startswith("[")   # skip placeholders
    )

    if not history.strip():
        return

    prompt = [
        {
            "role": "user",
            "content": (
                "Analyze this Daraz shopping conversation. Extract any NEW user preferences.\n"
                "Return a JSON object with ONLY fields that are new or changed.\n"
                "Valid fields: name (string), preferred_categories (list of strings), budget_range (string), "
                "liked_brands (list of strings), disliked_brands (list of strings), notes (string).\n"
                "If nothing new found, return exactly: {}\n"
                "Return ONLY the raw JSON object. No markdown. No explanation.\n"
                "Example: {\"name\": \"Ali\", \"liked_brands\": [\"Samsung\"]}\n\n"
                f"Conversation:\n{history}"
            ),
        }
    ]

    try:
        # No timeout — extraction LLM call takes as long as it needs.
        # This runs after the user already has their response, so latency is irrelevant.
        raw = await llm_generate_fn(prompt, max_tokens=200)
        logger.info(f"[extraction] Raw LLM output for {user_id}: {raw[:120]!r}")
        updates = _extract_json_object(raw)
        # Filter to only valid CRM keys with non-empty values
        updates = {k: v for k, v in updates.items() if k in _VALID_CRM_KEYS and v}
        if not updates:
            logger.info(f"[extraction] No new CRM fields extracted for {user_id}")
            return
        from src.tools.crm import update_profile
        await update_profile(user_id, updates)
        logger.info(f"[extraction] ✅ Background CRM updated for {user_id}: {updates}")
        # Immediately refresh the session's CRM cache so next turn has updated preferences
        if session_id:
            from src.conversation.memory import refresh_crm_block
            await refresh_crm_block(session_id)
            logger.info(f"[extraction] CRM block refreshed for session={session_id} after background update")
    except json.JSONDecodeError as e:
        logger.warning(f"[extraction] JSON parse failed for {user_id}: {e}")
    except Exception as e:
        logger.warning(f"[extraction] Silently failed for {user_id}: {e}")
        # Never re-raise — background task must not crash the session

