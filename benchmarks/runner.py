# =============================================================================
# benchmarks/runner.py
# Standalone benchmark runner for the Daraz Assistant backend.
#
# Usage (from project root):
#   python -m benchmarks.runner
#   python -m benchmarks.runner --runs 10 --save
#
# Requires the backend to be running (uses httpx against the live server)
# OR import run_benchmark() programmatically and pass a session_factory.
# =============================================================================

import argparse
import asyncio
import json
import statistics
import time
import uuid
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Benchmark configuration
# ---------------------------------------------------------------------------
BENCHMARK_QUERIES = [
    "Show me Samsung phones under 15000 PKR",
    "What are the best laptops for students on Daraz?",
    "Compare the iPhone 15 and Samsung S24",
    "I need a gaming chair, budget 25000",
    "What's the return policy on electronics?",
    "Find me wireless earbuds under 3000 PKR",
    "Which brand makes the best air conditioners on Daraz?",
]

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_N_RUNS   = 5
TIMEOUT_SECONDS  = 60.0


# ---------------------------------------------------------------------------
# HTTP-based benchmark (runs against a live server)
# ---------------------------------------------------------------------------
async def run_query(client: httpx.AsyncClient, session_id: str, query: str) -> dict:
    """Send one query through the /chat REST endpoint and record metrics."""
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            "/chat",
            json={"session_id": session_id, "message": query},
            timeout=TIMEOUT_SECONDS,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code != 200:
            return {"ok": False, "latency_ms": latency_ms, "error": resp.text}
        body = resp.json()
        tokens_est = len(body.get("response", "").split())  # rough word count as proxy
        return {
            "ok":               True,
            "latency_ms":       round(latency_ms, 2),
            "tokens_generated": tokens_est,
            "status":           body.get("status"),
            "turns_used":       body.get("turns_used", 0),
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {"ok": False, "latency_ms": round(latency_ms, 2), "error": str(e)}


async def run_benchmark(
    base_url: str = DEFAULT_BASE_URL,
    n_runs: int   = DEFAULT_N_RUNS,
    token: Optional[str] = None,
    verbose: bool = True,
) -> dict:
    """
    Run all BENCHMARK_QUERIES × n_runs against a live server.

    Returns a summary dict:
      avg_latency_ms, p95_latency_ms, avg_tokens, error_rate,
      per_query breakdown, raw results.
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
        all_latencies:   list[float] = []
        all_tokens:      list[int]   = []
        errors:          int         = 0
        per_query:       list[dict]  = []

        for query in BENCHMARK_QUERIES:
            q_latencies = []
            q_tokens    = []
            q_errors    = 0

            for run in range(n_runs):
                session_id = str(uuid.uuid4())
                result = await run_query(client, session_id, query)

                if result["ok"]:
                    q_latencies.append(result["latency_ms"])
                    q_tokens.append(result.get("tokens_generated", 0))
                else:
                    q_errors += 1
                    errors += 1
                    if verbose:
                        print(f"  ⚠  Error [{query[:40]}] run {run+1}: {result.get('error')}")

            if q_latencies:
                avg_lat = statistics.mean(q_latencies)
                p95_lat = sorted(q_latencies)[int(len(q_latencies) * 0.95)]
                avg_tok = statistics.mean(q_tokens) if q_tokens else 0
            else:
                avg_lat = p95_lat = avg_tok = 0.0

            all_latencies.extend(q_latencies)
            all_tokens.extend(q_tokens)

            row = {
                "query":          query,
                "avg_latency_ms": round(avg_lat, 1),
                "p95_latency_ms": round(p95_lat, 1),
                "avg_tokens":     round(avg_tok, 1),
                "errors":         q_errors,
                "runs":           n_runs,
            }
            per_query.append(row)

            if verbose:
                status = "✅" if q_errors == 0 else "⚠️"
                print(f"  {status} [{query[:45]:<45}] "
                      f"avg={avg_lat:7.1f}ms  p95={p95_lat:7.1f}ms  "
                      f"tokens≈{avg_tok:5.1f}  errors={q_errors}/{n_runs}")

    total_runs = len(BENCHMARK_QUERIES) * n_runs

    summary = {
        "base_url":       base_url,
        "n_runs":         n_runs,
        "total_runs":     total_runs,
        "avg_latency_ms": round(statistics.mean(all_latencies), 1) if all_latencies else 0.0,
        "p95_latency_ms": round(
            sorted(all_latencies)[int(len(all_latencies) * 0.95)], 1
        ) if all_latencies else 0.0,
        "avg_tokens":     round(statistics.mean(all_tokens), 1) if all_tokens else 0.0,
        "error_count":    errors,
        "error_rate":     round(errors / total_runs, 3) if total_runs else 0.0,
        "per_query":      per_query,
    }
    return summary


# ---------------------------------------------------------------------------
# Programmatic interface (used by admin_router.py)
# ---------------------------------------------------------------------------
async def run_benchmark_against_engine(
    session_factory,
    n_runs: int = DEFAULT_N_RUNS,
) -> dict:
    """
    Alternative: run against the in-process engine (no HTTP server needed).
    session_factory: async callable() -> session object with .send_turn(msg) -> (response, meta)

    This matches the interface expected by admin/router.py's SSE benchmark endpoint.
    """
    results = {
        "latency_ms":          [],
        "tokens_generated":    [],
        "retrieval_time_ms":   [],
        "compaction_triggered": 0,
        "total_turns":          0,
    }

    for query in BENCHMARK_QUERIES:
        for _ in range(n_runs):
            session = await session_factory()
            t0 = time.perf_counter()
            try:
                response, meta = await session.send_turn(query)
                latency = (time.perf_counter() - t0) * 1000
                results["latency_ms"].append(latency)
                results["tokens_generated"].append(meta.get("tokens_generated", 0))
                results["retrieval_time_ms"].append(meta.get("retrieval_time_ms", 0))
                results["total_turns"] += 1
                if meta.get("compaction_ran"):
                    results["compaction_triggered"] += 1
            except Exception as e:
                print(f"[benchmark] Error for '{query[:40]}': {e}")

    n = len(results["latency_ms"]) or 1
    return {
        "avg_latency_ms":   round(statistics.mean(results["latency_ms"]), 1) if results["latency_ms"] else 0,
        "p95_latency_ms":   round(sorted(results["latency_ms"])[int(n * 0.95)], 1) if results["latency_ms"] else 0,
        "avg_tokens":       round(statistics.mean(results["tokens_generated"]), 1) if results["tokens_generated"] else 0,
        "avg_retrieval_ms": round(statistics.mean(results["retrieval_time_ms"]), 1) if results["retrieval_time_ms"] else 0,
        "compaction_rate":  results["compaction_triggered"] / results["total_turns"] if results["total_turns"] else 0,
        "raw":              results,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
async def _main():
    parser = argparse.ArgumentParser(description="Daraz Assistant benchmark runner")
    parser.add_argument("--url",   default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--runs",  type=int, default=DEFAULT_N_RUNS, help="Runs per query")
    parser.add_argument("--token", default=None, help="JWT access token for auth")
    parser.add_argument("--save",  action="store_true", help="Save results to benchmark_results.json")
    args = parser.parse_args()

    print(f"\n🚀 Daraz Assistant Benchmark")
    print(f"   URL:   {args.url}")
    print(f"   Runs:  {args.runs} per query × {len(BENCHMARK_QUERIES)} queries")
    print(f"   Total: {args.runs * len(BENCHMARK_QUERIES)} requests\n")

    summary = await run_benchmark(
        base_url=args.url,
        n_runs=args.runs,
        token=args.token,
        verbose=True,
    )

    print(f"\n{'='*60}")
    print(f"  Summary")
    print(f"{'='*60}")
    print(f"  Avg latency    : {summary['avg_latency_ms']} ms")
    print(f"  P95 latency    : {summary['p95_latency_ms']} ms")
    print(f"  Avg tokens     : {summary['avg_tokens']}")
    print(f"  Error rate     : {summary['error_rate']*100:.1f}% ({summary['error_count']}/{summary['total_runs']})")

    if args.save:
        out = f"benchmark_results_{int(time.time())}.json"
        with open(out, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n  📄 Results saved to {out}")


if __name__ == "__main__":
    asyncio.run(_main())
