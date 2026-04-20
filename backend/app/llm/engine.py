# =============================================================================
# llm/engine.py
# Voice-to-Voice orchestration engine.
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

import io
import logging
import os
import queue
import tempfile
import time
import asyncio
import threading
from typing import Optional, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

import math
import wave

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import moonshine_onnx as moonshine
from piper import PiperVoice
from llama_cpp import Llama

from app.core.config import MAX_TURNS, MAX_TOKENS, N_CTX, N_THREADS, N_BATCH
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
from app.rag.retrieval.retriever import retriever
from app.rag.tools.orchestrator import orchestrator


logger = logging.getLogger(__name__)

# Thread pool for blocking model inference (keeps async event loop free)
_executor = ThreadPoolExecutor(max_workers=1)

# =============================================================================
# STT MODEL — Moonshine ASR (base), loaded once at startup.
# moonshine-onnx runs on CPU via ONNX Runtime — no GPU required.
# The model weights are downloaded automatically on first use (~70 MB).
# =============================================================================
_MOONSHINE_MODEL = "moonshine/base"   # swap to "moonshine/tiny" for faster CPU
logger.info(f"[engine] Moonshine STT model: {_MOONSHINE_MODEL} (weights auto-downloaded on first call)")

# =============================================================================
# TTS MODEL — Piper TTS, loaded once at startup.
# Requires an .onnx voice model + matching .onnx.json config in /models/.
# Download from: https://github.com/rhasspy/piper/releases
# Default voice: en_US-lessac-medium (clear, neutral US-English male).
# =============================================================================
_piper_model_path = os.getenv("PIPER_MODEL", "/models/en_US-lessac-medium.onnx")
try:
    _tts_model = PiperVoice.load(_piper_model_path)
    logger.info(f"✅ [engine] Piper TTS loaded: {_piper_model_path}")
except Exception as _e:
    logger.error(f"❌ [engine] Piper TTS load failed: {_e}")
    _tts_model = None


# =============================================================================
# STAGE 1 — SPEECH-TO-TEXT  (Uwaid: Moonshine ASR)
# Moonshine expects a mono, 16 kHz WAV file path.
# Incoming audio may be WAV or WebM — we normalize it here before passing
# it to the model so the caller never has to worry about format.
# =============================================================================

async def transcribe_audio(audio_bytes: bytes, session_id: str) -> str:
    """
    Converts raw audio bytes (WebM/WAV from the browser) to a text transcript
    using Moonshine ASR (base model) running on CPU via ONNX Runtime.

    Args:
        audio_bytes: Raw audio data received over WebSocket (WebM or WAV).
        session_id : Active session ID (for logging/tracing).

    Returns:
        Transcribed text string, or "" if audio is silent / unintelligible.
    """
    logger.info(f"[engine] STT called | session={session_id} | {len(audio_bytes)} bytes")

    def _run_stt() -> str:
        # Step 1 — write incoming bytes to a temp file (WebM or WAV)
        suffix = ".wav" if audio_bytes[:4] == b"RIFF" else ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            raw_path = tmp.name

        wav_path = None
        try:
            # Step 2 — decode + resample to 16 kHz mono (Moonshine requirement)
            # Use ffmpeg since soundfile cannot read browser WebM blobs
            import subprocess
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_tmp:
                wav_path = wav_tmp.name
                
            subprocess.run([
                "ffmpeg", "-y", "-i", raw_path,
                "-ac", "1", "-ar", "16000",
                wav_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Step 4 — run Moonshine ASR
            transcripts = moonshine.transcribe(wav_path, _MOONSHINE_MODEL)
            transcript  = " ".join(t.strip() for t in transcripts).strip()
            logger.info(f"[engine] STT done | '{transcript[:80]}' | session={session_id}")
            return transcript

        finally:
            for p in (raw_path, wav_path):
                if p:
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_stt)


# =============================================================================
# STAGE 2 — LLM ORCHESTRATION LOOP
# The business logic handles RAG retrieval and tool calling in a recursive loop.
# =============================================================================

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
        verbose=True,
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
        raise RuntimeError("LLM not loaded. Ensure MODEL_PATH is correct.")

    from app.core.config import build_chatml_prompt, TEMPERATURE, TOP_P, REPEAT_PENALTY, RAG_MAX_CONTEXT_TOKENS, estimate_tokens

    # Fetch RAG context
    rag_context = retriever.get_relevant_context(user_text)
    
    # Simple truncation for context window safety (cap at RAG_MAX_CONTEXT_TOKENS)
    if estimate_tokens(rag_context) > RAG_MAX_CONTEXT_TOKENS:
        rag_context = rag_context[:RAG_MAX_CONTEXT_TOKENS * 4]

    messages = build_inference_payload(session_id, user_text, rag_context=rag_context)
    prompt   = build_chatml_prompt(messages)


    loop = asyncio.get_event_loop()

    # Loop to handle tool updates (multi-turn reasoning)
    # We limit to 2 tool calls per turn to prevent infinite loops
    for _ in range(2):
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

        tool_result = await orchestrator.parse_and_execute(raw_response)
        if tool_result:
            # If a tool was called, add result to history and ask LLM again
            logger.info(f"[engine] Tool result obtained: {tool_result[:50]}...")
            
            # We don't use add_message_to_chat here yet because it's internal reasoning
            # We build a new prompt with the tool result injected
            messages.append({"role": "assistant", "content": raw_response})
            messages.append({"role": "system", "content": tool_result})
            prompt = build_chatml_prompt(messages)
            continue # Try generating again with the tool output
        else:
            # No tool call, return final response
            clean = extract_and_strip_state(session_id, raw_response)
            return clean

    return "I apologize, but I encountered an issue processing your request with my tools."


# =============================================================================
# STAGE 3 — TEXT-TO-SPEECH (Piper TTS)
# Piper synthesizes directly into a wave.Wave_write object.
# =============================================================================

async def synthesize_speech(text: str, session_id: str) -> bytes:
    """
    Converts assistant reply text to WAV audio bytes using Piper TTS running
    on CPU via ONNX Runtime (en_US-lessac-medium voice by default).

    Args:
        text      : Clean assistant reply from the LLM stage.
        session_id: Active session ID (for logging/tracing).

    Returns:
        WAV bytes ready to send over WebSocket to the browser.
    """
    if _tts_model is None:
        raise RuntimeError("Piper TTS model is not loaded. Set PIPER_MODEL env var.")

    logger.info(f"[engine] TTS called | session={session_id} | {len(text)} chars")

    def _run_tts() -> bytes:
        # synthesize() writes PCM frames directly into a wave.Wave_write.
        # We back it with an in-memory BytesIO so nothing touches disk.
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(_tts_model.config.sample_rate)
            _tts_model.synthesize(text, wav_file)
        wav_bytes = buf.getvalue()
        logger.info(
            f"[engine] TTS done | session={session_id} | {len(wav_bytes)} bytes"
        )
        return wav_bytes

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_tts)


# =============================================================================
# ORCHESTRATION LAYER
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

    async def process_audio(self, session_id: str, audio_bytes: bytes) -> tuple[bytes, str, str]:
        """
        Full pipeline: audio_bytes → STT → LLM → TTS → audio_bytes.

        Args:
            session_id  : Active session.
            audio_bytes : Raw audio from the WebSocket client.

        Returns:
            Tuple containing (audio_response_bytes, user_text, assistant_text)

        Raises:
            RuntimeError : If the LLM/TTS is not loaded.
        """
        start = time.perf_counter()

        # --- Lifecycle guard ---
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            # Even for guard responses, synthesize speech so the client gets audio.
            return await synthesize_speech(guard_text, session_id), "", guard_text

        # --- Stage 1: STT ---
        user_text = await transcribe_audio(audio_bytes, session_id)
        if not user_text.strip():
            logger.info(f"[engine] Empty transcript | session={session_id}")
            silence_reply = "I didn't catch that — could you try again?"
            return await synthesize_speech(silence_reply, session_id), "", silence_reply

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

        return audio_response, user_text, assistant_text

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
        Uses an asyncio.Queue to bridge the LLM generator (running in a thread pool) 
        to the async event loop, ensuring true non-blocking streaming.
        """
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            yield {"token": guard_text, "done": True}
            return

        if _llm is None:
            yield {"token": "LLM not loaded.", "done": True, "error": "LLM initialization failed."}
            return

        start = time.perf_counter()
        from app.core.config import build_chatml_prompt, TEMPERATURE, TOP_P, REPEAT_PENALTY, RAG_MAX_CONTEXT_TOKENS, estimate_tokens
        
        # Fetch RAG context
        rag_context = retriever.get_relevant_context(user_message)
        
        # Simple truncation for context window safety
        if estimate_tokens(rag_context) > RAG_MAX_CONTEXT_TOKENS:
            rag_context = rag_context[:RAG_MAX_CONTEXT_TOKENS * 4]

        messages = build_inference_payload(session_id, user_message, rag_context=rag_context)
        prompt   = build_chatml_prompt(messages)


        # --- MULTI-TURN REASONING LOOP FOR STREAMING ---
        # We handle up to 2 tool calls per turn.
        # If a tool call is detected, we don't stream it to the user.
        for _ in range(2):
            full_text = ""
            yield_buffer = ""
            hide_remaining = False
            token_queue = asyncio.Queue()

            # Start worker for this generation turn
            def _worker_v2(current_prompt):
                try:
                    for chunk in _llm(
                        current_prompt,
                        max_tokens=MAX_TOKENS,
                        stop=['<|im_end|>', '<|endoftext|>', '<|im_start|>'],
                        echo=False,
                        temperature=TEMPERATURE,
                        top_p=TOP_P,
                        repeat_penalty=REPEAT_PENALTY,
                        stream=True,
                    ):
                        loop.call_soon_threadsafe(token_queue.put_nowait, chunk)
                except Exception as e:
                    loop.call_soon_threadsafe(token_queue.put_nowait, e)
                finally:
                    loop.call_soon_threadsafe(token_queue.put_nowait, None)

            loop = asyncio.get_event_loop()
            loop.run_in_executor(_executor, _worker_v2, prompt)

            current_turn_full_text = ""
            while True:
                item = await token_queue.get()
                if item is None: break
                if isinstance(item, Exception):
                    logger.error(f"[engine] Stream worker error: {item}")
                    yield {"token": "", "done": True, "error": str(item)}
                    return

                token = item["choices"][0]["text"]
                current_turn_full_text += token
                
                # Buffer logic to hide <STATE> tags or <TOOL_CALL> tags from user
                yield_buffer += token
                
                if "<STATE>" in yield_buffer or "<TOOL_CALL>" in yield_buffer:
                    hide_remaining = True
                    # If we hit a tool call, we definitely stop yielding this turn's text
                    # because we want to run the tool and generate a final answer.
                
                if not hide_remaining:
                    # Partial matching logic for tags (avoid yielding bits of <STA...)
                    match_len = 0
                    for tag in ["<STATE>", "<TOOL_CALL>"]:
                        for i in range(1, len(tag) + 1):
                            if yield_buffer.endswith(tag[:i]):
                                match_len = max(match_len, i)
                    
                    if match_len > 0:
                        safe_to_yield = yield_buffer[:-match_len]
                        yield_buffer = yield_buffer[-match_len:]
                    else:
                        safe_to_yield = yield_buffer
                        yield_buffer = ""
                    
                    if safe_to_yield:
                        yield {"token": safe_to_yield, "done": False}

            # Turn is done — check if it was a tool call
            tool_result = await orchestrator.parse_and_execute(current_turn_full_text)
            if tool_result:
                logger.info(f"[engine] Streaming turn yielded tool call. Running tool...")
                messages.append({"role": "assistant", "content": current_turn_full_text})
                messages.append({"role": "system", "content": tool_result})
                prompt = build_chatml_prompt(messages)
                continue # Generate again with tool output
            else:
                # Normal response finished
                full_text = current_turn_full_text
                if yield_buffer and not hide_remaining:
                    yield {"token": yield_buffer, "done": False}
                break

        latency_ms = (time.perf_counter() - start) * 1000
        clean_response = extract_and_strip_state(session_id, full_text)
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
