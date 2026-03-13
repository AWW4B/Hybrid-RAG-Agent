# =============================================================================
# app/api/routes.py
# Awwab — A3 refactor: audio WebSocket, JWT auth stubs, rate limiting,
#         input sanitization, token truncation guardrail.
#
# Changes from A2:
#   • /ws/chat          — now accepts binary audio frames, returns binary audio
#   • /auth/login       — JWT stub (returns token in HttpOnly cookie)
#   • /auth/refresh     — JWT refresh stub
#   • All endpoints     — decorated with @limiter.limit() for per-IP rate limiting
#   • Text fallback     — bleach-sanitized and token-truncated before hitting LLM
# =============================================================================

import uuid
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bleach
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.core.config import (
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    MAX_TURNS,
    truncate_to_token_limit,
)
from app.llm.engine import llm_engine
from app.main import limiter                       # shared slowapi Limiter instance
from app.memory.context import (
    get_chat_history,
    get_or_create_session,
    get_session_state,
    get_session_status,
    get_welcome_message,
    list_active_sessions,
    reset_session,
)
from app.memory.database import delete_session as db_delete_session, list_sessions, load_session

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# INPUT SANITIZATION HELPER
# bleach strips all HTML/JS tags from any text that reaches the backend.
# Applied to every user message before it touches the LLM or database.
# =============================================================================

def sanitize_text(text: str) -> str:
    """
    Strips HTML and JavaScript from user input.
    bleach.clean() with no allowed tags/attrs removes all markup.
    Also truncates to token budget as a second guardrail.
    """
    cleaned = bleach.clean(text, tags=[], attributes={}, strip=True)
    return truncate_to_token_limit(cleaned)


# =============================================================================
# JWT HELPERS
# =============================================================================

def _create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire  = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    payload.update({"exp": expire})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")


def get_current_user(access_token: Optional[str] = Cookie(default=None)) -> dict:
    """
    FastAPI dependency: reads JWT from HttpOnly cookie, returns payload.
    Use as: user = Depends(get_current_user) on protected endpoints.
    Currently a stub — add real user lookup once a user DB exists.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return _verify_token(access_token)


# =============================================================================
# SCHEMAS
# =============================================================================

class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Omit to auto-generate")
    message:    str            = Field(...,  description="User message text (fallback REST)")

    class Config:
        json_schema_extra = {
            "example": {"session_id": "abc-123", "message": "I need a phone under 30000 PKR"}
        }


class ChatResponse(BaseModel):
    session_id: str
    response:   str
    latency_ms: float
    status:     str
    turns_used: int
    turns_max:  int


class ResetRequest(BaseModel):
    session_id: str


class LoginRequest(BaseModel):
    username: str
    password: str


# =============================================================================
# AUTH ENDPOINTS (JWT stubs)
# Awwab's scope: wiring, cookie handling, and response shape.
# Real user validation is a stub — extend with a users DB when ready.
# =============================================================================

@router.post("/auth/login", tags=["Auth"])
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    """
    Stub JWT login endpoint.
    Issues a signed JWT in an HttpOnly cookie (XSS-safe — JS cannot read it).

    TODO (future): validate body.username / body.password against a users table.
    For now, any non-empty credentials succeed (demo only).
    """
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Username and password required.")

    # TODO: replace with real DB user lookup and password hash check
    if body.password == "":  # placeholder rejection
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    token = _create_access_token({"sub": body.username})

    response = JSONResponse(content={"message": "Login successful.", "username": body.username})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,       # JS cannot read this cookie — XSS protection
        secure=True,         # HTTPS only in production
        samesite="strict",   # CSRF protection
        max_age=JWT_EXPIRE_MINUTES * 60,
    )
    logger.info(f"[auth] Login: {body.username}")
    return response


@router.post("/auth/refresh", tags=["Auth"])
@limiter.limit("10/minute")
async def refresh_token(request: Request, user: dict = Depends(get_current_user)):
    """
    Issues a new JWT using the existing valid token (sliding expiry).
    Client calls this before expiry to stay logged in without re-entering credentials.
    """
    new_token = _create_access_token({"sub": user["sub"]})
    response  = JSONResponse(content={"message": "Token refreshed."})
    response.set_cookie(
        key="access_token", value=new_token,
        httponly=True, secure=True, samesite="strict",
        max_age=JWT_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/auth/logout", tags=["Auth"])
async def logout():
    """Clears the HttpOnly auth cookie."""
    response = JSONResponse(content={"message": "Logged out."})
    response.delete_cookie("access_token")
    return response


# =============================================================================
# WEBSOCKET — /ws/chat  (Primary A3 endpoint)
#
# Protocol (Voice mode):
#   IN  → binary frame : raw audio bytes (WebM/PCM from MediaRecorder)
#   OUT → binary frame : raw audio bytes (WAV/PCM from TTS)
#   OUT → text frame   : JSON control message {"event": "...", ...}
#
# Protocol (Text fallback mode, for Postman/debug):
#   IN  → text frame   : JSON {"session_id": "...", "message": "..."}
#   OUT → text frame   : JSON {"token": "...", "done": true/false, ...}
#
# The endpoint auto-detects binary vs text frames to support both modes.
# Binary frames go through the full STT → LLM → TTS pipeline.
# Text frames use the legacy text-generation path (no STT/TTS).
# =============================================================================

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Voice-to-Voice WebSocket endpoint.
    Accepts audio binary chunks, returns audio binary chunks.
    Falls back to text token streaming if text frame is received.
    """
    await websocket.accept()
    session_id = None

    try:
        while True:
            # Receive next frame — could be binary (audio) or text (JSON fallback)
            message = await websocket.receive()

            # ------------------------------------------------------------------
            # BINARY PATH — Voice mode (primary A3 flow)
            # Client sends raw audio bytes captured by MediaRecorder/WebRTC.
            # ------------------------------------------------------------------
            if "bytes" in message and message["bytes"]:
                audio_bytes = message["bytes"]

                # Read session_id from query param or generate one
                if session_id is None:
                    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
                    logger.info(f"[routes] WS audio | session={session_id} | {len(audio_bytes)} bytes")

                # Reject oversized audio frames (belt-and-suspenders on top of middleware)
                from app.core.config import MAX_PAYLOAD_BYTES
                if len(audio_bytes) > MAX_PAYLOAD_BYTES:
                    await websocket.send_json({"event": "error", "detail": "Audio chunk too large."})
                    continue

                try:
                    # Full pipeline: STT → LLM → TTS
                    response_audio = await llm_engine.process_audio(session_id, audio_bytes)
                    await websocket.send_bytes(response_audio)

                    # Send a control message so the frontend knows the turn is done
                    session = get_or_create_session(session_id)
                    await websocket.send_json({
                        "event":      "turn_complete",
                        "session_id": session_id,
                        "status":     session["status"],
                        "turns_used": session["turns"],
                        "turns_max":  MAX_TURNS,
                    })

                except NotImplementedError:
                    await websocket.send_json({
                        "event":  "error",
                        "detail": "Voice pipeline not ready yet — STT/TTS not implemented.",
                    })
                except Exception as e:
                    logger.error(f"[routes] Audio pipeline error | session={session_id} | {e}")
                    await websocket.send_json({"event": "error", "detail": str(e)})

            # ------------------------------------------------------------------
            # TEXT PATH — Legacy / debug fallback
            # Preserves the A2 text-streaming behaviour for Postman and testing.
            # ------------------------------------------------------------------
            elif "text" in message and message["text"]:
                try:
                    import json as _json
                    data = _json.loads(message["text"])
                except Exception:
                    await websocket.send_json({"error": "Invalid JSON. Expected {session_id, message}."})
                    continue

                session_id   = data.get("session_id") or str(uuid.uuid4())
                raw_message  = data.get("message", "").strip()

                if not raw_message:
                    await websocket.send_json({"error": "message field is required."})
                    continue

                # Sanitize and truncate before any processing
                user_message = sanitize_text(raw_message)

                logger.info(f"[routes] WS text | session={session_id}")

                # Stream text tokens back (A2-compatible)
                async for chunk in llm_engine.stream(session_id, user_message):
                    await websocket.send_json(chunk)
                    if chunk.get("done"):
                        break

    except WebSocketDisconnect:
        logger.info(f"[routes] WS disconnected | session={session_id}")
    except Exception as e:
        logger.error(f"[routes] WS error | session={session_id} | {e}")
        try:
            await websocket.send_json({"error": str(e), "done": True})
        except Exception:
            pass


# =============================================================================
# REST CHAT ENDPOINT (text fallback — Postman / benchmarks)
# =============================================================================

@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    """
    Text-in / text-out REST endpoint. Used for Postman testing and benchmarks.
    Input is sanitized and token-truncated before hitting the LLM.
    """
    session_id = body.session_id or str(uuid.uuid4())

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    user_message = sanitize_text(body.message)

    logger.info(f"[routes] POST /chat | session={session_id}")
    result = await llm_engine.generate(session_id=session_id, user_message=user_message)
    return ChatResponse(**result)


# =============================================================================
# SESSION ENDPOINTS
# =============================================================================

@router.get("/session/welcome/{session_id}", tags=["Session"])
@limiter.limit("30/minute")
async def welcome(request: Request, session_id: str):
    return get_welcome_message(session_id)


@router.post("/reset", tags=["Session"])
@limiter.limit("20/minute")
async def reset(request: Request, body: ResetRequest):
    reset_session(body.session_id)
    return {"message": f"Session '{body.session_id}' reset.", "status": "active"}


@router.get("/sessions", tags=["Session"])
@limiter.limit("30/minute")
async def get_all_sessions(request: Request):
    return {"sessions": list_sessions()}


@router.get("/sessions/{session_id}", tags=["Session"])
@limiter.limit("30/minute")
async def get_session(request: Request, session_id: str):
    session = get_or_create_session(session_id)
    return {
        "session_id": session_id,
        "history":    session["history"],
        "state":      session["state"],
        "turns":      session["turns"],
        "status":     session["status"],
        "turns_max":  MAX_TURNS,
    }


@router.delete("/sessions/{session_id}", tags=["Session"])
@limiter.limit("20/minute")
async def delete_session_endpoint(request: Request, session_id: str):
    # Remove from Redis (context module handles this)
    reset_session(session_id)
    success = db_delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": f"Session '{session_id}' deleted."}


# =============================================================================
# BENCHMARKING ENDPOINT
# =============================================================================

@router.post("/benchmark", tags=["Benchmarking"])
@limiter.limit("5/minute")
async def benchmark(request: Request, runs: int = 3):
    """Runs N text-inference calls and returns latency statistics."""
    if runs < 1 or runs > 20:
        raise HTTPException(status_code=400, detail="runs must be between 1 and 20.")

    bench_session = f"benchmark-{uuid.uuid4()}"
    latencies, errors = [], 0
    test_message = "I need a budget smartphone under 20000 PKR."

    for i in range(runs):
        try:
            result = await llm_engine.generate(bench_session, test_message)
            latencies.append(result["latency_ms"])
        except Exception as e:
            errors += 1
            logger.error(f"[benchmark] Run {i+1} failed: {e}")

    reset_session(bench_session)

    if not latencies:
        raise HTTPException(status_code=500, detail="All benchmark runs failed.")

    latencies.sort()
    avg = sum(latencies) / len(latencies)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else latencies[-1]

    return {
        "runs_completed": len(latencies),
        "runs_failed":    errors,
        "avg_ms":         round(avg, 2),
        "min_ms":         round(latencies[0], 2),
        "max_ms":         round(latencies[-1], 2),
        "p50_ms":         round(p50, 2),
        "p95_ms":         round(p95, 2),
        "note":           "Save these results for README.md performance benchmarks.",
    }


# =============================================================================
# HEALTH & DEBUG
# =============================================================================

@router.get("/health", tags=["System"])
async def health():
    try:
        from app.core.config import REDIS_URL
        import redis as _r
        _r.from_url(REDIS_URL, socket_connect_timeout=1).ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unreachable"

    return {
        "status":          "ok",
        "redis":           redis_status,
        "active_sessions": len(list_active_sessions()),
    }


@router.post("/debug/warmup", tags=["Debug"])
async def warmup():
    warm_id = f"warmup-{uuid.uuid4()}"
    result  = await llm_engine.generate(warm_id, "Hello")
    reset_session(warm_id)
    return {"message": "Warmup complete.", "latency_ms": result["latency_ms"]}


@router.get("/debug/history/{session_id}", tags=["Debug"])
async def debug_history(session_id: str):
    history = get_chat_history(session_id)
    return {"session_id": session_id, "message_count": len(history), "history": history}


@router.get("/debug/state/{session_id}", tags=["Debug"])
async def debug_state(session_id: str):
    return {
        "session_id": session_id,
        "state":      get_session_state(session_id),
        "status":     get_session_status(session_id),
    }


@router.get("/debug/sessions", tags=["Debug"])
async def debug_sessions():
    sessions = list_active_sessions()
    return {"count": len(sessions), "session_ids": sessions}