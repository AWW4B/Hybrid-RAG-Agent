"""
llm.py — The Chat Engine with flawless parallel execution.

Thread A (foreground): Streams Chat LLM tokens to the client.
Thread B (background): Fires the Brain LLM compaction engine AFTER streaming.
Both NEVER run simultaneously — coordinated via asyncio.Lock.
"""

import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from llama_cpp import Llama

from config import (
    LLM_MODEL_PATH,
    LLM_N_CTX,
    LLM_N_THREADS,
    LLM_N_GPU_LAYERS,
    LLM_CHAT_TEMP,
    LLM_MAX_TOKENS_CHAT,
)
from conversation import memory
from conversation.compaction import run_background_compaction, init_compaction, get_llm_lock
from tools.orchestrator import run_orchestrator, init_orchestrator
import db

logger = logging.getLogger(__name__)

# ── Shared resources ────────────────────────────────────────────────
_llm: Llama | None = None
_executor: ThreadPoolExecutor | None = None


# ════════════════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN
# ════════════════════════════════════════════════════════════════════

def startup() -> None:
    """Load the LLM and create the thread pool. Called once at app boot."""
    global _llm, _executor

    n_threads = LLM_N_THREADS or os.cpu_count() or 4
    _executor = ThreadPoolExecutor(max_workers=max(4, n_threads))

    logger.info(f"[llm] Loading model: {LLM_MODEL_PATH}")
    _llm = Llama(
        model_path=LLM_MODEL_PATH,
        n_ctx=LLM_N_CTX,
        n_threads=n_threads,
        n_gpu_layers=LLM_N_GPU_LAYERS,
        verbose=False,
    )
    logger.info(f"[llm] Model loaded. Context: {LLM_N_CTX}, Threads: {n_threads}")

    # Wire up subsystems
    init_compaction(_llm, _executor)
    init_orchestrator(_executor)


def shutdown() -> None:
    global _llm, _executor
    if _executor:
        _executor.shutdown(wait=False)
        _executor = None
    _llm = None
    logger.info("[llm] Shutdown complete.")


# ════════════════════════════════════════════════════════════════════
#  CHAT STREAMING  (the hot path)
# ════════════════════════════════════════════════════════════════════

async def stream_chat(
    session_id: str,
    user_prompt: str,
    on_tool_start=None,
    on_tool_done=None,
) -> AsyncGenerator[str, None]:
    """
    The main entry point for a chat turn.

    1. Append user message to RAM history.
    2. Run the orchestrator to get tool context (sends tool status to frontend).
    3. Build the full prompt array.
    4. STREAM Chat LLM tokens back via async generator (under LLM lock).
    5. After streaming completes, fire background compaction (also under lock).
    """
    # Step 1: Record the user message in RAM
    memory.append_message(session_id, "user", user_prompt)

    # Step 2: Orchestrator — get tool context (runs in thread pool)
    if on_tool_start:
        await on_tool_start()

    tool_context = await run_orchestrator(user_prompt)

    if on_tool_done:
        await on_tool_done(tool_context)

    if tool_context:
        logger.info(f"[llm] Tool context: {len(tool_context)} chars")

    # Step 3: Build prompt messages
    messages = memory.build_prompt_messages(session_id, tool_context)

    # Log the system prompt for debugging CRM injection
    system_msg = messages[0]["content"] if messages else ""
    if "[Customer Profile]" in system_msg:
        logger.info(f"[llm] CRM injected into system prompt ✓")
    else:
        logger.info(f"[llm] No CRM profile in system prompt")

    # Step 4: Stream the Chat LLM (acquire lock to prevent concurrent access)
    full_response = []
    loop = asyncio.get_running_loop()
    llm_lock = get_llm_lock()

    chunks_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async with llm_lock:
        logger.info(f"[llm] LLM lock acquired for streaming ({session_id[:8]})")

        def _generate():
            """Run the blocking LLM generation in a thread, pushing chunks."""
            try:
                for chunk in _llm.create_chat_completion(
                    messages=messages,
                    temperature=LLM_CHAT_TEMP,
                    max_tokens=LLM_MAX_TOKENS_CHAT,
                    stream=True,
                ):
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        loop.call_soon_threadsafe(chunks_queue.put_nowait, token)

                # Signal end of stream
                loop.call_soon_threadsafe(chunks_queue.put_nowait, None)
            except Exception as e:
                logger.error(f"[llm] Generation error: {e}", exc_info=True)
                loop.call_soon_threadsafe(chunks_queue.put_nowait, None)

        # Start generation in thread pool
        _executor.submit(_generate)

        # Yield tokens as they arrive
        while True:
            token = await chunks_queue.get()
            if token is None:
                break
            full_response.append(token)
            yield token

    # Lock released after streaming completes
    logger.info(f"[llm] LLM lock released ({session_id[:8]})")

    # Step 5: Save assistant response to RAM + DB
    assistant_text = "".join(full_response)
    if assistant_text:
        memory.append_message(session_id, "assistant", assistant_text)

        # Persist messages to DB (fire-and-forget)
        asyncio.create_task(_save_messages_to_db(session_id, user_prompt, assistant_text))

    # Step 6: Fire background compaction AFTER streaming (will acquire its own lock)
    asyncio.create_task(_safe_compaction(session_id))


async def _safe_compaction(session_id: str) -> None:
    """Wrapper to catch any compaction errors without crashing."""
    try:
        await run_background_compaction(session_id)
    except Exception as e:
        logger.error(f"[llm] Background compaction error: {e}", exc_info=True)


async def _save_messages_to_db(session_id: str, user_msg: str, asst_msg: str) -> None:
    """Persist the turn to the database asynchronously."""
    try:
        await db.save_message(session_id, "user", user_msg)
        await db.save_message(session_id, "assistant", asst_msg)
        await db.touch_session(session_id)
        logger.info(f"[llm] Messages persisted to DB for session {session_id[:8]}")
    except Exception as e:
        logger.error(f"[llm] DB save failed: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════
#  NON-STREAMING CHAT  (for /voice endpoint)
# ════════════════════════════════════════════════════════════════════

async def generate_response(session_id: str, user_prompt: str) -> str:
    """Non-streaming version — collects full response and returns it."""
    chunks = []
    async for token in stream_chat(session_id, user_prompt):
        chunks.append(token)
    return "".join(chunks)


# ════════════════════════════════════════════════════════════════════
#  WARMUP
# ════════════════════════════════════════════════════════════════════

async def warmup() -> str:
    """Pre-heat the model with a trivial generation to eliminate first-call latency."""
    if not _llm:
        return "Model not loaded"

    llm_lock = get_llm_lock()
    async with llm_lock:
        loop = asyncio.get_running_loop()

        def _run():
            _llm.create_chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
            )
            return "warm"

        result = await loop.run_in_executor(_executor, _run)
    logger.info("[llm] Warmup complete.")
    return result
