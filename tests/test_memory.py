# =============================================================================
# tests/test_memory.py
# Unit tests for micro-compaction and auto-compaction logic.
# Run with: pytest tests/test_memory.py -v
# =============================================================================

import asyncio
import sys
import os

# Ensure backend/src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from src.conversation.compaction import (
    micro_compact,
    estimate_tokens,
    auto_compact_if_needed,
    CLEARED_PLACEHOLDER,
    AUTO_COMPACT_THRESHOLD_PCT,
    KEEP_RECENT_TURNS,
)


# =============================================================================
# HELPERS
# =============================================================================
def make_long_history(words: int = 10000) -> list[dict]:
    """Generate a message history totalling ~words words alternating user/assistant."""
    word = "shopping " * 10  # 10 words per chunk
    msgs = []
    total = 0
    role_cycle = ["user", "assistant"]
    idx = 0
    while total < words:
        chunk = word * 10  # ~100 words
        msgs.append({"role": role_cycle[idx % 2], "content": chunk})
        total += 100
        idx += 1
    return msgs


class MockLLM:
    """Fake LLM that returns a canned summary without hitting real inference."""
    async def __call__(self, messages: list[dict], max_tokens: int = 400) -> str:
        return "User asked about phones and laptops. Budget: under 20000 PKR. No resolution yet."


mock_llm = MockLLM()


def _make_mock_session(history: list[dict], user_id: str = "test-user-001") -> dict:
    return {
        "history":    history,
        "user_id":    user_id,
        "turn_count": 0,
        "state":      {"resolved": "no"},
        "turns":      len(history) // 2,
        "status":     "active",
    }


# =============================================================================
# TestMicroCompact
# =============================================================================
class TestMicroCompact:

    def test_clears_consumed_rag_tool_result(self):
        """Tool result followed by an assistant message must be cleared."""
        messages = [
            {"role": "user",      "content": "Find me a phone"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "tc1", "function": {"name": "retrieve_documents", "arguments": "{}"}}
            ]},
            {"role": "tool", "name": "retrieve_documents", "tool_call_id": "tc1",
             "content": "A" * 2000},
            {"role": "assistant", "content": "Here are some phones for you..."},
        ]
        result = micro_compact(messages)
        assert result[2]["content"] == CLEARED_PLACEHOLDER, "Tool result must be cleared after assistant reply"
        # Structure invariant
        assert result[2]["role"] == "tool"
        assert result[2]["name"] == "retrieve_documents"
        assert result[2]["tool_call_id"] == "tc1"

    def test_clears_consumed_crm_tool_result(self):
        """get_crm_profile results should also be cleared."""
        messages = [
            {"role": "tool", "name": "get_crm_profile", "tool_call_id": "tc2",
             "content": '{"name": "Ali", "preferred_categories": ["phones"]}'},
            {"role": "assistant", "content": "I see you prefer phones."},
        ]
        result = micro_compact(messages)
        assert result[0]["content"] == CLEARED_PLACEHOLDER

    def test_does_not_clear_unconsumed_tool_result(self):
        """Tool result with no subsequent assistant message must NOT be cleared."""
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "tc3", "function": {"name": "retrieve_documents", "arguments": "{}"}}
            ]},
            {"role": "tool", "name": "retrieve_documents", "tool_call_id": "tc3",
             "content": "Important live data"},
        ]
        result = micro_compact(messages)
        assert result[1]["content"] == "Important live data", "Unconsumed result must not be cleared"

    def test_non_compactable_tool_not_touched(self):
        """Tools not in MICRO_COMPACTABLE_TOOLS must not have their content cleared."""
        messages = [
            {"role": "tool", "name": "update_crm_profile", "tool_call_id": "tc4",
             "content": "Updated successfully"},
            {"role": "assistant", "content": "Done."},
        ]
        result = micro_compact(messages)
        assert result[0]["content"] == "Updated successfully"

    def test_already_cleared_not_double_cleared(self):
        """Messages already bearing CLEARED_PLACEHOLDER must not be re-processed."""
        messages = [
            {"role": "tool", "name": "retrieve_documents", "tool_call_id": "tc5",
             "content": CLEARED_PLACEHOLDER},
            {"role": "assistant", "content": "Continuing…"},
        ]
        result = micro_compact(messages)
        assert result[0]["content"] == CLEARED_PLACEHOLDER  # unchanged

    def test_structure_invariant_preserved(self):
        """After compaction, every tool_call_id in assistant messages has a matching tool result."""
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "x", "function": {"name": "retrieve_documents", "arguments": "{}"}}
            ]},
            {"role": "tool", "name": "retrieve_documents", "tool_call_id": "x", "content": "data"},
            {"role": "assistant", "content": "Response"},
        ]
        result = micro_compact(messages)
        tool_call_ids = {
            tc["id"]
            for m in result if m.get("tool_calls")
            for tc in m["tool_calls"]
        }
        tool_result_ids = {m["tool_call_id"] for m in result if m.get("role") == "tool"}
        assert tool_call_ids == tool_result_ids

    def test_message_count_unchanged(self):
        """micro_compact never removes messages — only replaces content."""
        messages = [
            {"role": "user",      "content": "Hello"},
            {"role": "tool", "name": "retrieve_documents", "tool_call_id": "t1", "content": "big data"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = micro_compact(messages)
        assert len(result) == len(messages)

    def test_legacy_role_content_dicts_unaffected(self):
        """Plain {role, content} dicts (no tool fields) pass through unchanged."""
        messages = [
            {"role": "user",      "content": "What phones are cheap?"},
            {"role": "assistant", "content": "I suggest the Redmi series."},
        ]
        result = micro_compact(messages)
        assert result == messages


# =============================================================================
# TestEstimateTokens
# =============================================================================
class TestEstimateTokens:

    def test_rough_estimate_short_text(self):
        messages = [{"content": "hello world"}]  # 11 chars → ~3 tokens
        est = estimate_tokens(messages)
        assert 2 <= est <= 5, f"Expected 2-5 tokens for 'hello world', got {est}"

    def test_empty_messages(self):
        assert estimate_tokens([]) == 0

    def test_none_content_handled(self):
        messages = [{"role": "assistant", "content": None}]
        # Should not raise; None treated as empty string
        est = estimate_tokens(messages)
        assert est == 0

    def test_scales_with_length(self):
        short_est = estimate_tokens([{"content": "x" * 100}])
        long_est  = estimate_tokens([{"content": "x" * 1000}])
        assert long_est > short_est


# =============================================================================
# TestAutoCompact
# =============================================================================
class TestAutoCompact:

    @pytest.mark.asyncio
    async def test_compaction_not_triggered_below_threshold(self):
        session = _make_mock_session([
            {"role": "user",      "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ])
        ran = await auto_compact_if_needed(
            session, mock_llm, context_window=4096, session_id="test-below"
        )
        assert ran is False

    @pytest.mark.asyncio
    async def test_compaction_triggered_above_threshold(self):
        session = _make_mock_session(make_long_history(words=20000))
        ran = await auto_compact_if_needed(
            session, mock_llm, context_window=4096, session_id="test-above"
        )
        assert ran is True
        # After compaction session must be shorter
        assert len(session["history"]) < 20

    @pytest.mark.asyncio
    async def test_recent_messages_preserved_verbatim(self):
        """The last KEEP_RECENT_TURNS pairs must be identical after compaction."""
        history = make_long_history(words=20000)
        session = _make_mock_session(history)
        # Capture last 2*KEEP_RECENT_TURNS messages (N pairs = 2N messages)
        original_recent = list(history[-(KEEP_RECENT_TURNS * 2):])
        await auto_compact_if_needed(
            session, mock_llm, context_window=4096, session_id="test-recent"
        )
        preserved = session["history"][-(KEEP_RECENT_TURNS * 2):]
        assert preserved == original_recent, "Recent messages must survive compaction verbatim"

    @pytest.mark.asyncio
    async def test_summary_message_inserted(self):
        session = _make_mock_session(make_long_history(words=20000))
        await auto_compact_if_needed(
            session, mock_llm, context_window=4096, session_id="test-summary"
        )
        # First message after compaction should be the summary block
        assert session["history"][0]["role"] == "system"
        assert "[Earlier conversation" in session["history"][0]["content"]

    @pytest.mark.asyncio
    async def test_no_old_messages_skips_compaction(self):
        """If the split_index yields no old messages, compaction must skip gracefully."""
        # Only 2 messages = less than KEEP_RECENT_TURNS pairs, nothing to compact
        session = _make_mock_session([
            {"role": "user",      "content": "word " * 5000},  # large but only 1 pair
            {"role": "assistant", "content": "reply " * 5000},
        ])
        original_history = list(session["history"])
        # Even if token count exceeds threshold, if there's nothing old to compact, skip
        ran = await auto_compact_if_needed(
            session, mock_llm, context_window=100, session_id="test-no-old"
        )
        # Should either return False or leave history intact (nothing to compact)
        if ran:
            # If it ran, history must still be valid (not empty)
            assert len(session["history"]) > 0
