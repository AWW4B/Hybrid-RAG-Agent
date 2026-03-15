# =============================================================================
# llm/engine.py
# Awwab — A3 refactor: replaced text generation with audio pipeline stubs.
#
# Architecture (Voice-to-Voice pipeline):
#   audio_bytes → [STT] → text → [LLM] → text → [TTS] → audio_bytes
#
# Uwaid owns model selection and implementation for all three stages.
# Awwab owns the orchestration layer (this file) and the WebSocket plumbing.
#
# Each stage is an isolated async function with a clear signature.
# Engine.process_audio() chains them together — routes.py calls only this.
# =============================================================================

import logging
import time
import asyncio
from typing import Optional, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from llama_cpp import Llama

from app.core.config import MAX_TURNS, MAX_TOKENS
from app.memory.context import (
    build_inference_payload,
    add_message_to_chat,
    extract_and_strip_state,
    increment_turn,
    is_session_maxed,
    get_session_status,
    set_session_status,
    is_conversation_resolved,
    get_or_create_session,
)

logger = logging.getLogger(__name__)

# Thread pool for blocking model inference (keeps async event loop free)
_executor = ThreadPoolExecutor(max_workers=1)


# =============================================================================
# STAGE 1 — SPEECH-TO-TEXT
# TODO Uwaid: Implement local Whisper STT here.
#
# Suggested approach:
#   - Use faster-whisper (CTranslate2 backend) for CPU-efficient transcription.
#   - Recommended model: "base" or "small" for sub-second latency on CPU.
#   - Load model once at module level (not inside the function).
#   - Run inference in _executor to avoid blocking the event loop.
#
# Example skeleton:
#   from faster_whisper import WhisperModel
#   _stt_model = WhisperModel("small", device="cpu", compute_type="int8")
# =============================================================================

async def transcribe_audio(audio_bytes: bytes, session_id: str) -> str:
    """
    Converts raw audio bytes (WebM/PCM from the browser) to a text transcript.

    Args:
        audio_bytes: Raw audio data received over WebSocket.
        session_id : Active session ID (for logging/tracing).

    Returns:
        Transcribed text string.

    # TODO Uwaid: Replace the placeholder below with real Whisper inference.
    #   1. Write audio_bytes to a temp file (or use io.BytesIO if model supports it).
    #   2. Run _stt_model.transcribe() in _executor (it's CPU-blocking).
    #   3. Join segments and return the transcript string.
    #   4. Handle empty/silence detection — return "" and let the caller skip LLM.
    """
    logger.info(f"[engine] STT stub called | session={session_id} | {len(audio_bytes)} bytes")

    # TODO Uwaid: Remove this placeholder and implement real transcription.
    raise NotImplementedError("STT not implemented yet — Uwaid's task.")


# =============================================================================
# STAGE 2 — LLM TEXT GENERATION
# The business logic (context window, STATE extraction, lifecycle) from A2 is
# preserved here. Uwaid should NOT need to touch this stage.
#
# If Uwaid wants to swap the LLM model, change _load_model() below and update
# MODEL_PATH / generation parameters in config.py.
# =============================================================================

# Load the LLM using llama-cpp-python (imported from A2)
import os
from app.core.config import N_CTX, N_THREADS, N_BATCH

# Read MODEL_PATH from env (set in docker-compose.yml to qwen2.5-3b-instruct-q4_k_m.gguf)
_model_path = os.getenv("MODEL_PATH", "/models/qwen2.5-3b-instruct-q4_k_m.gguf")

logger.info(f"[engine] Loading LLM model from: {_model_path}")
try:
    _llm = Llama(
        model_path=_model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_batch=N_BATCH,
        n_gpu_layers=0,  # CPU-only for this assignment
        verbose=False,
    )
    logger.info("✅ [engine] LLM model loaded successfully.")
except Exception as e:
    logger.error(f"❌ [engine] LLM load failed: {e}")
    _llm = None


async def _generate_text(session_id: str, user_text: str) -> str:
    """
    Internal: runs the LLM and returns the clean assistant reply (STATE stripped).
    Delegates to the thread pool so the async loop stays free during inference.
    """
    if _llm is None:
        raise RuntimeError("LLM not loaded. Uwaid: assign a model instance to _llm.")

    from app.core.config import build_chatml_prompt, TEMPERATURE, TOP_P, REPEAT_PENALTY

    messages = build_inference_payload(session_id, user_text)
    prompt   = build_chatml_prompt(messages)

    loop = asyncio.get_event_loop()

    raw_response = await loop.run_in_executor(
        _executor,
        lambda: "".join(
            chunk["choices"][0]["text"]
            for chunk in _llm(
                prompt,
                max_tokens=MAX_TOKENS,
                stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
                echo=False,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                repeat_penalty=REPEAT_PENALTY,
                stream=True,
            )
        ),
    )

    clean = extract_and_strip_state(session_id, raw_response)
    return clean


# =============================================================================
# STAGE 3 — TEXT-TO-SPEECH
# TODO Uwaid: Implement local TTS here.
#
# Suggested approach:
#   - Use Kokoro-82M (ONNX) or Piper TTS for low-latency CPU synthesis.
#   - Output format: WAV or raw PCM — match whatever Rayan's frontend expects.
#   - Load model once at module level.
#   - Run inference in _executor (blocking call).
#
# Example skeleton:
#   from kokoro_onnx import Kokoro
#   _tts_model = Kokoro("kokoro-v0_19.onnx", "voices.bin")
# =============================================================================

async def synthesize_speech(text: str, session_id: str) -> bytes:
    """
    Converts assistant reply text to audio bytes for streaming back to client.

    Args:
        text      : Clean assistant reply from the LLM stage.
        session_id: Active session ID (for logging/tracing).

    Returns:
        Audio bytes (WAV/PCM) ready to send over WebSocket.

    # TODO Uwaid: Replace the placeholder below with real TTS inference.
    #   1. Run _tts_model.create(text, voice="af_heart", speed=1.0) in _executor.
    #   2. Convert samples/numpy array to WAV bytes (use soundfile or wave module).
    #   3. Return the bytes — Awwab's WebSocket handler will chunk and stream them.
    #   4. Target latency: < 500 ms for a typical 1-2 sentence reply.
    """
    logger.info(f"[engine] TTS stub called | session={session_id} | {len(text)} chars")

    # TODO Uwaid: Remove this placeholder and implement real speech synthesis.
    raise NotImplementedError("TTS not implemented yet — Uwaid's task.")


# =============================================================================
# ORCHESTRATION LAYER (Awwab's scope)
# Routes.py calls process_audio() — it chains STT → LLM → TTS and handles
# session lifecycle. The three model stages are isolated; swapping any one
# does not require changes here, only in its own function above.
# =============================================================================

class VoiceEngine:
    """
    Orchestrates the full voice-to-voice pipeline for a single turn.
    Handles lifecycle guards (session ended, max turns) before invoking models.
    """

    def _check_lifecycle_guards(self, session_id: str) -> Optional[str]:
        """
        Returns an early-exit text reply if the session cannot proceed.
        Returns None if the session is healthy.
        """
        if _llm is None:
            return "I'm temporarily unavailable. Please try again later."
        if get_session_status(session_id) == "ended":
            return "This session has ended. Please start a new chat."
        if is_session_maxed(session_id):
            set_session_status(session_id, "ended")
            farewell = "We've reached the end of our session. Thank you for shopping with Daraz Assistant!"
            add_message_to_chat(session_id, "assistant", farewell)
            return farewell
        return None

    async def process_audio(self, session_id: str, audio_bytes: bytes) -> bytes:
        """
        Full pipeline: audio_bytes → STT → LLM → TTS → audio_bytes.

        Args:
            session_id  : Active session.
            audio_bytes : Raw audio from the WebSocket client.

        Returns:
            Audio bytes of the assistant's spoken reply.

        Raises:
            NotImplementedError : Until Uwaid implements STT and TTS stubs.
            RuntimeError        : If the LLM is not loaded.
        """
        start = time.perf_counter()

        # --- Lifecycle guard ---
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            # Even for guard responses, synthesize speech so the client gets audio.
            return await synthesize_speech(guard_text, session_id)

        # --- Stage 1: STT ---
        user_text = await transcribe_audio(audio_bytes, session_id)
        if not user_text.strip():
            logger.info(f"[engine] Empty transcript | session={session_id}")
            silence_reply = "I didn't catch that — could you try again?"
            return await synthesize_speech(silence_reply, session_id)

        logger.info(f"[engine] Transcript: '{user_text}' | session={session_id}")

        # --- Stage 2: LLM ---
        assistant_text = await _generate_text(session_id, user_text)

        # Persist the turn to Redis + SQLite
        add_message_to_chat(session_id, "user",      user_text)
        add_message_to_chat(session_id, "assistant", assistant_text)
        increment_turn(session_id)

        # Update session lifecycle
        if get_session_status(session_id) != "ended" and is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")

        # --- Stage 3: TTS ---
        audio_response = await synthesize_speech(assistant_text, session_id)

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(f"[engine] Pipeline complete | session={session_id} | {latency_ms:.0f} ms")

        return audio_response

    # -------------------------------------------------------------------------
    # LEGACY TEXT INTERFACE (kept for /chat REST endpoint & benchmark)
    # Routes that still send text (Postman, benchmarks) use generate().
    # -------------------------------------------------------------------------

    async def generate(self, session_id: str, user_message: str) -> dict:
        """
        Text-in / text-out wrapper. Used by POST /chat and /benchmark.
        Does NOT call STT or TTS — skips audio stages entirely.
        """
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            session = get_or_create_session(session_id)
            return {
                "response": guard_text, "latency_ms": 0.0,
                "session_id": session_id, "status": session.get("status", "active"),
                "turns_used": session.get("turns", 0), "turns_max": MAX_TURNS,
            }

        start = time.perf_counter()
        assistant_text = await _generate_text(session_id, user_message)

        add_message_to_chat(session_id, "user",      user_message)
        add_message_to_chat(session_id, "assistant", assistant_text)
        increment_turn(session_id)

        if get_session_status(session_id) != "ended" and is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")

        session = get_or_create_session(session_id)
        return {
            "response":   assistant_text,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "session_id": session_id,
            "status":     session["status"],
            "turns_used": session["turns"],
            "turns_max":  MAX_TURNS,
        }

    async def stream(self, session_id: str, user_message: str) -> AsyncGenerator[dict, None]:
        """
        Text-in / streaming-token-out wrapper. Used by WebSocket text fallback.
        Yields tokens live from the LLM via thread-pool executor.
        """
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            yield {"token": guard_text, "done": True}
            return

        if _llm is None:
            yield {"token": "LLM not loaded.", "done": True, "error": "LLM initialization failed."}
            return

        start = time.perf_counter()
        
        from app.core.config import build_chatml_prompt, TEMPERATURE, TOP_P, REPEAT_PENALTY
        messages = build_inference_payload(session_id, user_message)
        prompt   = build_chatml_prompt(messages)
        
        loop = asyncio.get_event_loop()
        
        # Execute the streaming iterator in the thread pool, yielding chunks
        # back to the async loop so we don't block other requests.
        try:
            token_generator = await loop.run_in_executor(
                _executor,
                lambda: tuple(_llm(
                    prompt,
                    max_tokens=MAX_TOKENS,
                    stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
                    echo=False,
                    temperature=TEMPERATURE,
                    top_p=TOP_P,
                    repeat_penalty=REPEAT_PENALTY,
                    stream=True,
                ))
            )
            
            full_text = ""
            for chunk in token_generator:
                token = chunk["choices"][0]["text"]
                full_text += token
                yield {"token": token, "done": False}
                await asyncio.sleep(0)  # yield to event loop

        except Exception as e:
            logger.error(f"[engine] Stream error: {e}")
            yield {"token": "", "done": True, "error": str(e)}
            return
            
        latency_ms = (time.perf_counter() - start) * 1000
        clean_response = extract_and_strip_state(session_id, full_text)
        
        # Strip trailing newlines just in case
        clean_response = clean_response.strip()

        add_message_to_chat(session_id, "user", user_message)
        add_message_to_chat(session_id, "assistant", clean_response)
        increment_turn(session_id)

        if get_session_status(session_id) != "ended" and is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")

        session = get_or_create_session(session_id)
        yield {
            "token": "",
            "done": True,
            "latency_ms": round(latency_ms, 2),
            "session_id": session_id,
            "status": session["status"],
            "turns_used": session["turns"],
            "turns_max": MAX_TURNS,
        }


# Singleton — imported by routes.py
llm_engine = VoiceEngine()