# 🛍️ Daraz Voice Assistant

**CS 4063 — Natural Language Processing | Assignment 3**  
**Final Submission | March 29, 2026**

> A low-latency, voice-to-voice conversational shopping assistant running entirely on CPU using locally deployed open-weights models. No RAG, no external APIs, no cloud inference.

**Live Demo:** [daraz-voice-assistant.vercel.app](https://daraz-voice-assistant.vercel.app)

---

## 👥 Team & Contribution Matrix

| Member | Role | Files Owned |
|--------|------|-------------|
| **Awwab** | Backend & Infrastructure | `main.py`, `routes.py`, `config.py`, `context.py`, `Dockerfile`, `docker-compose.yml` |
| **Uwaid** | Model Engine | `engine.py` (STT + LLM + TTS implementations), `models/` |
| **Rayan** | Frontend | `frontend/` (React voice UI, MediaRecorder, audio playback), `database.py`, `locustfile.py`, `benchmark_full.py` |

---

## 🏗️ Architecture

```
Browser (React Voice UI)
    │
    │  WebSocket  ws://host/ws/chat?session_id=uuid
    │  binary frames (WebM/WAV audio) ──► backend
    │  binary frames (WAV audio)      ◄── backend
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  nginx  (port 80)                                   │
│  • Reverse proxy to backend bridge                  │
│  • Serves frontend static assets                    │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  FastAPI Backend  (port 8000)                       │
│                                                     │
│  Middleware stack:                                  │
│    1. PayloadSizeLimit  → reject > 1 MB             │
│    2. SlowAPI           → per-IP rate limiting      │
│    3. CORS              → strict origin locking     │
│                                                     │
│  /ws/chat  ──► VoiceEngine.process_audio()          │
│                      │                              │
│            ┌─────────▼──────────┐                  │
│            │  transcribe_audio  │                  │
│            │  Moonshine ASR     │                  │
│            └─────────┬──────────┘                  │
│            ┌─────────▼──────────┐                  │
│            │  _generate_text    │                  │
│            │  llama-cpp Qwen    │                  │
│            └─────────┬──────────┘                  │
│            ┌─────────▼──────────┐                  │
│            │  synthesize_speech │                  │
│            │  Piper TTS         │                  │
│            └─────────┬──────────┘                  │
│                      │ WAV response                 │
└──────────────────────┼──────────────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Redis  (Session hot cache) │
        │  SQLite (Cold persistence)  │
        └─────────────────────────────┘
```

---

## 📋 Assignment Constraints Summary

| Constraint | Implementation Detail |
|-----------|-----------------------|
| **No RAG** | Core prompt engineering + state-aware sliding window context. |
| **Self-Hosted** | All models run locally via `llama-cpp-python` (LLM), `moonshine-onnx` (STT), and `faster-piper` (TTS). |
| **CPU-Only** | Quantized GGUF (Q4_K_M) and optimized ONNX models for real-time CPU performance. |
| **Concurrency** | Tested for 4+ concurrent users via async FastAPI + Redis session isolation. |
| **State Management** | `<STATE>` tag extraction logic persists budget/preferences to Redis for immediate recall. |

---

## 📁 Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/routes.py        # WebSocket & REST endpoints
│   │   ├── core/config.py       # Engine & Security constants
│   │   ├── llm/engine.py        # STT → LLM → TTS Orchestration
│   │   ├── memory/              # Redis (hot) & SQLite (cold) layers
│   │   └── main.py              # FastAPI app lifecycle
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                    # React + Vite + Framer Motion
├── models/                      # Local weight storage (Moonshine, GGUF, Piper)
├── nginx/                       # Proxy configuration
├── locustfile.py                # Performance testing suite
└── docker-compose.yml           # Full stack orchestration
```

---

## 🚀 Performance Benchmarks

Measured on a standard dual-core CPU with 8GB RAM. Latency represents the end-to-end "Silence-to-Speech" delay for a standard 2-sentence turn.

| Metric | LLM Token Gen (ms) | Full Pipeline STT+LLM+TTS (ms) |
|--------|-------------------|--------------------------------|
| **Average** | 12,402 | 17,245 |
| **p50 (Median)** | 13,567 | 18,367 |
| **p95** | 16,882 | 21,882 |
| **Min** | 6,427 | 9,842 |
| **Max** | 16,882 | 21,882 |

---

## 🛠️ Installation & Setup

### Prerequisites
- Docker & Docker Compose
- Model files placed in `./models/`:
  - `qwen2.5-3b-instruct-q4_k_m.gguf`
  - `en_US-lessac-medium.onnx`

### 1. Clone

```bash
git clone https://github.com/AWW4B/secure-scalable-voice-agent.git
cd secure-scalable-voice-agent
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your JWT_SECRET and FRONTEND_ORIGIN
```

### 3. Launch Stack
```bash
docker compose up --build
```

### 4. Access
- **Frontend UI:** `http://localhost/ui`
- **API Docs:** `http://localhost:8000/docs`
- **Health Check:** `http://localhost:8000/health`

---

## 🧪 Load Testing

Run the performance suite with 4 concurrent users:
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi "uvicorn[standard]" uvloop
pip install llama-cpp-python    # compiles C++ — takes 2-5 min
pip install redis slowapi bleach "python-jose[cryptography]"
pip install locust websocket-client

# Freeze
pip freeze > requirements.txt

# Run Redis in Docker while developing locally
docker run -d -p 6379:6379 redis:7.2-alpine

# Start backend
uvicorn app.main:app --reload --port 8000
```

---

## 📡 API Reference

### WebSocket — `ws://host/ws/chat`

The primary voice endpoint. Connect with your session ID in the query string:

```
ws://localhost:8000/ws/chat?session_id=<uuid>
```

**Voice mode** (binary frames — primary A3 flow):

```
Client ──► binary frame   raw audio bytes (WebM/WAV from MediaRecorder)
Client ◄── binary frame   WAV audio bytes (TTS response)
Client ◄── text frame     {"event":"turn_complete","status":"active","turns_used":1,"turns_max":15}
```

**Text fallback mode** (JSON frames — Postman / debug):

```
Client ──► text frame  {"session_id":"uuid","message":"I need a laptop"}
Client ◄── text frame  {"token":"Great","done":false}    ← one per token
Client ◄── text frame  {"token":"","done":true,"full_response":"...","latency_ms":1240}
```

### REST Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| `GET` | `/health` | — | Server + Redis status |
| `POST` | `/chat` | 10/min | Text-in/text-out fallback |
| `GET` | `/session/welcome/{id}` | 30/min | Welcome message + session init |
| `POST` | `/reset` | 20/min | Clear session (New Chat button) |
| `GET` | `/sessions` | 30/min | List all sessions from SQLite |
| `GET` | `/sessions/{id}` | 30/min | Full history + state |
| `DELETE` | `/sessions/{id}` | 20/min | Delete permanently |
| `POST` | `/auth/login` | 5/min | JWT → HttpOnly cookie |
| `POST` | `/auth/refresh` | 10/min | Refresh JWT |
| `POST` | `/auth/logout` | — | Clear auth cookie |
| `POST` | `/benchmark?runs=N` | 5/min | Latency benchmark (N = 1–20) |
| `POST` | `/debug/warmup` | — | Warm up LLM KV cache |
| `GET` | `/debug/state/{id}` | — | Extracted budget/item/preferences |
| `GET` | `/debug/history/{id}` | — | Raw message history |

---

## 🔒 Security

| Feature | File | What it does |
|---------|------|-------------|
| Payload size limit | `main.py` | Rejects bodies > 1 MB with HTTP 413 before any handler runs |
| Rate limiting | `main.py` + `routes.py` | Per-IP limits via `slowapi` — 10/min chat, 5/min login |
| Strict CORS | `main.py` | Only `FRONTEND_ORIGIN` env var is allowed, no wildcard |
| Input sanitization | `routes.py` + `database.py` | `bleach.clean()` strips all HTML/JS before LLM and before DB write |
| Token truncation | `config.py` | Hard-caps user input to `N_CTX / 2` tokens — prevents context overflow attacks |
| JWT + HttpOnly cookies | `routes.py` | Tokens in HttpOnly cookies — inaccessible to JavaScript (XSS-safe) |
| Redis session isolation | `context.py` | Namespaced keys per session — concurrent users fully isolated |
| Non-root Docker user | `Dockerfile` | App runs as `appuser`, not root |

---

## 📊 Performance Benchmarks

```bash
# Step 1 — warmup (always do this first or first run will be slow)
curl -X POST http://localhost:8000/debug/warmup

# Step 2 — run benchmark
curl -X POST "http://localhost:8000/benchmark?runs=10"
```

| Metric | LLM only (ms) | Full pipeline STT+LLM+TTS (ms) |
|--------|:---:|:---:|
| Average | 12,402 | 3,118 |
| p50 | 13,567 | 2,840 |
| p95 | 16,882 | 3,886 |
| Min | 6,427 | 2,629 |
| Max | 16,882 | 3,886 |

> [!NOTE] 
> These benchmarks were recorded on CPU using the Qwen-2.5-3B model. While the assignment target is **< 1000 ms**, the local CPU execution time is considerably higher due to the hardware constraints. The Full Pipeline (STT+LLM+TTS) currently exceeds the 15s timeout in some cases.

Assignment target: **< 1000 ms** end-to-end per turn.

---

## 🦗 Load Testing

Simulates 4 concurrent users (3 REST + 1 WebSocket) as required by the assignment.

```bash
pip install locust websocket-client

# Interactive dashboard at http://localhost:8089
locust -f locustfile.py --host=http://localhost:8000
# Set: Users=4, Spawn rate=1, Duration=60s

# Headless — saves CSV to results/
locust -f locustfile.py --host=http://localhost:8000 \
       --users 4 --spawn-rate 1 --run-time 60s --headless \
       --csv=results/locust_report
```

---

## 🧪 Postman Collection

Import `daraz_assistant_a3.postman_collection.json` into Postman.

Set the collection variable `base_url = http://localhost:8000` then run requests **1 → 20 in order**. The session ID is auto-captured from request 6 (Welcome Message) and reused automatically for all subsequent requests.

Covers: health check, JWT auth cookies, full conversation flow, XSS sanitization check, payload rejection (413), rate limit trigger (429), and latency benchmarks with console output.

---

## 🐳 Docker Reference

```bash
# Start all services
docker compose up --build

# Rebuild backend only after code changes
docker compose up --build backend

# Live logs
docker compose logs -f backend
docker compose logs -f redis

# Stop
docker compose down

# Stop and wipe all volumes (fresh start)
docker compose down -v
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection — auto-set in Docker Compose |
| `MODEL_PATH` | `/models/qwen2.5-3b-instruct-q4_k_m.gguf` | Model path (LLM GGUF) |
| `PIPER_MODEL` | `/models/en_US-lessac-medium.onnx` | Model path (Piper TTS ONNX) |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | Frontend CORS origin (local or Vercel) |
| `JWT_SECRET` | `CHANGE_ME_IN_PRODUCTION` | Change to any long random string before deploying |
| `PYTHONUNBUFFERED` | `1` | Ensures Docker logs appear immediately |

---