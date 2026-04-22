"""
End-to-End LLM loop test: Verifies that the bot correctly triggers tools.
Run with: docker compose exec backend python3 src/test_llm_loop.py
"""
import asyncio
import os
import sys
import time

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.engine.llm import llm_engine, get_llm
from src import db

async def test_scenario(session_id: str, prompt: str):
    print(f"\n[USER]: {prompt}")
    start = time.perf_counter()
    result = await llm_engine.generate(session_id, prompt)
    end = time.perf_counter()
    print(f"[BOT] ({round(end-start, 2)}s): {result['response']}")
    return result

async def main():
    print("=" * 60)
    print("  DARAZ ASSISTANT — E2E LLM LOOP & WARMUP TEST")
    print("=" * 60)

    # 1. WARMUP
    print("\n--- STAGE 0: WARMUP ---")
    print("Loading LLM model into memory (this may take 30-60s)...")
    start_warmup = time.perf_counter()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_llm)
    print(f"✅ Warmup complete in {round(time.perf_counter()-start_warmup, 2)}s")

    # 2. SESSION INIT
    print("\n--- STAGE 1: SESSION INIT ---")
    session_id = "e2e-test-session-001"
    # Ensure user exists for CRM tools
    user = await db.get_user_by_username("test_tool_user")
    if not user:
        await db.create_user("test_tool_user", "test@example.com", "hash")
    
    print(f"Session established: {session_id}")

    # 3. TEST SCENARIOS
    scenarios = [
        "What's the square root of 1024?", # Calculator
        "How much would it cost to ship a package to Faisalabad?", # Shipping
        "I'm looking for some Gul Ahmed products.", # Product Search
        "Compare Product_1 and Product_8 for me.", # Comparison
        "What are the best flash deals active right now?", # Flash Sale
        "Hey, please remember that I am interested in high-end electronics like laptops.", # CRM Update
        "Based on my preferences, what should I look for?" # CRM Retrieval
    ]

    for prompt in scenarios:
        await test_scenario(session_id, prompt)

    print("\n" + "=" * 60)
    print("  E2E LLM LOOP TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
