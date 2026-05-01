"""
orchestrator.py — Pre-generation tool routing.

Takes the raw user prompt BEFORE it hits the LLMs.
Detects intent, calls the right tools (RAG, product search, etc.),
and returns a formatted tool-output string to be injected into the prompt.
"""

import re
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from tools.product_search import search_products
from tools.flash_sale import get_flash_deals
from tools.shipping import estimate_shipping
from tools.calculator import calculate
from tools.comparison import compare_products
from retrieval.search import retriever

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None


def init_orchestrator(executor: ThreadPoolExecutor) -> None:
    global _executor
    _executor = executor
    logger.info("[orchestrator] Initialized with thread pool.")


# ── Intent Detection (keyword-based, zero-latency) ─────────────────

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("flash_sale",  ["flash sale", "flash deal", "today's deal", "deals", "active deals", "sale"]),
    ("shipping",    ["shipping", "delivery", "deliver to", "ship to", "shipping cost"]),
    ("calculator",  ["calculate", "how much is", "what is", "math", "add", "multiply", "subtract"]),
    ("compare",     ["compare", "versus", "vs", "better", "difference between"]),
    ("product",     ["search", "find", "show me", "looking for", "want to buy",
                     "price of", "how much", "cheapest", "expensive", "phone", "laptop",
                     "product", "buy", "shop"]),
]


def _detect_intents(prompt: str) -> list[str]:
    """Return list of matched intent names, ordered by priority."""
    lower = prompt.lower()
    matched = []
    for intent_name, keywords in _INTENT_PATTERNS:
        if any(kw in lower for kw in keywords):
            matched.append(intent_name)
    return matched


def _extract_city(prompt: str) -> str:
    """Try to pull a city name from the prompt for shipping."""
    cities = [
        "karachi", "lahore", "islamabad", "rawalpindi",
        "faisalabad", "multan", "peshawar", "quetta",
    ]
    lower = prompt.lower()
    for city in cities:
        if city in lower:
            return city
    # Fallback: try to grab word after "to"
    m = re.search(r"\bto\s+([a-zA-Z]+)", prompt, re.IGNORECASE)
    return m.group(1) if m else ""


def _extract_compare_products(prompt: str) -> tuple[str, str]:
    """Try to extract two product names for comparison."""
    patterns = [
        r"compare\s+(.+?)\s+(?:and|vs|versus|with)\s+(.+)",
        r"(.+?)\s+vs\.?\s+(.+)",
        r"difference between\s+(.+?)\s+and\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, prompt, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return "", ""


def _extract_math_expr(prompt: str) -> str:
    """Pull a math expression from the prompt."""
    m = re.search(r"(?:calculate|compute|what is|how much is)\s+(.+)", prompt, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip("?.")
    # Fallback: look for an expression-like pattern
    m = re.search(r"(\d[\d\s\+\-\*/\.\(\)]+\d)", prompt)
    return m.group(1).strip() if m else ""


# ── Tool Execution ─────────────────────────────────────────────────

def _execute_tool(intent: str, prompt: str) -> str:
    """Run a single tool synchronously and return formatted output."""
    try:
        if intent == "flash_sale":
            result = get_flash_deals()
            return f"[Tool Output: Flash Deals]\n{result}"

        elif intent == "shipping":
            city = _extract_city(prompt)
            if not city:
                return ""
            result = estimate_shipping(city)
            return f"[Tool Output: Shipping]\n{result}"

        elif intent == "calculator":
            expr = _extract_math_expr(prompt)
            if not expr:
                return ""
            result = calculate(expr)
            return f"[Tool Output: Calculator]\n{result}"

        elif intent == "compare":
            a, b = _extract_compare_products(prompt)
            if not a or not b:
                return ""
            result = compare_products(a, b)
            return f"[Tool Output: Comparison]\n{result}"

        elif intent == "product":
            result = search_products(prompt)
            return f"[Tool Output: Product Search]\n{result}"

    except Exception as e:
        logger.error(f"[orchestrator] Tool '{intent}' failed: {e}")
    return ""


# ── RAG Retrieval ──────────────────────────────────────────────────

def _run_rag(prompt: str) -> str:
    """Query the ChromaDB vector store for relevant context."""
    try:
        return retriever.get_relevant_context(prompt)
    except Exception as e:
        logger.error(f"[orchestrator] RAG retrieval failed: {e}")
        return ""


# ── Public API ─────────────────────────────────────────────────────

async def run_orchestrator(prompt: str) -> str:
    """
    Main entry point. Detects intents, runs tools + RAG in parallel
    threads, and returns the combined tool context string.
    """
    loop = asyncio.get_running_loop()
    intents = _detect_intents(prompt)

    # Always run RAG in parallel with any detected tool
    futures = []

    # RAG retrieval
    futures.append(loop.run_in_executor(_executor, _run_rag, prompt))

    # Tool calls (run at most 2 tools to avoid bloating the prompt)
    for intent in intents[:2]:
        futures.append(loop.run_in_executor(_executor, _execute_tool, intent, prompt))

    results = await asyncio.gather(*futures, return_exceptions=True)

    # Combine non-empty results
    parts = []
    for r in results:
        if isinstance(r, str) and r.strip():
            parts.append(r.strip())
        elif isinstance(r, Exception):
            logger.error(f"[orchestrator] Parallel task failed: {r}")

    return "\n\n".join(parts)
