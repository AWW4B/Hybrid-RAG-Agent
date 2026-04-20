import json
import logging
import asyncio
from typing import Dict, Any, Optional

# Import the tool functions
from app.rag.tools.shipping import estimate_shipping
from app.rag.tools.product_search import search_products
from app.rag.tools.comparison import compare_products
from app.rag.tools.flash_sale import get_flash_deals
# from app.rag.tools.crm import get_user_info, update_user_info # Awwab will implement these

logger = logging.getLogger(__name__)

# List of available tools for the LLM to see in the prompt
TOOLS_METADATA = [
    {
        "name": "estimate_shipping",
        "description": "Calculate shipping fees and delivery date for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Destination city, e.g., Karachi"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "search_products",
        "description": "Search the local catalog for product details and prices.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term, e.g., 'Samsung'"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "compare_products",
        "description": "Compare two products side-by-side (price and ratings).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_a": {"type": "string", "description": "First product name"},
                "product_b": {"type": "string", "description": "Second product name"}
            },
            "required": ["product_a", "product_b"]
        }
    },
    {
        "name": "get_flash_deals",
        "description": "List the top active flash sales and discount deals.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]

class ToolOrchestrator:
    def __init__(self):
        self.tools = {
            "estimate_shipping": estimate_shipping,
            "search_products": search_products,
            "compare_products": compare_products,
            "get_flash_deals": get_flash_deals,
        }

    def get_tools_prompt(self) -> str:
        """Returns a string describing the tools for inclusion in the system prompt."""
        prompt = "\n## Available Tools (Agentic Capabilities)\n"
        prompt += "If you need real-time info, call these tools using: <TOOL_CALL>{\"name\": \"tool_name\", \"parameters\": {\"param\": \"value\"}}</TOOL_CALL>\n\n"
        for tool in TOOLS_METADATA:
            prompt += f"- {tool['name']}: {tool['description']}\n"
        return prompt

    async def parse_and_execute(self, llm_text: str) -> Optional[str]:
        """
        Scans LLM output for <TOOL_CALL> tags, executes them, and returns the result.
        Returns None if no tool call was found.
        """
        if "<TOOL_CALL>" not in llm_text:
            return None

        try:
            # Extract the JSON between tags
            start = llm_text.find("<TOOL_CALL>") + len("<TOOL_CALL>")
            end = llm_text.find("</TOOL_CALL>")
            call_json = llm_text[start:end].strip()
            
            call_data = json.loads(call_json)
            tool_name = call_data.get("name")
            params = call_data.get("parameters", {})

            if tool_name in self.tools:
                logger.info(f"[orchestrator] Executing tool: {tool_name} with params: {params}")
                
                # Execute tool (asynchronously if needed, though these are quick)
                # We use a wrapper to handle both sync and async functions if needed
                func = self.tools[tool_name]
                if asyncio.iscoroutinefunction(func):
                    result = await func(**params)
                else:
                    # Run sync tools in a way that doesn't block (using event loop executor for safety)
                    result = await asyncio.get_event_loop().run_in_executor(None, lambda: func(**params))
                
                return f"\n[TOOL_RESULT: {tool_name}]\n{result}\n"
            
            return f"\n[TOOL_ERROR] Tool '{tool_name}' not found.\n"

        except Exception as e:
            logger.error(f"[orchestrator] Tool execution failed: {e}")
            return f"\n[TOOL_ERROR] Failed to execute tool: {str(e)}\n"

# Singleton instance
orchestrator = ToolOrchestrator()