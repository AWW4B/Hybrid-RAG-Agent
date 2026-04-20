# =============================================================================
# backend/src/admin/router.py
# Admin API endpoints — all protected by require_admin dependency.
# Only JWT tokens with "admin": true can access these routes.
# =============================================================================

import asyncio
import logging
import statistics
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.auth.security import require_admin
from src import db
from src.conversation.memory import list_active_sessions, get_or_create_session

logger = logging.getLogger(__name__)

admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

# ---------------------------------------------------------------------------
# Benchmark queries (mirrors benchmarks/runner.py)
# ---------------------------------------------------------------------------
BENCHMARK_QUERIES = [
    "Show me Samsung phones under 15000 PKR",
    "What are the best laptops for students on Daraz?",
    "Compare the iPhone 15 and Samsung S24",
    "I need a gaming chair, budget 25000",
    "What's the return policy on electronics?",
]


# =============================================================================
# LIVE SESSION MONITOR
# =============================================================================
@admin_router.get("/sessions")
async def admin_sessions():
    """Returns a summary of all active sessions with token estimates."""
    from src.conversation.compaction import estimate_tokens

    session_ids = list_active_sessions()
    results = []
    for sid in session_ids:
        session = get_or_create_session(sid)
        history = session.get("history", [])
        token_est = estimate_tokens(history)
        from src.config import N_CTX
        pct = token_est / N_CTX
        results.append({
            "session_id":    sid,
            "user_id":       session.get("user_id"),
            "turns":         session.get("turns", 0),
            "turn_count":    session.get("turn_count", 0),
            "token_estimate": token_est,
            "context_pct":   round(pct * 100, 1),
            "status":        session.get("status", "active"),
            "near_limit":    pct >= 0.78,   # yellow indicator threshold
        })
    return {"active_count": len(results), "sessions": results}


# =============================================================================
# MEMORY HEALTH — COMPACTION STATS
# =============================================================================
@admin_router.get("/compaction/stats")
async def compaction_stats(hours: int = 24):
    """Returns compaction event counts and token averages for the dashboard."""
    stats = await db.get_compaction_stats(hours=hours)
    return {"hours": hours, "stats": stats}


# =============================================================================
# BENCHMARK RUNNER (SSE streaming progress)
# =============================================================================
@admin_router.post("/benchmark/run")
async def run_benchmark(n_runs: int = 3):
    """
    Triggers the benchmark runner and streams results via SSE.
    Each line is a JSON object: {"query": ..., "avg_latency_ms": ..., "status": ...}
    """
    from src.engine.llm import llm_engine

    async def _stream():
        results = []
        for query in BENCHMARK_QUERIES:
            latencies = []
            for _ in range(n_runs):
                import uuid as _uuid
                session_id = str(_uuid.uuid4())
                t0 = time.perf_counter()
                try:
                    result = await asyncio.wait_for(
                        llm_engine.generate(session_id=session_id, user_message=query),
                        timeout=30.0,
                    )
                    latency = (time.perf_counter() - t0) * 1000
                    latencies.append(latency)
                    await db.insert_benchmark(
                        test_name=query[:50],
                        metric="latency_ms",
                        value=latency,
                        session_id=session_id,
                    )
                except Exception as e:
                    logger.error(f"[benchmark] Run failed for '{query}': {e}")

            if latencies:
                row = {
                    "query":          query,
                    "avg_latency_ms": round(statistics.mean(latencies), 1),
                    "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1),
                    "runs":           len(latencies),
                    "status":         "ok",
                }
            else:
                row = {"query": query, "status": "error", "runs": 0}

            results.append(row)
            import json as _json
            yield f"data: {_json.dumps(row)}\n\n"

        # Final summary event
        import json as _json
        yield f"data: {_json.dumps({'done': True, 'total_queries': len(results)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@admin_router.get("/benchmark/history")
async def benchmark_history(limit: int = 100):
    rows = await db.get_benchmark_history(limit=limit)
    return {"results": rows}


# =============================================================================
# USER / CRM TABLE
# =============================================================================
@admin_router.get("/users")
async def list_users(page: int = 1, page_size: int = 20):
    users = await db.list_users(page=page, page_size=page_size)
    return {"page": page, "page_size": page_size, "users": users}


@admin_router.get("/users/{user_id}/crm")
async def get_user_crm(user_id: str):
    profile = await db.get_crm_profile(user_id)
    if not profile:
        raise HTTPException(404, detail="CRM profile not found.")
    return profile


@admin_router.post("/users/{user_id}/unlock")
async def unlock_user(user_id: str):
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, detail="User not found.")
    await db.unlock_user(user_id)
    return {"message": f"User {user_id} unlocked.", "user_id": user_id}
