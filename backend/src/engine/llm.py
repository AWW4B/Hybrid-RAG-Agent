# =============================================================================
# backend/src/engine/llm.py
# Voice-to-Voice orchestration engine with Lazy-Loading and Tool execution loop.
# =============================================================================

import io
import json
import logging
import os
import tempfile
import time
import asyncio
import threading
from typing import Optional, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

import wave
import moonshine_onnx as moonshine
from piper import PiperVoice
from llama_cpp import Llama

from src.config import (
    MAX_TURNS, MAX_TOKENS, N_CTX, N_THREADS, N_BATCH,
    TEMPERATURE, TOP_P, REPEAT_PENALTY,
    RAG_MAX_CONTEXT_TOKENS,
)
from src.conversation.memory import (
    build_inference_payload,
    add_message_to_chat,
    extract_and_strip_state,
    increment_turn,
    is_session_maxed,
    get_session_status,
    set_session_status,
    is_conversation_resolved,
    get_or_create_session,
    apply_micro_compact,
    refresh_crm_block,
    flush_session_to_db,
)
from src.conversation.compaction import (
    auto_compact_if_needed,
    maybe_extract_to_crm,
    estimate_tokens,
)
from src.retrieval.search import retriever


logger = logging.getLogger(__name__)

# Thread pool for blocking model inference
_executor = ThreadPoolExecutor(max_workers=10)

# Implementation Note:
# We use lazy loading to prevent OOM in environments with limited RAM.
# Models occupy ~2.5GB combined. Only load them on first use.

_llm: Optional[Llama] = None
_tts_model: Optional[PiperVoice] = None
_load_lock = threading.Lock()

def get_llm() -> Llama:
    global _llm
    if _llm is None:
        with _load_lock:
            if _llm is None:
                model_path = os.getenv("MODEL_PATH", "/models/qwen2.5-3b-instruct-q4_k_m.gguf")
                logger.info(f"🔥 [engine] Lazy-loading LLM model from: {model_path}")
                try:
                    _llm = Llama(
                        model_path=model_path,
                        n_ctx=N_CTX,
                        n_threads=N_THREADS,
                        n_batch=N_BATCH,
                        n_gpu_layers=0,
                        verbose=False,
                    )
                    logger.info("✅ [engine] LLM model loaded successfully.")
                except Exception as e:
                    logger.error(f"❌ [engine] LLM load failed: {e}")
                    raise
    return _llm

def get_tts() -> PiperVoice:
    global _tts_model
    if _tts_model is None:
        with _load_lock:
            if _tts_model is None:
                model_path = os.getenv("PIPER_MODEL", "/models/en_US-lessac-medium.onnx")
                logger.info(f"🔥 [engine] Lazy-loading Piper TTS: {model_path}")
                try:
                    _tts_model = PiperVoice.load(model_path)
                    logger.info("✅ [engine] Piper TTS loaded.")
                except Exception as e:
                    logger.error(f"❌ [engine] TTS load failed: {e}")
                    raise
    return _tts_model

# Moonshine is lightweight but we still follow the pattern
_MOONSHINE_MODEL = "moonshine/base"

# =============================================================================
# STAGE 1 — SPEECH-TO-TEXT
# =============================================================================
async def transcribe_audio(audio_bytes: bytes, session_id: str) -> str:
    logger.info(f"[engine] STT called | session={session_id} | {len(audio_bytes)} bytes")

    def _run_stt() -> str:
        suffix = ".wav" if audio_bytes[:4] == b"RIFF" else ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            raw_path = tmp.name

        wav_path = None
        try:
            import subprocess
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_tmp:
                wav_path = wav_tmp.name
            subprocess.run(
                ["ffmpeg", "-y", "-i", raw_path, "-ac", "1", "-ar", "16000", wav_path],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # moonshine handles its own internal loading
            transcripts = moonshine.transcribe(wav_path, _MOONSHINE_MODEL)
            return " ".join(t.strip() for t in transcripts).strip()
        finally:
            for p in (raw_path, wav_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_stt)


# =============================================================================
# STAGE 3 — TEXT-TO-SPEECH
# =============================================================================
async def synthesize_speech(text: str, session_id: str) -> bytes:
    tts = get_tts()

    def _run_tts() -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(tts.config.sample_rate)
            tts.synthesize(text, wav_file)
        return buf.getvalue()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_tts)


# =============================================================================
# INTERNAL LLM HELPERS
# =============================================================================
from src.config import build_chatml_prompt

def _run_llm_sync(prompt: str, max_tokens: int) -> str:
    """Blocking call — must run in executor."""
    llm = get_llm()
    return "".join(
        chunk["choices"][0]["text"]
        for chunk in llm(
            prompt,
            max_tokens=max_tokens,
            stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
            echo=False,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repeat_penalty=REPEAT_PENALTY,
            stream=True,
        )
    )


async def _llm_generate_non_streaming(messages: list[dict], max_tokens: int = 400) -> str:
    prompt = build_chatml_prompt(messages)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_llm_sync, prompt, max_tokens)


async def _generate_text(session_id: str, user_text: str, recursion_limit: int = 3) -> str:
    """Stage 2: RAG retrieval + LLM generation with recursive Tool Execution Loop."""
    from src.tools.orchestrator import orchestrator
    
    # Track the prompt for recursion (append results over turns)
    current_text_to_process = user_text
    
    for attempt in range(recursion_limit):
        # RAG context is mostly for the initial user query
        rag_context = retriever.get_relevant_context(current_text_to_process)
        if estimate_tokens([{"content": rag_context}]) > RAG_MAX_CONTEXT_TOKENS:
            rag_context = rag_context[: RAG_MAX_CONTEXT_TOKENS * 4]

        messages = build_inference_payload(session_id, current_text_to_process, rag_context=rag_context)
        prompt   = build_chatml_prompt(messages)

        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(_executor, _run_llm_sync, prompt, MAX_TOKENS)
        
        if "<TOOL_CALL>" in raw_response:
            logger.info(f"🛠️ [engine] Tool call detected on attempt {attempt+1}")
            session = get_or_create_session(session_id)
            tool_result = await orchestrator.parse_and_execute(raw_response, session["user_id"], session)
            current_text_to_process += f"\n{tool_result}"
            continue
        
        return extract_and_strip_state(session_id, raw_response)
    
    return "I'm having trouble completing that request right now."


# =============================================================================
# ORCHESTRATION LAYER
# =============================================================================
class VoiceEngine:

    def _check_lifecycle_guards(self, session_id: str) -> Optional[str]:
        if get_session_status(session_id) == "ended":
            return "This session has ended. Please start a new chat."
        if is_session_maxed(session_id):
            set_session_status(session_id, "ended")
            farewell = "We've reached the end of our session. Thank you for shopping with Daraz Assistant!"
            add_message_to_chat(session_id, "assistant", farewell)
            return farewell
        return None

    async def _post_turn_hooks(self, session_id: str) -> None:
        loop = asyncio.get_event_loop()
        apply_micro_compact(session_id)
        loop.run_in_executor(_executor, flush_session_to_db, session_id)
        session = get_or_create_session(session_id)
        await maybe_extract_to_crm(session, _llm_generate_non_streaming)

    async def process_audio(self, session_id: str, audio_bytes: bytes) -> tuple[bytes, str, str]:
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            return await synthesize_speech(guard_text, session_id), "", guard_text

        user_text = await transcribe_audio(audio_bytes, session_id)
        if not user_text.strip():
            silence_reply = "I didn't catch that — could you try again?"
            return await synthesize_speech(silence_reply, session_id), "", silence_reply

        assistant_text = await _generate_text(session_id, user_text)

        add_message_to_chat(session_id, "user",      user_text)
        add_message_to_chat(session_id, "assistant", assistant_text)
        increment_turn(session_id)

        if get_session_status(session_id) != "ended" and is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")

        audio_response = await synthesize_speech(assistant_text, session_id)
        session = get_or_create_session(session_id)
        asyncio.create_task(self._background_memory_work(session_id, session))

        return audio_response, user_text, assistant_text

    async def generate(self, session_id: str, user_message: str) -> dict:
        guard_text = self._check_lifecycle_guards(session_id)
        if guard_text:
            session = get_or_create_session(session_id)
            return {
                "response":   guard_text,
                "latency_ms": 0.0,
                "session_id": session_id,
                "status":     session.get("status", "active"),
                "turns_used": session.get("turns", 0),
                "turns_max":  MAX_TURNS,
            }

        start = time.perf_counter()
        assistant_text = await _generate_text(session_id, user_message)

        add_message_to_chat(session_id, "user",      user_message)
        add_message_to_chat(session_id, "assistant", assistant_text)
        increment_turn(session_id)

        if get_session_status(session_id) != "ended" and is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")

        session = get_or_create_session(session_id)
        result = {
            "response":   assistant_text,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "session_id": session_id,
            "status":     session["status"],
            "turns_used": session["turns"],
            "turns_max":  MAX_TURNS,
        }
        asyncio.create_task(self._background_memory_work(session_id, session))
        return result

    async def _background_memory_work(self, session_id: str, session: dict) -> None:
        try:
            await auto_compact_if_needed(
                session, _llm_generate_non_streaming, context_window=N_CTX, session_id=session_id
            )
            await self._post_turn_hooks(session_id)
        except Exception as e:
            logger.warning(f"[engine] Background memory work failed: {e}")

    async def stream(self, session_id: str, user_message: str, recursion_limit: int = 3) -> AsyncGenerator[dict, None]:
        if get_session_status(session_id) == "ended":
            yield {"token": "This session has ended.", "done": True}
            return

        current_prompt_text = user_message
        from src.tools.orchestrator import orchestrator

        for attempt in range(recursion_limit):
            start = time.perf_counter()
            rag_context = retriever.get_relevant_context(current_prompt_text)
            if estimate_tokens([{"content": rag_context}]) > RAG_MAX_CONTEXT_TOKENS:
                rag_context = rag_context[: RAG_MAX_CONTEXT_TOKENS * 4]

            messages = build_inference_payload(session_id, current_prompt_text, rag_context=rag_context)
            prompt   = build_chatml_prompt(messages)

            loop = asyncio.get_event_loop()
            token_queue: asyncio.Queue = asyncio.Queue()
            llm = get_llm()

            def _worker():
                try:
                    for chunk in llm(
                        prompt,
                        max_tokens=MAX_TOKENS,
                        stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
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

            loop.run_in_executor(_executor, _worker)

            full_text = ""
            is_tool_call = False
            hide_remaining = False
            yield_buffer = ""

            while True:
                item = await token_queue.get()
                if item is None: break
                if isinstance(item, Exception):
                    yield {"token": "", "done": True, "error": str(item)}
                    return

                token = item["choices"][0]["text"]
                full_text += token

                if "<TOOL_CALL>" in full_text and not is_tool_call:
                    is_tool_call = True
                
                if is_tool_call:
                    continue

                if hide_remaining: continue
                yield_buffer += token

                if "<STATE>" in yield_buffer:
                    hide_remaining = True
                    valid_text, _ = yield_buffer.split("<STATE>", 1)
                    if valid_text: yield {"token": valid_text, "done": False}
                    yield_buffer = ""
                    continue

                match_len = 0
                for i in range(1, len("<STATE>") + 1):
                    if yield_buffer.endswith("<STATE>"[:i]): match_len = i

                if match_len > 0:
                    safe_to_yield = yield_buffer[:-match_len]
                    yield_buffer  = yield_buffer[-match_len:]
                else:
                    safe_to_yield = yield_buffer
                    yield_buffer  = ""

                if safe_to_yield:
                    yield {"token": safe_to_yield, "done": False}

            if is_tool_call:
                logger.info(f"🛠️ [engine-stream] Tool call detected on attempt {attempt+1}")
                session = get_or_create_session(session_id)
                tool_result = await orchestrator.parse_and_execute(full_text, session["user_id"], session)
                current_prompt_text += f"\n{tool_result}"
                continue
            
            if yield_buffer and not hide_remaining:
                yield {"token": yield_buffer, "done": False}

            clean_response = extract_and_strip_state(session_id, full_text)
            add_message_to_chat(session_id, "user",      user_message)
            add_message_to_chat(session_id, "assistant", clean_response.strip())
            increment_turn(session_id)
            
            if get_session_status(session_id) != "ended" and is_conversation_resolved(session_id):
                set_session_status(session_id, "closing")

            session = get_or_create_session(session_id)
            yield {
                "token":      "",
                "done":       True,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "session_id": session_id,
                "status":     session["status"],
                "turns_used": session["turns"],
                "turns_max":  MAX_TURNS,
            }
            asyncio.create_task(self._background_memory_work(session_id, session))
            return

llm_engine = VoiceEngine()
