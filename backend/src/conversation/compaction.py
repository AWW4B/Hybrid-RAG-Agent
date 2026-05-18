"""
compaction.py — The 3-Layer Brain LLM (Compaction Engine).

Runs entirely in the background after every chat turn.
Never blocks the streaming Chat LLM.

Layer 2: Micro-Compaction — scrub large tool payloads already consumed.
Layer 3: Auto-Compaction — if tokens > 78% of context window, summarize
         older turns via the Brain LLM, keeping the 3 most recent intact.
Layer 4: CRM Extraction — extract structured CRM updates from the latest
         exchange and merge into the user profile.

CRITICAL: Layer 3 and 4 must NEVER run concurrently with the Chat LLM
because llama-cpp is NOT thread-safe. They are deferred until the streaming
response finishes (coordinated via a lock in llm.py).
"""

import re
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from config import (
    COMPACTION_TRIGGER_PCT,
    TOOL_PAYLOAD_MAX_CHARS,
    RECENT_TURNS_TO_KEEP,
    CHARS_PER_TOKEN_ESTIMATE,
    LLM_N_CTX,
    LLM_BRAIN_TEMP,
    LLM_MAX_TOKENS_BRAIN,
)
from conversation import memory
from tools.crm import merge_crm
import db

logger = logging.getLogger(__name__)

_llm_instance = None
_executor: Optional[ThreadPoolExecutor] = None

# Lock to serialize LLM access (prevents segfault from concurrent llama-cpp calls)
_llm_lock: Optional[asyncio.Lock] = None


def init_compaction(llm_instance, executor: ThreadPoolExecutor) -> None:
    global _llm_instance, _executor, _llm_lock
    _llm_instance = llm_instance
    _executor = executor
    _llm_lock = asyncio.Lock()
    logger.info("[compaction] Engine initialized.")


def get_llm_lock() -> asyncio.Lock:
    """Return the LLM lock so llm.py can acquire it during streaming."""
    return _llm_lock


def _estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN_ESTIMATE)


def _estimate_history_tokens(history: list[dict]) -> int:
    return sum(_estimate_tokens(m["content"]) for m in history)


# ── LAYER 2: MICRO-COMPACTION ──────────────────────────────────────

SCRUB_MARKER = "[Tool result cleared — response already incorporates this output]"

_TOOL_TAG_RE = re.compile(
    r"(<TOOL_CALL>.*?</TOOL_CALL>|\[Retrieved Knowledge Context\].*?(?=\n\[|\Z)|\[Tool Output:.*?\].*?(?=\n\[|\Z))",
    re.DOTALL,
)


def _run_micro_compaction(session_id: str) -> bool:
    history = memory.get_history(session_id)
    changed = False
    for i, msg in enumerate(history):
        if msg["role"] != "user":
            continue
        has_response = any(history[j]["role"] == "assistant" for j in range(i + 1, len(history)))
        if not has_response:
            continue
        content = msg["content"]
        for match in _TOOL_TAG_RE.finditer(content):
            payload = match.group(0)
            if len(payload) > TOOL_PAYLOAD_MAX_CHARS:
                content = content.replace(payload, SCRUB_MARKER, 1)
                changed = True
        if changed:
            msg["content"] = content
    if changed:
        logger.info(f"[compaction] L2 micro-compacted session {session_id[:8]}")
    return changed


# ── LAYER 3: AUTO-COMPACTION ───────────────────────────────────────

_SUMMARY_PROMPT = (
    "You are a memory compaction engine. Write a FACTUAL, CONCISE bullet-point summary of this conversation. "
    "Preserve all product names, prices, quantities, user preferences, and decisions. "
    "Do NOT hallucinate.\n\nCONVERSATION:\n{conversation}\n\nFACTUAL SUMMARY:"
)


def _run_auto_compaction_sync(session_id: str) -> None:
    """MUST be called only when the LLM lock is held."""
    if _llm_instance is None:
        return
    history = memory.get_history(session_id)
    total_tokens = _estimate_history_tokens(history)
    threshold = int(LLM_N_CTX * COMPACTION_TRIGGER_PCT)
    if total_tokens < threshold:
        logger.info(f"[compaction] L3 skip: {total_tokens} tokens < {threshold} threshold")
        return
    logger.info(f"[compaction] L3 triggered: {total_tokens} tokens >= {threshold}")

    keep_count = RECENT_TURNS_TO_KEEP * 2
    if len(history) <= keep_count:
        return
    old_messages = history[:-keep_count]
    recent_messages = history[-keep_count:]

    conversation_text = "\n".join(f"{m['role'].upper()}: {m['content'][:500]}" for m in old_messages)
    prompt = _SUMMARY_PROMPT.format(conversation=conversation_text)

    try:
        result = _llm_instance.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_BRAIN_TEMP,
            max_tokens=LLM_MAX_TOKENS_BRAIN,
        )
        summary = result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[compaction] L3 Brain LLM failed: {e}")
        summary = "Previous conversation context was auto-compacted."

    memory.set_context(session_id, summary)
    memory.set_history(session_id, recent_messages)
    logger.info(f"[compaction] L3 done: compacted {len(old_messages)} msgs")


# ── LAYER 4: CRM EXTRACTION ───────────────────────────────────────

_CRM_PROMPT = (
    "You are a JSON extractor. Output ONLY a valid JSON object, no prose, no explanation.\n"
    "Extract NEW or UPDATED customer info from this exchange.\n"
    "Fields: name (str), location (str), budget_range (str), "
    "preferred_categories (list of str), preferred_brands (list of str), "
    "language_preference (str), "
    "shipping_addresses (list of objects with: label, address, city, is_default bool), "
    "notes (str).\n"
    "If the user mentions a shipping address or delivery location, extract it.\n"
    "If nothing new is present, output exactly: {{}}\n\n"
    "CURRENT CRM: {crm}\n\nUSER: {user_msg}\nASSISTANT: {asst_msg}\n\nJSON:"
)


def _run_crm_extraction_sync(session_id: str) -> None:
    """MUST be called only when the LLM lock is held."""
    if _llm_instance is None:
        logger.warning("[compaction] L4 skip: no LLM instance")
        return
    user_id = memory.get_session_owner(session_id)
    if not user_id:
        logger.warning(f"[compaction] L4 skip: no owner for session {session_id[:8]}")
        return
    history = memory.get_history(session_id)
    if len(history) < 2:
        logger.info(f"[compaction] L4 skip: history too short ({len(history)} msgs)")
        return

    last_user = last_asst = ""
    for msg in reversed(history):
        if msg["role"] == "assistant" and not last_asst:
            last_asst = msg["content"]
        elif msg["role"] == "user" and not last_user:
            last_user = msg["content"]
        if last_user and last_asst:
            break
    if not last_user:
        logger.info("[compaction] L4 skip: no user message found")
        return

    current_crm = memory.get_crm(user_id)
    prompt = _CRM_PROMPT.format(
        crm=json.dumps(current_crm, ensure_ascii=False),
        user_msg=last_user[:800],
        asst_msg=last_asst[:800],
    )
    logger.info(f"[compaction] L4 running CRM extraction for user {user_id[:8]}...")
    try:
        result = _llm_instance.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_BRAIN_TEMP,
            max_tokens=300,
        )
        raw = result["choices"][0]["message"]["content"].strip()

        # Extract JSON object from the raw response (model often wraps in prose)
        import re as _re
        json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if not json_match:
            logger.info(f"[compaction] L4 CRM: no JSON object found in response. Raw: {raw[:200]}")
            return

        updates = json.loads(json_match.group(0))
        if isinstance(updates, dict) and updates:
            merged = merge_crm(current_crm, updates)
            memory.set_crm(user_id, merged)
            logger.info(f"[compaction] L4 CRM updated: {list(updates.keys())} → {json.dumps(merged, ensure_ascii=False)[:200]}")
        else:
            logger.info("[compaction] L4 CRM extraction returned empty — no updates.")
    except json.JSONDecodeError as e:
        logger.warning(f"[compaction] L4 CRM JSON parse failed: {e}, raw: {raw[:200] if 'raw' in dir() else 'N/A'}")
    except Exception as e:
        logger.error(f"[compaction] L4 failed: {e}", exc_info=True)


# ── PUBLIC ENTRY POINT ─────────────────────────────────────────────

async def run_background_compaction(session_id: str) -> None:
    """
    Called after the streaming response is FULLY complete.
    Acquires the LLM lock to ensure no concurrent llama-cpp calls.
    """
    loop = asyncio.get_running_loop()

    # Layer 2: Micro-compaction (no LLM needed, safe to run anytime)
    await loop.run_in_executor(_executor, _run_micro_compaction, session_id)

    # Layers 3 & 4: Need the LLM — acquire lock first
    if _llm_lock:
        async with _llm_lock:
            logger.info(f"[compaction] LLM lock acquired for session {session_id[:8]}")

            def _brain_work():
                try:
                    _run_auto_compaction_sync(session_id)
                    _run_crm_extraction_sync(session_id)
                except Exception as e:
                    logger.error(f"[compaction] Brain work failed: {e}", exc_info=True)

            await loop.run_in_executor(_executor, _brain_work)
            logger.info(f"[compaction] Brain work complete for session {session_id[:8]}")

    # Persist to DB
    await _persist_async(session_id)


async def _persist_async(session_id: str) -> None:
    """Persist compaction results to DB using the existing event loop."""
    try:
        user_id = memory.get_session_owner(session_id)
        ctx = memory.get_context(session_id)
        if ctx:
            await db.update_session_context(session_id, ctx)
            logger.info(f"[compaction] Persisted context for session {session_id[:8]}")

        if user_id:
            crm = memory.get_crm(user_id)
            if crm and any(v for v in crm.values()):
                await db.upsert_crm(user_id, crm)
                logger.info(f"[compaction] Persisted CRM for user {user_id[:8]}")
    except Exception as e:
        logger.error(f"[compaction] Persist failed: {e}", exc_info=True)
