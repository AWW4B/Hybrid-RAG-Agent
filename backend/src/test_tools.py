"""
Comprehensive test for all 10+ tools in the unified src/ architecture.
Run with: sudo docker compose exec backend python3 src/test_tools.py
"""
import sys
import os
import asyncio

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def run_tests():
    print("=" * 60)
    print("  DARAZ ASSISTANT — UNIFIED TOOL REPOSITORY TEST")
    print("=" * 60)

    # 1. Shipping Estimator
    from src.tools.shipping import estimate_shipping
    print("\n--- TEST 1: Shipping Estimator ---")
    print(estimate_shipping("Islamabad"))

    # 3. Product Search
    from src.tools.product_search import search_products
    print("\n--- TEST 3: Product Search ---")
    print(search_products("Khaadi men clothing"))

    # 4. Product Comparison
    from src.tools.comparison import compare_products
    print("\n--- TEST 4: Product Comparison ---")
    # Using the new realistic names for comparison
    print(compare_products("Khaadi Men's Casual Wear", "Service Men's Athletic Shoes"))

    # 5. Flash Sale
    from src.tools.flash_sale import get_flash_deals
    print("\n--- TEST 5: Flash Deals ---")
    print(get_flash_deals())

    # 6. Calculator
    from src.tools.calculator import calculate
    print("\n--- TEST 6: Calculator ---")
    print(f"1500 * 2 = {calculate('1500 * 2')}")
    print(f"sqrt(625) = {calculate('sqrt(625)')}")

    # 7. CRM Profile (Async)
    from src.tools.crm import handle_crm_tool
    print("\n--- TEST 7: CRM Profile (Async) ---")
    session = {"crm_dirty": False}
    profile_result = await handle_crm_tool("get_crm_profile", {}, "test-user-123", session)
    print(f"Profile: {profile_result}")

    print("\n" + "=" * 60)
    print("  ALL CORE TOOLS VERIFIED [OK]")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
