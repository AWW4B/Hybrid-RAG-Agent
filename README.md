# 🛍️ Hybrid RAG Voice Assistant — Daraz Shopping Agent

**CS 4063 — Natural Language Processing | Assignment 3 & 4**  
**Final Project Submission | April 20, 2026**

> A state-of-the-art, low-latency, voice-to-voice conversational shopping assistant. This project combines local LLM inference with a Hybrid RAG (Retrieval-Augmented Generation) pipeline and a multi-layered persistent memory system, all running locally on CPU.

---

## 👥 Team & Contribution Matrix

| Member | Roll No | Primary Role | Key Contributions |
|--------|---------|--------------|-------------------|
| **Awwab Ahmad** | 23i-0079 | Lead Infrastructure & Systems | System Architecture, Dockerization, 4-Layer Memory (Redis/SQLite), Admin Dashboard, CRM Extraction. |
| **Rayan** | 23i-0018 | RAG Implementation | Retrieval Pipeline, ChromaDB Integration, Semantic Search, Contextual Prompt Injection. |
| **Uwaid Muneer** | 23i-2574 | Model Engineering | [Space Reserved for Contribution Details] |

---

## 🏗️ System Architecture & Workflow

The assistant follows a sophisticated 7-step turn-based orchestration for every user interaction, ensuring high responsiveness and contextual accuracy.

1.  **Auto-Compaction**: (Awwab) Analyzing context window (N_CTX) and triggering background summarization to prevent token overflow.
2.  **RAG Retrieval**: (Rayan) Performing semantic search against the local vector database (ChromaDB) to fetch relevant product and domain knowledge.
3.  **Inference**: Orchestrating the local LLM (Qwen-2.5-3B) via `llama-cpp-python` with state-aware prompt engineering.
4.  **History Persistence**: Appending turns to the multi-stage memory system.
5.  **Micro-Compaction**: (Awwab) Real-time cleanup of ephemeral data (like raw tool results) to keep the "hot" context lean.
6.  **CRM Extraction**: (Awwab) Asynchronous background task to extract user preferences, budget, and intents into a permanent CRM store.
7.  **Speech Synthesis**: (Uwaid) Converting the assistant's text response into high-quality audio using Piper TTS.

---

## 🚀 Key Features

### 1. Advanced Memory Management (Awwab Ahmad)
- **Hot Cache (Redis)**: Sub-millisecond session state retrieval for active conversations.
- **Cold Storage (SQLite/aiosqlite)**: Permanent persistence of chat histories and user profiles.
- **Dual-Stage Compaction**: Combines token-count based summarization with periodic "micro-cleanup" of the active context window.
- **Background CRM Integration**: Non-blocking extraction of user attributes using a secondary LLM worker.

### 2. Hybrid RAG Pipeline (Rayan)
- **Vector Search**: Local ChromaDB instance indexing the Daraz product dataset.
- **Semantic Retrieval**: Uses `sentence-transformers` to map user queries to the most relevant knowledge chunks.
- **Contextual Injection**: Dynamically augmenting the system prompt with retrieved information without cluttering the long-term chat history.

### 3. Full-Stack Orchestration (Awwab Ahmad)
- **Containerization**: Multi-service Docker setup with optimized networking for sub-second latency.
- **Admin Dashboard**: A comprehensive monitoring UI to track active sessions, system health, and extracted CRM insights in real-time.
- **Security**: JWT-based authentication, HTTP-only cookies, and Pydantic-based input sanitization.

### 4. Local Model Engine (Uwaid Muneer)
- **STT**: Moonshine ASR for high-accuracy local transcription.
- **LLM**: Quantized GGUF inference (Q4_K_M) optimized for CPU.
- **TTS**: Piper ONNX for ultra-fast, natural-sounding voice responses.

---

## 🛠️ Installation & Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Local models placed in `./models/`:
  - `qwen2.5-3b-instruct-q4_k_m.gguf` (LLM)
  - `en_US-lessac-medium.onnx` (TTS)

### Quick Start
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/AWW4B/Hybrid-RAG-Agent.git
    cd Hybrid-RAG-Agent
    ```

2.  **Environment Setup**:
    ```bash
    cp .env.example .env
    # Edit .env with your JWT_SECRET and FRONTEND_ORIGIN
    ```

3.  **Build and Launch**:
    ```bash
    docker compose up --build
    ```

4.  **Access the Application**:
    - **User UI**: `http://localhost:3000`
    - **Admin Dashboard**: `http://localhost:3000` (Login with Admin credentials)
    - **API Documentation**: `http://localhost:8000/docs`

---

## 📁 Project Structure

```bash
.
├── backend/
│   ├── src/
│   │   ├── admin/           # Admin Dashboard API (Awwab)
│   │   ├── auth/            # JWT & Security (Awwab)
│   │   ├── conversation/    # Memory & Compaction (Awwab)
│   │   ├── engine/          # STT/LLM/TTS Orchestration (Uwaid/Awwab)
│   │   ├── retrieval/       # RAG Implementation (Rayan)
│   │   └── main.py          # FastAPI Core
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # ChatWidget, AdminDashboard, etc.
│   │   └── App.jsx          # Mode switching & State
│   └── Dockerfile
├── models/                  # Local weight storage
└── docker-compose.yml       # Orchestration (Awwab)
```

---

## 🔒 Performance & Constraints
- **Concurrency**: Specifically architected to handle 4+ concurrent users on standard CPU hardware via async processing and Redis session isolation.
- **Latency**: Targeted sub-second "Silence-to-Speech" response time (hardware dependent).
- **Privacy**: 100% local execution. No data leaves the containerized environment.