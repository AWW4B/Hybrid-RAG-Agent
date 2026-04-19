# =============================================================================
# app/main.py
# Security & Infrastructure for Daraz Voice Assistant (A3).
#   • Payload size limits (1MB max safety guard)
#   • Rate limiting (SlowAPI) on all endpoints
#   • Strict CORS configuration (locked to frontend origin)
#   • Persistent session management (Redis + SQLite)
# =============================================================================

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.core.config import FRONTEND_ORIGIN, MAX_PAYLOAD_BYTES
from app.core.limiter import limiter

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)



# =============================================================================
# PAYLOAD SIZE MIDDLEWARE
# Rejects any request whose body exceeds MAX_PAYLOAD_BYTES (1 MB) before it
# reaches any endpoint or WebSocket handler. This is the first line of defence
# against DDoS via oversized payloads.
# =============================================================================
class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reads the Content-Length header for a fast reject path.
    If not present (chunked transfer), reads up to the limit + 1 byte to detect overflow.
    """

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        # Fast path: Content-Length header present
        if content_length:
            if int(content_length) > MAX_PAYLOAD_BYTES:
                logger.warning(
                    f"[security] Payload rejected: {content_length} bytes from {request.client.host}"
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload too large. Maximum allowed size is 1 MB."},
                )

        # Slow path: chunked transfer — read and check
        else:
            body = await request.body()
            if len(body) > MAX_PAYLOAD_BYTES:
                logger.warning(
                    f"[security] Chunked payload rejected: {len(body)} bytes from {request.client.host}"
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload too large. Maximum allowed size is 1 MB."},
                )

        return await call_next(request)


# =============================================================================
# LIFESPAN — startup and shutdown
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("🚀 Daraz Assistant (A3 Voice) starting up...")

    # Verify Redis is reachable before accepting traffic
    try:
        import redis as redis_lib
        from app.core.config import REDIS_URL
        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=3)
        r.ping()
        logger.info("✅ Redis connection verified.")
    except Exception as e:
        logger.error(f"❌ Redis unreachable at startup: {e}. Sessions will not persist.")

    # Initialize SQLite and load sessions from DB into Redis
    from app.memory.context import init_sessions_from_db
    init_sessions_from_db()
    logger.info("✅ Startup complete. API ready.")

    yield

    # --- Shutdown ---
    logger.info("🛑 Daraz Assistant shutting down...")


# =============================================================================
# APP
# =============================================================================
app = FastAPI(
    title="Daraz Voice Assistant API",
    description=(
        "A3: Voice-to-Voice conversational AI backend. "
        "CPU-optimised local LLM + ASR + TTS pipeline via llama-cpp-python & local models. "
        "No RAG, no tools — prompt engineering, context management, and audio I/O."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# =============================================================================
# ATTACH RATE LIMITER STATE TO APP
# slowapi reads app.state.limiter to track counters.
# =============================================================================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# =============================================================================
# MIDDLEWARE (order matters — outermost runs first on request, last on response)
# =============================================================================

# 1. Payload size guard — must be first to reject oversized bodies early
app.add_middleware(PayloadSizeLimitMiddleware)

# 2. slowapi rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# 3. CORS — strict: allow the frontend origin(s) configured via env var.
#    Supports comma-separated strings for multiple origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",")],
    allow_credentials=True,           # required for HttpOnly cookie auth
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Session-ID"],
)


# =============================================================================
# ROUTES
# =============================================================================
app.include_router(router)


# =============================================================================
# FRONTEND STATIC SERVING
# =============================================================================
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    logger.info(f"Frontend mounted from: {FRONTEND_DIR}")

    @app.get("/ui", tags=["Frontend"], include_in_schema=False)
    async def serve_ui():
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"message": "Frontend not ready yet — index.html not found."}