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

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

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
# PAYLOAD SIZE MIDDLEWARE
# =============================================================================
class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > MAX_PAYLOAD_BYTES:
                logger.warning(f"[security] Payload rejected: {content_length} bytes")
                return JSONResponse(status_code=413, content={"detail": "Payload too large."})
        return await call_next(request)

# =============================================================================
# LIFESPAN
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Startup sequence initiated...")
    try:
        import redis as redis_lib
        from app.core.config import REDIS_URL
        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=5)
        r.ping()
        logger.info("✅ 1/3: Redis connection verified.")
    except Exception as e:
        logger.error(f"❌ Redis unreachable: {e}")

    try:
        from app.memory.context import init_sessions_from_db
        init_sessions_from_db()
        logger.info("✅ 2/3: Database initialized.")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

    logger.info("✅ 3/3: Startup complete. API ready.")
    yield
    logger.info("🛑 Shutting down...")

# =============================================================================
# APP
# =============================================================================
app = FastAPI(
    title="Daraz Voice Assistant API",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(PayloadSizeLimitMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    @app.get("/ui", include_in_schema=False)
    async def serve_ui():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))