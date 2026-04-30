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

    # Audit log (fire-and-forget, errors must not propagate)
    user_id = session.get("user_id")
    if user_id:
        try:
            await db.log_compaction(session_id, user_id, "auto", tokens_before, tokens_after)
        except Exception as e:
            logger.warning(f"[compaction] log_compaction failed: {e}")

    return True



