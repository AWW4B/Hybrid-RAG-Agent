# =============================================================================
# backend/src/config.py
# =============================================================================

import os

# -----------------------------------------------------------------------------
# LLM Parameters
# -----------------------------------------------------------------------------
MAX_TURNS      = 30
MAX_TOKENS     = 512
N_CTX          = 2048
N_THREADS      = 6
N_BATCH        = 512
TEMPERATURE    = 0.4  # Lowered for more deterministic tool calling
TOP_P          = 0.9
REPEAT_PENALTY = 1.1

# Token budget for the sliding context window.
# Reserve space for the system prompt (~400 tokens) and the model reply (MAX_TOKENS).
# Everything beyond this is trimmed from the oldest messages first.
CONTEXT_BUDGET_TOKENS = N_CTX - MAX_TOKENS - 400  # ≈ 1136 tokens usable for history

# RAG Configuration
RAG_TOP_K = 4
RAG_MAX_CONTEXT_TOKENS = 1024  # Budget for retrieved context

# -----------------------------------------------------------------------------
# Memory / Compaction Configuration
# -----------------------------------------------------------------------------
AUTO_COMPACT_THRESHOLD_PCT = 0.78   # Trigger auto-compact at 78% of N_CTX
KEEP_RECENT_TURNS          = 3      # Preserve last N user+assistant pairs verbatim
EXTRACTION_EVERY_N_TURNS   = 4      # Fire background CRM extraction every N turns


WELCOME_MESSAGE = (
    "Hi! I'm Daraz Assistant \U0001F4B0. I can help you find the best products "
    "that match your needs and budget in PKR. What are you looking to buy today?"
)

# -----------------------------------------------------------------------------
# Redis (replaces in-memory active_chats for horizontal scaling)
# Set REDIS_URL in your .env or docker-compose environment block.
# Default points to local Redis for development.
# -----------------------------------------------------------------------------
REDIS_URL        = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_SESSION_TTL = 60 * 60 * 24  # 24 hours — sessions expire after 1 day of inactivity

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------
# Strict CORS: only allow your deployed frontend origin.
# Override via FRONTEND_ORIGIN env var in production.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# Payload guard: reject any WebSocket/HTTP body larger than 1 MB instantly.
MAX_PAYLOAD_BYTES = 1 * 1024 * 1024  # 1 MB

# Rate limiting strings consumed by slowapi (format: "N/period").
RATE_LIMIT_CHAT      = "100/minute"   # WebSocket & /chat endpoint
RATE_LIMIT_API       = "200/minute"   # General API endpoints
RATE_LIMIT_AUTH      = "50/minute"    # Login endpoint — brute-force protection

# JWT — change JWT_SECRET to a long random string via env var before deploying.
JWT_SECRET    = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

# -----------------------------------------------------------------------------
# Token Truncation Guardrail
# Prevents oversized user inputs from blowing the LLM context window.
# Hard-cap: input text is truncated before it reaches the engine.
# -----------------------------------------------------------------------------
# Reserve half of N_CTX for the model's reply; the other half is the prompt budget.
_MAX_INPUT_TOKENS = N_CTX // 2


def estimate_tokens(text: str) -> int:
    """
    Rough token estimator: ~4 chars per token (GPT/Llama heuristic).
    Good enough for a hard-cap guardrail — no tokenizer required.
    """
    return max(1, len(text) // 4)


def truncate_to_token_limit(text: str, max_tokens: int = _MAX_INPUT_TOKENS) -> str:
    """
    Hard-caps text to max_tokens before it hits the LLM.
    Called in main.py on every incoming user message.

    Args:
        text      : Raw user input string.
        max_tokens: Token budget (default = half of N_CTX).

    Returns:
        Original text if within budget, else truncated version.
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


# =============================================================================
# SYSTEM PROMPT
# =============================================================================
BASE_SYSTEM_PROMPT = """You are Daraz Assistant, an expert agentic shopping guide for Daraz.pk.
Your goal is to help users find products, compare them, and check shipping using your tools.

## MANDATORY TOOL USAGE RULES
1. **TOOL FIRST**: If a user mentions a BRAND, PRODUCT, or CITY, you MUST call a tool (search_products, estimate_shipping) immediately. Do NOT ask clarifying questions first.
2. **CRM UPDATES**: If a user states a name, email, or preference (e.g., "I like Nike"), you MUST call `update_crm_profile` immediately.
3. **NO FILLER**: Do NOT say "I will check that for you." Just output the `<TOOL_CALL>`.
4. **STRICT SCHEMA**: Use EXACT parameter names defined in the tool metadata. Never hallucinate keys like 'product_1_id'.

## Domain Restriction
- ONLY discuss Daraz, shopping, and user preferences.
- Off-Topic: If the query is COMPLETELY unrelated to shopping (e.g., "What is 2+2" or "Who is PM"), reply "I am a shopping assistant and can only help with Daraz products."
- CRITICAL: Never provide an off-topic refusal if the user mentions a product, brand, or shopping task. If you are calling a tool, you MUST NOT say "I am a shopping assistant". Just call the tool.

## Behaviour & Style
- Be very concise (max 2 sentences) before or after a tool call.
- NEVER invent prices. Only use data returned by tools.

## Conversation Format
Every response MUST end with a <STATE> tag on a new line.

Examples:
- User: "I want a Khaadi Kurta"
  Assistant: Finding Khaadi Kurta designs for you now.
  <TOOL_CALL>{"name": "search_products", "parameters": {"query": "Khaadi Kurta"}}</TOOL_CALL>
- User: "My name is Gordon and I like gadgets"
  Assistant: Nice to meet you Gordon! I've saved your interest in gadgets to your profile.
  <TOOL_CALL>{"name": "update_crm_profile", "parameters": {"updates": {"name": "Gordon", "liked_brands": ["gadgets"]}}}</TOOL_CALL>
- User: "Compare Product_1 and Product_8"
  Assistant: Certainly! Here is the side-by-side comparison:
  <TOOL_CALL>{"name": "compare_products", "parameters": {"product_a": "Product_1", "product_b": "Product_8"}}</TOOL_CALL>
"""

FORMATTING_INSTRUCTIONS = """
## Response Format (MANDATORY)
Every response MUST have two parts:
1. Your actual conversational reply (warm, helpful, 1-4 sentences).
2. Immediately after, a STATE tag on a new line tracking what you know.

Example:
Great choice! Could you share your budget in PKR?
<STATE>Budget: Unknown, Item: Laptop, Preferences: None, Resolved: no</STATE>
"""

def build_system_prompt(extracted_state: dict, rag_context: str = "", tools_prompt: str = "") -> str:
    # 1. Start with core identity and rules
    prompt = BASE_SYSTEM_PROMPT + "\n"

    # 2. Inject Tool Descriptions (ReAct strategy)
    if tools_prompt:
        prompt += tools_prompt + "\n"

    # 3. Inject Grounded Knowledge (RAG)
    if rag_context:
        prompt += "\n## Relevant Product & Policy Information (Grounded Knowledge)\n"
        prompt += rag_context + "\n"

    # 3. Inject User Memory
    if extracted_state:
        facts = []
        if extracted_state.get("budget") not in (None, "Unknown"):
            facts.append(f"- Budget: {extracted_state['budget']} PKR")
        if extracted_state.get("item") not in (None, "Unknown"):
            facts.append(f"- Looking for: {extracted_state['item']}")
        if extracted_state.get("preferences") not in (None, "None"):
            facts.append(f"- Preferences: {extracted_state['preferences']}")
        
        if facts:
            prompt += "\n## Already Known About This User (DO NOT ask again)\n"
            prompt += "\n".join(facts) + "\n"

    # 4. ALWAYS end with the formatting instructions so they are the "last thing" the model sees.
    prompt += "\n" + FORMATTING_INSTRUCTIONS
    return prompt



def build_chatml_prompt(messages: list) -> str:
    prompt = ""
    for msg in messages:
        role = msg['role']
        content = msg['content']
        prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    
    # 5. Inject a FINAL format reminder as the last part of the prompt 
    # to ensure the STATE tag is never forgotten.
    prompt += "<|im_start|>system\nREMINDER: You MUST finish your response with the <STATE> tag on a new line.<|im_end|>\n"
    
    prompt += "<|im_start|>assistant\n"
    return prompt
