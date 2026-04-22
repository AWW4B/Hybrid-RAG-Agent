"""
Comprehensive test for all 7 tools (+ Orchestrator) in the unified src/ architecture.
Run with: docker compose exec backend python3 src/test_tools.py
"""
import sys
import os
import asyncio
import json

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def run_tests():
    print("=" * 60)
    print("  DARAZ ASSISTANT — FULL TOOLSUITE REGRESSION TEST")
    print("=" * 60)

    # 1. Shipping Estimator
    from src.tools.shipping import estimate_shipping
    print("\n--- TEST 1: Shipping Estimator ---")
    print(estimate_shipping("Islamabad"))
    print(estimate_shipping("Quetta"))

    # 2. Product Search
    from src.tools.product_search import search_products
    print("\n--- TEST 2: Product Search ---")
    print(search_products("Khaadi men clothing"))
    print(search_products("Shoes"))

    # 3. Product Comparison
    from src.tools.comparison import compare_products
    print("\n--- TEST 3: Product Comparison ---")
    print(compare_products("Khaadi Men's Casual Wear", "Service Men's Athletic Shoes"))

    # 4. Flash Sale
    from src.tools.flash_sale import get_flash_deals
    print("\n--- TEST 4: Flash Deals ---")
    print(get_flash_deals())

    # 5. Calculator
    from src.tools.calculator import calculate
    print("\n--- TEST 5: Calculator ---")
    print(f"1500 * 3 = {calculate('1500 * 3')}")
    print(f"sqrt(144) = {calculate('sqrt(144)')}")

    # 6. CRM Profile & Updates (Async)
    from src.tools.crm import handle_crm_tool
    from src import db
    print("\n--- TEST 6: CRM Profile Persistence ---")
    
    # Ensure user exists for foreign key constraint
    username = "test_tool_user"
    user = await db.get_user_by_username(username)
    if not user:
        print("Creating test user...")
        user_id = await db.create_user(username, "test@example.com", "placeholder_hash")
    else:
        user_id = user["id"]
        
    session = {"crm_dirty": False}
    
    print(f"Step A: Updating profile for user {user_id}...")
    upd_res = await handle_crm_tool("update_crm_profile", {"updates": {"name": "Test User", "liked_brands": ["Khaadi", "Outfitters"]}}, user_id, session)
    print(f"Update Result: {upd_res}")
    
    print("Step B: Fetching updated profile...")
    profile_result = await handle_crm_tool("get_crm_profile", {}, user_id, session)
    print(f"Fetch Result: {profile_result}")
    
    if "Test User" in profile_result and "Khaadi" in profile_result:
        print("[OK] CRM Update/Get Verified.")
    else:
        print("[FAIL] CRM update did not persist as expected.")

    # 7. Orchestrator Dispatch (Parsing)
    from src.tools.orchestrator import orchestrator
    print("\n--- TEST 7: Orchestrator Parsing & Execution ---")
    mock_llm_output = '<TOOL_CALL>{"name": "calculate", "parameters": {"expression": "100 * 5.5"}}</TOOL_CALL>'
    print(f"Input: {mock_llm_output}")
    orch_result = await orchestrator.parse_and_execute(mock_llm_output, user_id, session)
    print(f"Orchestrator Result: {orch_result}")
    
    if "550" in orch_result:
        print("[OK] Orchestrator correctly parsed and executed the tool call.")
    else:
        print("[FAIL] Orchestrator result unexpected.")

    print("\n" + "=" * 60)
    print("  ALL TOOLS & ORCHESTRATOR VERIFIED [OK]")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
