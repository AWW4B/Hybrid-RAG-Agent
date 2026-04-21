import asyncio
import time
import json
import statistics
from src.engine.llm import llm_engine
from src.admin.router import BENCHMARK_QUERIES

async def run_quality_bench():
    print("🚀 Starting Quality Benchmark...")
    results = []
    for entry in BENCHMARK_QUERIES:
        query = entry["query"]
        t0 = time.perf_counter()
        try:
            resp = await llm_engine.generate(f"bench-{time.time()}", query)
            lat = (time.perf_counter() - t0) * 1000
            results.append({"query": query, "latency": lat, "type": entry["type"], "status": "ok"})
            print(f"  [OK] {query[:40]}... -> {lat:.0f}ms")
        except Exception as e:
            results.append({"query": query, "status": "error", "error": str(e)})
            print(f"  [ERR] {query[:40]}...")
    
    avg = statistics.mean([r["latency"] for r in results if r["status"] == "ok"])
    print(f"✅ Quality Bench Done. Avg Latency: {avg:.0f}ms")
    return results

async def run_concurrency_bench(n=5):
    print(f"🚀 Starting Concurrency Test ({n} users)...")
    query = "What is the best Samsung phone under 50000 PKR?"
    sessions = [f"stress-{i}-{time.time()}" for i in range(n)]
    
    t0 = time.perf_counter()
    tasks = [llm_engine.generate(sid, query) for sid in sessions]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = (time.perf_counter() - t0) * 1000
    
    latencies = []
    # Note: We can't get individual latencies easily from gather, 
    # but the total_time/n gives us a good throughput metric.
    # Actually, we'll just use the total time as the "Stress Latency".
    
    print(f"✅ Concurrency Done. Total Time for {n} users: {total_time:.0f}ms")
    return total_time

async def run_warmup():
    print("🔥 Warming up models (2 turns)...")
    for _ in range(2):
        await llm_engine.generate("warmup", "Hi there")
    print("✅ Warmup complete.")

async def main():
    await run_warmup()
    q_results = await run_quality_bench()
    total_stress = await run_concurrency_bench(5)
    
    summary = {
        "quality_avg_ms": statistics.mean([r["latency"] for r in q_results if r["status"] == "ok"]),
        "stress_total_ms": total_stress,
        "stress_per_user_avg": total_stress / 5
    }
    with open("bench_results.json", "w") as f:
        json.dump(summary, f)

if __name__ == "__main__":
    asyncio.run(main())
