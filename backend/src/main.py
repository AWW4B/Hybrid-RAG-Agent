"""
main.py — FastAPI application entry point.

Endpoints:
  POST   /auth/register
  POST   /auth/login
  POST   /auth/logout
  POST   /sessions/create
  GET    /sessions?user_id=X       — list sessions for a user
  GET    /sessions/{session_id}/history
  DELETE /sessions/{session_id}
  WS     /ws/chat                  — streaming chat via WebSocket
  POST   /voice                    — non-streaming chat (for voice pipeline)
  POST   /warmup                   — pre-heat the model
  GET    /admin/dashboard          — placeholder admin route
  GET    /health                   — liveness probe
"""

import time
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from engine import llm
from conversation import memory
from auth.router import router as auth_router

# ── Logging ─────────────────────────────────────────────────────────
# Suppress noisy third-party loggers
for noisy in [
    "chromadb", "chromadb.telemetry", "chromadb.config",
    "chromadb.segment.impl", "chromadb.api",
    "sentence_transformers", "httpx", "httpcore",
    "urllib3", "onnxruntime",
]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ─────────────────────────────────────────────────────
    t0 = time.time()
    await db.init_db()
    logger.info(f"[startup] Database ready ({time.time()-t0:.2f}s)")

    t1 = time.time()
    llm.startup()
    logger.info(f"[startup] LLM engine ready ({time.time()-t1:.2f}s)")

    # Auto-index ChromaDB if empty (run in background to not block startup)
    def _bg_index():
        try:
            from retrieval.indexer import auto_index_if_needed
            auto_index_if_needed()
        except Exception as e:
            logger.warning(f"[startup] Auto-index skipped: {e}")

    asyncio.get_running_loop().run_in_executor(None, _bg_index)

    logger.info(f"[startup] Total boot time: {time.time()-t0:.2f}s")
    yield

    # ── Shutdown ────────────────────────────────────────────────────
    llm.shutdown()
    await db.close_db()
    logger.info("[shutdown] Clean shutdown complete.")


# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Daraz AI Voice Assistant",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


# ════════════════════════════════════════════════════════════════════
#  SESSION MANAGEMENT
# ════════════════════════════════════════════════════════════════════

class CreateSessionRequest(BaseModel):
    user_id: str
    title: str = ""


class SessionResponse(BaseModel):
    session_id: str


@app.post("/sessions/create", response_model=SessionResponse)
async def create_session(req: CreateSessionRequest):
    logger.info(f"[sessions] Creating session for user {req.user_id}")
    session_id = await db.create_session(req.user_id, req.title)
    memory.register_session(session_id, req.user_id)
    logger.info(f"[sessions] Created: {session_id}")
    return SessionResponse(session_id=session_id)


@app.get("/sessions")
async def list_sessions(user_id: str = Query(...)):
    logger.info(f"[sessions] Listing sessions for user {user_id}")
    sessions = await db.get_sessions_for_user(user_id)
    return {"sessions": sessions}


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    logger.info(f"[sessions] Loading history for {session_id}")
    # Try RAM first, fall back to DB
    history = memory.get_history(session_id)
    if not history:
        history = await db.get_messages(session_id)
        if history:
            memory.set_history(session_id, history)
    logger.info(f"[sessions] Loaded {len(history)} messages")
    return {"messages": history}


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    logger.info(f"[sessions] Deleting session {session_id}")
    await db.delete_session(session_id)
    return {"message": "Session deleted."}


# ════════════════════════════════════════════════════════════════════
#  CHAT (WebSocket — streaming)
#  Path: /ws/chat?session_id=X  (matches frontend expectation)
# ════════════════════════════════════════════════════════════════════

@app.websocket("/ws/chat")
async def chat_ws(
    ws: WebSocket,
    session_id: str = Query(default=""),
):
    await ws.accept()
    logger.info(f"[ws] Client connected (session_id from query: {session_id or 'none'})")

    try:
        while True:
            data = await ws.receive_json()
            # Support both formats:
            # Frontend sends: {session_id, message}  or  {session_id, prompt, user_id}
            sid = data.get("session_id") or session_id
            prompt = data.get("message") or data.get("prompt", "")
            prompt = prompt.strip()
            user_id = data.get("user_id", "")

            if not sid or not prompt:
                await ws.send_json({"error": "session_id and message required"})
                continue

            t_start = time.time()
            logger.info(f"[ws] ← user ({sid[:8]}): {prompt[:80]}...")

            # Ensure session is registered in RAM
            if not memory.get_session_owner(sid):
                if user_id:
                    memory.register_session(sid, user_id)
                else:
                    await ws.send_json({"error": "user_id required for new sessions"})
                    continue

            # Tool-calling callbacks for frontend indicator
            async def on_tool_start():
                await ws.send_json({"tool_status": "running", "tool_name": "Searching knowledge base & tools..."})

            async def on_tool_done(ctx):
                tools_used = []
                if ctx:
                    if "[Tool Output: Product Search]" in ctx:
                        tools_used.append("Product Search")
                    if "[Tool Output: Flash Deals]" in ctx:
                        tools_used.append("Flash Deals")
                    if "[Tool Output: Shipping]" in ctx:
                        tools_used.append("Shipping")
                    if "[Tool Output: Calculator]" in ctx:
                        tools_used.append("Calculator")
                    if "[Tool Output: Comparison]" in ctx:
                        tools_used.append("Comparison")
                    if "[Retrieved Knowledge Context]" in ctx:
                        tools_used.append("Knowledge Base")
                await ws.send_json({
                    "tool_status": "done",
                    "tools_used": tools_used or ["Knowledge Base"],
                })

            # Stream tokens
            full_response = []
            token_count = 0
            t_first_token = None

            async for token in llm.stream_chat(
                sid, prompt,
                on_tool_start=on_tool_start,
                on_tool_done=on_tool_done,
            ):
                if t_first_token is None:
                    t_first_token = time.time()
                    ttft = (t_first_token - t_start) * 1000
                    logger.info(f"[ws] TTFT: {ttft:.0f}ms")
                await ws.send_json({"token": token})
                full_response.append(token)
                token_count += 1

            total_time = (time.time() - t_start) * 1000
            response_text = "".join(full_response)

            # Signal end of response
            await ws.send_json({
                "done": True,
                "full_response": response_text,
                "latency_ms": round(total_time),
            })

            logger.info(
                f"[ws] → assistant ({sid[:8]}): {token_count} tokens, "
                f"{total_time:.0f}ms total, response: {response_text[:80]}..."
            )

    except WebSocketDisconnect:
        logger.info("[ws] Client disconnected.")
    except Exception as e:
        logger.error(f"[ws] Error: {e}", exc_info=True)
        try:
            await ws.send_json({"error": str(e)})
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
#  VOICE (non-streaming POST)
# ════════════════════════════════════════════════════════════════════

class VoiceRequest(BaseModel):
    session_id: str
    prompt: str
    user_id: str = ""


@app.post("/voice")
async def voice_chat(req: VoiceRequest):
    logger.info(f"[voice] Request for session {req.session_id}: {req.prompt[:60]}...")

    if not req.session_id or not req.prompt.strip():
        raise HTTPException(400, "session_id and prompt required.")

    if not memory.get_session_owner(req.session_id) and req.user_id:
        memory.register_session(req.session_id, req.user_id)

    t0 = time.time()
    response = await llm.generate_response(req.session_id, req.prompt.strip())
    elapsed = (time.time() - t0) * 1000
    logger.info(f"[voice] Response: {elapsed:.0f}ms, {len(response)} chars")

    return {"response": response}


# ════════════════════════════════════════════════════════════════════
#  WARMUP
# ════════════════════════════════════════════════════════════════════

@app.post("/warmup")
async def warmup():
    logger.info("[warmup] Starting model warmup...")
    t0 = time.time()
    result = await llm.warmup()
    logger.info(f"[warmup] Done in {(time.time()-t0)*1000:.0f}ms")
    return {"status": result}


# ════════════════════════════════════════════════════════════════════
#  ADMIN (placeholder)
# ════════════════════════════════════════════════════════════════════

@app.get("/admin/dashboard")
async def admin_dashboard():
    return {"message": "Admin dashboard placeholder.", "status": "ok"}


# ════════════════════════════════════════════════════════════════════
#  HEALTH
# ════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Run with uvicorn if executed directly ───────────────────────────

if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, workers=1)
