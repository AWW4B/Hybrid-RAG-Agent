"""
config.py — Single source of truth for every tunable constant.
Import from here everywhere; never hard-code paths or limits elsewhere.
"""

import os
from pathlib import Path

# ── Project Paths ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # Hybrid-RAG-Agent/
BACKEND_ROOT = PROJECT_ROOT / "backend"
SRC_ROOT     = BACKEND_ROOT / "src"

MODELS_DIR   = os.getenv("MODELS_DIR",  str(PROJECT_ROOT / "models"))
DATASET_DIR  = os.getenv("DOCS_DIR",    str(PROJECT_ROOT / "dataset"))
CHROMA_DIR   = os.getenv("CHROMA_PATH", str(PROJECT_ROOT / "chroma_db"))
DB_PATH      = os.getenv("DB_PATH",     str(BACKEND_ROOT / "app.db"))

# ── LLM (llama.cpp) ────────────────────────────────────────────────
LLM_MODEL_PATH = os.getenv(
    "LLM_MODEL_PATH",
    str(Path(MODELS_DIR) / "qwen2.5-3b-instruct-q4_k_m.gguf"),
)
LLM_N_CTX           = int(os.getenv("LLM_N_CTX", "4096"))       # context window tokens
LLM_N_THREADS       = int(os.getenv("LLM_N_THREADS", "0"))      # 0 = auto-detect
LLM_N_GPU_LAYERS    = int(os.getenv("LLM_N_GPU_LAYERS", "0"))
LLM_CHAT_TEMP       = float(os.getenv("LLM_CHAT_TEMP", "0.7"))
LLM_BRAIN_TEMP      = float(os.getenv("LLM_BRAIN_TEMP", "0.1")) # brain must be precise
LLM_MAX_TOKENS_CHAT = int(os.getenv("LLM_MAX_TOKENS_CHAT", "512"))
LLM_MAX_TOKENS_BRAIN= int(os.getenv("LLM_MAX_TOKENS_BRAIN", "768"))

# ── Compaction Thresholds ───────────────────────────────────────────
COMPACTION_TRIGGER_PCT   = 0.75          # 78 % of context window
TOOL_PAYLOAD_MAX_CHARS   = 600           # scrub tool payloads bigger than this
RECENT_TURNS_TO_KEEP     = 3             # kept intact during auto-compaction
CHARS_PER_TOKEN_ESTIMATE = 3.5           # rough char→token conversion factor

# ── Retrieval / RAG ────────────────────────────────────────────────
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))

# ── Server ──────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ── System Prompt (base) ───────────────────────────────────────────
SYSTEM_PROMPT_BASE = """You are Daraz AI — a fast, friendly Pakistani e-commerce shopping assistant.
You help customers find products, compare prices, track shipments, and make purchase decisions.
Always respond in a helpful, concise, and conversational tone.
If you used tool outputs to answer, cite the data naturally — do not dump raw JSON.
When the user speaks Urdu or Roman Urdu, reply in the same language."""
