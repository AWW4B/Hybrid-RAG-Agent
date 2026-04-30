# =============================================================================
# backend/src/tools/orchestrator.py
# Tool Orchestrator: Registry and Dispatcher for LLM Tool Calls.
# Consolidates tools from Hellsing and Refactor branches.
# =============================================================================

import json
import logging
import asyncio
from typing import Dict, Any, Optional

# --- Tool Imports ---
from src.tools.crm import handle_crm_tool
from src.tools.shipping import estimate_shipping
from src.tools.product_search import search_products
from src.tools.comparison import compare_products
from src.tools.flash_sale import get_flash_deals
from src.tools.calculator import calculate
# Note: calender, utils, shipping are imported where needed or through dispatch

logger = logging.getLogger(__name__)

# Metadata registry for LLM prompt injection
TOOLS_METADATA = [
    {
        "name": "update_crm_profile",
        "description": "CRITICAL: Save/Update user info immediately when they state a preference (e.g. 'I like Nike') or personal detail (e.g. 'My name is Gordon').",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "object", 
                    "description": "Dict of fields. Keys: name, preferred_categories (list), liked_brands (list), disliked_brands (list), budget_range, notes."
                }
            },
            "required": ["updates"]
        }
    },
    {
        "name": "search_products",
        "description": "Search the local product catalog. Use this IMMEDIATELY when a user mentions a brand or product type.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword (e.g. 'Khaadi lawn', 'Mens Shoes')"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "estimate_shipping",
        "description": "Get shipping fee and delivery date for a city in Pakistan.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g., 'Lahore', 'Faisalabad')"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "compare_products",
        "description": "Compare two products side-by-side. Use EXACT titles found via search_products.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_a": {"type": "string", "description": "Full name of first product"},
                "product_b": {"type": "string", "description": "Full name of second product"}
            },
            "required": ["product_a", "product_b"]
        }
    },
    {
        "name": "get_flash_deals",
        "description": "List all active 24-hour flash sales and discounted items.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "calculate",
        "description": "Perform SHOPPING-RELATED math only (e.g. price with discount, tax calculation, total for multiple items). Do NOT use for general math.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression (e.g. '1500 * 0.85')"}
            },
            "required": ["expression"]
        }
    }
]

class ToolOrchestrator:
    def __init__(self):
        self.tools = {
            "update_crm_profile": handle_crm_tool,
            "search_products": search_products,
            "estimate_shipping": estimate_shipping,
            "compare_products": compare_products,
            "get_flash_deals": get_flash_deals,
            "calculate": calculate
        }

    def get_tools_prompt(self) -> str:
        """Returns the system prompt block for tool usage."""
        prompt = "\n## Available Tools\n"
        prompt += "To use a tool, you MUST output EXACTLY this JSON format and nothing else:\n"
        prompt += "<TOOL_CALL>{\"name\": \"tool_name\", \"parameters\": {\"key\": \"value\"}}</TOOL_CALL>\n\n"
        for tool in TOOLS_METADATA:
            prompt += f"- {tool['name']}: {tool['description']}\n"
        return prompt

    async def execute_tool(self, tool_name: str, params: Dict[str, Any], user_id: str, session: dict) -> str:
        try:
            if tool_name in self.tools:
                func = self.tools[tool_name]
                
                # Manual dispatch for tools requiring context injection
                if tool_name in ["get_crm_profile", "update_crm_profile"]:
                    result = await func(tool_name, params, user_id, session)
                else:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**params)
                    else:
                        result = await asyncio.get_event_loop().run_in_executor(None, lambda: func(**params))
                
                return f"\n[TOOL_RESULT: {tool_name}]\n{result}\n"
            return f"\n[TOOL_ERROR] Tool '{tool_name}' not found.\n"
        except Exception as e:
            logger.error(f"[orchestrator] Tool execution failed: {e}")
            return f"\n[TOOL_ERROR] Failed to execute tool: {str(e)}\n"

    async def parse_and_execute(self, llm_text: str, user_id: str, session: dict) -> Optional[str]:
        if "<TOOL_CALL>" not in llm_text:
            return None
        try:
            start = llm_text.find("<TOOL_CALL>") + len("<TOOL_CALL>")
            end = llm_text.find("</TOOL_CALL>")
            call_data = json.loads(llm_text[start:end].strip())
            return await self.execute_tool(call_data["name"], call_data.get("parameters", {}), user_id, session)
        except Exception as e:
            logger.error(f"[orchestrator] Parse error: {e}")
            return f"\n[TOOL_ERROR] Invalid tool call format.\n"

orchestrator = ToolOrchestrator()