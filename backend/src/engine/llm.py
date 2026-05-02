"""
llm.py — The Chat Engine with flawless parallel execution.

Thread A (foreground): Streams Chat LLM tokens to the client.
Thread B (background): Fires the Brain LLM compaction engine AFTER streaming.
Both NEVER run simultaneously — coordinated via asyncio.Lock.
"""

import io
import os
import logging
import asyncio
import tempfile
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Optional

from llama_cpp import Llama

from config import (
    LLM_MODEL_PATH,
    LLM_N_CTX,
    LLM_N_THREADS,
    LLM_N_GPU_LAYERS,
    LLM_CHAT_TEMP,
    LLM_MAX_TOKENS_CHAT,
    PIPER_MODEL_PATH,
    WHISPER_MODEL,
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
#  VOICE — STT (faster-whisper) + TTS (Piper)
# ════════════════════════════════════════════════════════════════════

_tts_model = None
_tts_lock  = threading.Lock()
_stt_model = None
_stt_lock  = threading.Lock()


def _get_tts():
    global _tts_model
    if _tts_model is None:
        with _tts_lock:
            if _tts_model is None:
                from piper import PiperVoice
                logger.info(f"[voice] Loading Piper TTS: {PIPER_MODEL_PATH}")
                _tts_model = PiperVoice.load(PIPER_MODEL_PATH)
                logger.info("[voice] Piper TTS loaded.")
    return _tts_model


def _get_stt():
    """Lazy-load faster-whisper STT model (CPU, tiny model ~40MB)."""
    global _stt_model
    if _stt_model is None:
        with _stt_lock:
            if _stt_model is None:
                from faster_whisper import WhisperModel
                logger.info(f"[voice] Loading faster-whisper STT model: {WHISPER_MODEL}")
                _stt_model = WhisperModel(
                    WHISPER_MODEL,
                    device="cpu",
                    compute_type="int8",
                    download_root="/models/whisper",
                )
                logger.info("[voice] faster-whisper STT loaded.")
    return _stt_model


async def transcribe_audio(audio_bytes: bytes, session_id: str) -> str:
    """faster-whisper STT: audio bytes → transcript string."""
    logger.info(f"[voice] STT called | session={session_id[:8]} | {len(audio_bytes)} bytes")

    def _run() -> str:
        import subprocess

        suffix = ".wav" if audio_bytes[:4] == b"RIFF" else ".webm"
        tmp_path = None
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wtmp:
                wav_path = wtmp.name

            # Convert to 16kHz mono WAV for whisper
            ret = subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_path, "-ac", "1", "-ar", "16000",
                 "-sample_fmt", "s16", wav_path],
                capture_output=True, text=True,
            )
            if ret.returncode != 0:
                logger.error(f"[voice] ffmpeg error: {ret.stderr[:300]}")
                return ""

            model = _get_stt()
            logger.info(f"[voice] Transcribing {wav_path}...")
            segments, info = model.transcribe(wav_path, beam_size=1, language="en")
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            logger.info(f"[voice] Transcript: '{transcript}' (lang={info.language}, prob={info.language_probability:.2f})")
            return transcript
        except Exception as e:
            logger.error(f"[voice] STT failed: {e}", exc_info=True)
            return ""
        finally:
            for p in (tmp_path, wav_path):
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except OSError: pass

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _run)


async def synthesize_speech(text: str, session_id: str) -> bytes:
    """Piper TTS: text → WAV audio bytes."""
    tts = _get_tts()

    def _run() -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(tts.config.sample_rate)
            tts.synthesize(text, wf)
        return buf.getvalue()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _run)


async def process_audio(session_id: str, audio_bytes: bytes) -> tuple[bytes, str, str]:
    """Full voice pipeline: audio → STT → LLM → TTS → audio."""
    # Step 1: Transcribe (no LLM needed)
    user_text = await transcribe_audio(audio_bytes, session_id)
    if not user_text.strip():
        reply = "I didn't catch that — could you try again?"
        audio_resp = await synthesize_speech(reply, session_id)
        return audio_resp, "", reply

    logger.info(f"[voice] Generating response for: '{user_text[:80]}'")

    # Step 2: LLM generation (collects all tokens)
    assistant_text = await generate_response(session_id, user_text)
    logger.info(f"[voice] LLM response: '{assistant_text[:80]}'")

    # Step 3: TTS (no LLM needed)
    audio_response = await synthesize_speech(assistant_text, session_id)
    logger.info(f"[voice] TTS done: {len(audio_response)} bytes")

    return audio_response, user_text, assistant_text


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
