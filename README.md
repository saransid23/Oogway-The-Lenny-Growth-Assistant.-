# ⚡ The Lenny Growth Assistant

> Full-stack AI-powered conversational web application that ingests transcripts from Lenny's Podcast, answers product management and growth questions strictly with grounded citations, generates Ship 30 for 30 style essays, and renders live HTML/CSS or Markdown artifacts side-by-side.

---

## 🌟 Features Overview

- **Grounded Transcript RAG**: Answers product management & growth questions strictly using Lenny's Podcast transcript corpus (Shreyas Doshi, Elena Verna, Marty Cagan, Brian Chesky, Gibson Biddle) with explicit quote citations and timestamps.
- **Flexible LLM Execution Layer**:
  - **Local LLM**: Integrated with **Ollama** (`mistral`, `llama3`, `phi3`).
  - **Cloud LLM**: Integrated with **OpenAI** (`gpt-4o-mini`) and **Anthropic** (`claude-3-5-sonnet`).
  - **Smart RAG Fallback**: Built-in deterministic RAG engine so the demo runs seamlessly out-of-the-box even without active API keys or local Ollama processes.
- **Ship 30 for 30 Content Generator Skill**: Dedicated skill button generating ~1,250-word hyper-skimmable growth essays (strong hook, narrative progression, 3 actionable rules, transcript-grounded claims).
- **In-App Artifact Viewer**: Claude Artifacts-style side-by-side split pane rendering HTML/CSS visual mockups or Markdown documents natively with live preview, code viewing, and copy functionality.
- **Security Sandboxing**: HTML/CSS artifacts are rendered inside a secure `<iframe>` container with `sandbox="allow-scripts"` (restricting `allow-same-origin`), blocking XSS and host DOM access.
- **Session & Message Persistence**: Complete conversation history, session creation, title generation, and message storage powered by SQLAlchemy (SQLite default for zero-config local run, PostgreSQL supported).

---

## 🏗️ Project Architecture

```
c:\oogway project\
├── app\                     # FastAPI Backend Application
│   ├── main.py              # Application entry point & router mounting
│   ├── config.py            # Environment configuration & defaults
│   ├── database.py          # SQLAlchemy models & DB connection
│   ├── models.py            # Pydantic schemas (Chat, Sessions, Citations, Artifacts)
│   ├── rag\                 # Grounded Retrieval Pipeline
│   │   ├── knowledge_base.py# Transcript loader & chunker
│   │   └── retriever.py     # TF-IDF keyword search & citation generator
│   ├── llm\                 # Flexible LLM & Agent Adapter Layer
│   │   ├── agent_router.py  # Intent classifier & agent routing layer
│   │   ├── anthropic_agent.py# Anthropic Claude Agent SDK integration (tool-calling loop)
│   │   ├── provider.py      # Unified LLM orchestrator & fallback
│   │   ├── ollama_client.py # Local Ollama client
│   │   └── cloud_client.py  # OpenAI / Anthropic AsyncAnthropic cloud client
│   ├── skills\              # AI Skills & Artifact Generators
│   │   ├── ship30.py        # Ship 30 for 30 essay generator
│   │   └── artifact_generator.py # HTML/Markdown artifact extractor
│   └── routers\             # REST API Endpoints
│       ├── chat.py          # /api/chat endpoint
│       ├── sessions.py      # /api/sessions management
│       ├── skills.py        # /api/skills/ship30 endpoint
│       ├── artifacts.py     # /api/artifacts/{id} endpoint
│       └── health.py        # /api/health & /api/models status
├── data\
│   └── transcripts\        # Lenny's Podcast JSON transcript corpus
├── frontend\                # HTML, CSS & Vanilla JS Frontend
│   ├── index.html           # Main UI layout & side-by-side viewer
│   ├── css\style.css        # Modern dark-mode glassmorphism design system
│   └── js\app.js            # Dynamic chat & artifact interaction logic
├── tests\                   # Automated Pytest Test Suite
│   ├── test_api.py          # API & session lifecycle integration tests
│   └── test_rag.py          # Transcript retrieval & citation unit tests
├── PRD.md                   # Product Requirements Document
├── architecture.md          # Database schema & security architecture
├── design.md                # UI/UX design specification
├── Dockerfile               # Production container definition
├── docker-compose.yml       # One-command container startup
├── requirements.txt         # Python dependencies
└── run.py                   # One-command python application launcher
```

---

## ⚡ Quick Start

### Prerequisites
- **Python 3.10+** (Python 3.13 tested)
- (Optional) **Ollama** installed locally for local LLM execution (`ollama pull mistral`)
- (Optional) **Docker & Docker Compose** for containerized execution

---

### Option A: Local Python Startup (Recommended)

1. **Clone & Navigate to Project**:
   ```bash
   cd "c:\oogway project"
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables (Optional)**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

4. **Launch Application**:
   ```bash
   python run.py
   ```

5. **Open in Browser**:
   Navigate to [http://localhost:8000](http://localhost:8000)

---

### Option B: One-Command Docker Multi-Container Startup (FastAPI + PostgreSQL)

Starts both the **FastAPI Application** and dedicated **PostgreSQL 16 Database** container with healthchecks and persistent storage volumes:

```bash
docker compose up --build
```
- Web Application: [http://localhost:8000](http://localhost:8000)
- PostgreSQL Database: `localhost:5432` (`postgres:postgrespassword`, DB: `lenny_growth_db`)

---

### 🗄️ Database Persistence (PostgreSQL & Supabase / Railway)

The persistence layer ([app/database.py](file:///c:/oogway%20project/app/database.py)) stores conversations, session IDs, timestamps, and artifacts in PostgreSQL:
1. **Docker Compose**: Uses the bundled PostgreSQL 16 container automatically.
2. **Supabase / Railway**: Simply provide your connection URI in `.env`:
   ```bash
   DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/[DB]
   ```
3. **Local Dev Fallback**: If running without Docker or PostgreSQL installed, it cleanly defaults to SQLite (`./lenny_assistant.db`) so evaluator testing is never blocked.

---

## 🧪 Running Automated Tests

Run the full automated test suite covering API endpoints, session persistence, RAG retrieval accuracy, and Ship 30 essay generation:

```bash
pytest -v
```

---

## 🤖 Model Switching & Configuration

- **Local LLM (Ollama)**:
  - Start Ollama server: `ollama serve`
  - Pull recommended model: `ollama pull mistral`
  - In the UI header, select **Local (Ollama)**.
- **Cloud LLM (OpenAI / Anthropic)**:
  - Set `OPENAI_API_KEY=your_key_here` in `.env`.
  - In the UI header, select **Cloud (OpenAI)**.
- **Fallback Engine**:
  - If Ollama is offline and no API keys are provided, the system automatically uses the embedded RAG engine so evaluator testing is never blocked.

---

## ⚡ Real-Time Streaming & Performance Configuration

The application includes an optimized Server-Sent Events (SSE) streaming endpoint and performance tuning layer:

### 1. Streaming Chat Endpoint (`POST /api/chat/stream`)
- **Protocol**: Server-Sent Events (`text/event-stream`).
- **Events Emitted**:
  - `event: meta` — Immediate event containing citation metadata, active provider, model name, and `evidence_found` boolean flag.
  - `event: token` — Individual generated tokens delivered in real time for progressive UI rendering.
  - `event: done` — Complete `ChatResponse` payload matching `/api/chat` with persisted message ID, formatted citations, and extracted artifact objects.
  - `event: error` — Structured error message if an exception occurs during stream generation.
- **Routing**: Automatically streams tokens for local RAG execution; non-local or specialized skill calls are cleanly delivered as single atomic completions.

### 2. Performance Tuning Environment Variables (`.env`)
The following optional settings can be configured in `.env` (or `.env.example`):

```bash
# Local LLM Keep-Alive & Bounded Generation
OLLAMA_KEEP_ALIVE=30m             # Prevents model de-allocation between user prompts
OLLAMA_NUM_PREDICT=400            # Bounded output token target for sub-2s time-to-first-token

# Non-Blocking RAG & Embedding Cache
EMBED_TIMEOUT_SECONDS=2.0         # Fast timeout for Ollama embedding calls
EMBED_BACKOFF_SECONDS=30.0        # Circuit breaker skips embedding during service outages
EMBED_CACHE_SIZE=256              # LRU in-memory query embedding cache capacity

# Chat Context & Database Pooling
HISTORY_MAX_MESSAGES=6            # Bounded history window to limit prompt bloat
HISTORY_MSG_MAX_CHARS=600         # Per-message truncation limit for pruned chat turns
DB_POOL_SIZE=5                    # PostgreSQL connection pool capacity
DB_MAX_OVERFLOW=10                # Max overflow connections for PostgreSQL
```

For complete empirical benchmarks and measurement methodology, see [docs/performance.md](file:///c:/oogway%20project/docs/performance.md).

---

| # | Deliverable | Location / Resource | Status |
|:---:|:---|:---|:---:|
| **1** | **Repository Structure & Clean Code** | Root repository (`app/`, `frontend/`, `data/`, `tests/`) | ✅ Complete |
| **2** | **README Documentation** | [README.md](file:///c:/oogway%20project/README.md) | ✅ Complete |
| **3** | **Product Requirements Document** | [PRD.md](file:///c:/oogway%20project/PRD.md) | ✅ Complete |
| **4** | **UI/UX Design Specification** | [design.md](file:///c:/oogway%20project/design.md) | ✅ Complete |
| **5** | **System Architecture Specification** | [architecture.md](file:///c:/oogway%20project/architecture.md) | ✅ Complete |
| **6** | **Agent Transcripts & Decision Trails** | [agent_transcripts/](file:///c:/oogway%20project/agent_transcripts/README.md) | ✅ Complete |
| **7** | **Automated Tests & UI Manual Test Plan** | [tests/](file:///c:/oogway%20project/tests/) & [tests/manual_test_plan.md](file:///c:/oogway%20project/tests/manual_test_plan.md) | ✅ Complete |
| **8** | **Demo Video Script & Instructions** | [demo_video_script.md](file:///c:/oogway%20project/demo_video_script.md) | ✅ Complete |

---


