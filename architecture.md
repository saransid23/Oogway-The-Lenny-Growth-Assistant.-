# Architecture Specification
## The Lenny Growth Assistant

---

## 1. System Topology & Component Boundaries

```
 +-----------------------------------------------------------------------+
 |                     BROWSER FRONTEND (HTML / CSS / JS)               |
 |  +--------------------+  +--------------------+  +-----------------+  |
 |  |  Chat Interface    |  | Model Selector UI  |  | Artifact Viewer |  |
 |  +--------------------+  +--------------------+  +-----------------+  |
 +-----------------------------------:-----------------------------------+
                                     | HTTP / REST API
 +-----------------------------------v-----------------------------------+
 |                        FASTAPI BACKEND SERVER                        |
 |  +--------------------+  +--------------------+  +-----------------+  |
 |  | Session & Chat API |  | Ship 30 Skill API  |  | Artifact API    |  |
 |  +---------:----------+  +---------:----------+  +--------:--------+  |
 |            |                       |                      |           |
 |  +---------v-----------------------v----------------------v--------+  |
 |  |                      ORCHESTRATOR LAYER                         |  |
 |  |  - RAG Retriever Engine (data/transcripts/*.json)               |  |
 |  |  - Unified LLM Provider (Ollama Local / OpenAI Cloud / Fallback)|  |
 |  |  - Artifact Extraction & Security Sanitization                 |  |
 |  +---------------------------------:-------------------------------+  |
 +------------------------------------:----------------------------------+
                                      | SQLAlchemy ORM
 +------------------------------------v----------------------------------+
 |                   DATABASE PERSISTENCE ENGINE                         |
 |  - SQLite (default for zero-config local run)                         |
 |  - PostgreSQL (supported via DATABASE_URL env)                        |
 +-----------------------------------------------------------------------+
```

---

## 2. Database Schema

### `sessions` Table
- `id` (VARCHAR(36), PK): UUID session identifier
- `title` (VARCHAR(255)): Conversation title
- `created_at` (TIMESTAMP): Session creation timestamp
- `updated_at` (TIMESTAMP): Last message timestamp
- `provider` (VARCHAR(50)): Active LLM provider (`local` / `cloud`)
- `model_name` (VARCHAR(100)): Active model name (`mistral` / `gpt-4o-mini`)

### `messages` Table
- `id` (VARCHAR(36), PK): Message UUID
- `session_id` (VARCHAR(36), FK -> sessions.id): Related session
- `sender` (VARCHAR(20)): `user` or `assistant`
- `content` (TEXT): Message content (markdown)
- `citations_json` (TEXT): JSON serialized list of source citations
- `artifact_id` (VARCHAR(36), FK -> artifacts.id, Nullable): Linked artifact

### `artifacts` Table
- `id` (VARCHAR(36), PK): Artifact UUID
- `session_id` (VARCHAR(36), FK -> sessions.id): Related session
- `title` (VARCHAR(255)): Artifact display name
- `artifact_type` (VARCHAR(50)): `html` or `markdown`
- `content` (TEXT): Code content
- `created_at` (TIMESTAMP): Generation timestamp

---

## 3. RAG Retrieval & Citation Flow

1. User sends query string to `/api/chat`.
2. `TranscriptRetriever` queries Ollama `nomic-embed-text` for the 768-dimensional query vector and tokenizes query terms.
3. Chunks are scored via **Hybrid Evaluation**:
   - **Semantic Cosine Similarity**: Compares query vector with pre-cached transcript chunk embeddings (`0.60` weight).
   - **Lexical Keyword Weighting**: Evaluates guest match (+3.0), topic match (+2.5), title match (+2.0), and text frequency (+2.0) (`0.40` weight).
   - **Automatic Resilience**: If Ollama embeddings are unavailable, automatically falls back to 100% lexical TF-IDF scoring.
4. Top 3 matching chunks are extracted and formatted into structured prompt context.
5. `LLMProvider` generates response and attaches structured `Citation` objects (Guest, Title, Timestamp, Excerpt Quote).

---

## 4. Security & Artifact Sandboxing Strategy

- **Threat**: Executing arbitrary LLM-generated HTML/CSS/JS code directly in the main web page window exposes the app to Cross-Site Scripting (XSS), cookie theft, and DOM manipulation.
- **Sanitization Strategy**:
  - All rendered HTML artifacts are served inside an `<iframe>` container.
  - The iframe includes strict security attributes: `sandbox="allow-scripts"`.
  - **Explicit Exclusion**: `allow-same-origin` is omitted. This ensures the executed iframe content operates in a unique opaque origin, blocking access to `window.parent`, `localStorage`, `sessionStorage`, cookies, and local domain APIs.

---

## 5. REST API Endpoints Specification

| Method | Endpoint | Request Body | Response Body | Description |
|:---|:---|:---|:---|:---|
| `GET` | `/api/health` | None | `{status, service, transcripts_loaded, ollama_status, database_status}` | Operational health and readiness probe |
| `GET` | `/api/models` | None | `{default_provider, providers: {local: {...}, cloud: {...}}}` | Discoverable model and provider metadata |
| `POST` | `/api/sessions` | `{title?: string}` | `{id, title, created_at, updated_at, provider, model_name}` | Initializes an isolated conversational session |
| `GET` | `/api/sessions` | None | `Array<SessionResponse>` | Lists recent sessions ordered by `updated_at DESC` |
| `GET` | `/api/sessions/{id}/messages` | None | `Array<MessageResponse>` | Retrieves ordered conversation history for session |
| `DELETE` | `/api/sessions/{id}` | None | `{status: "deleted", session_id}` | Cascading deletion of session, messages, and artifacts |
| `POST` | `/api/chat` | `{session_id?: string, message: string, provider?: string, model?: string}` | `{reply: string, session_id: string, citations: [...], artifact?: {...}}` | Main RAG conversation pipeline with citations & artifacts |
| `POST` | `/api/skills/ship30` | `{session_id?: string, topic: string, target_audience?: string}` | `{reply: string, session_id: string, citations: [...], artifact?: {...}}` | Synthesizes ~1,250-word Ship 30 essay artifact |
| `GET` | `/api/artifacts/{id}` | None | `{id, session_id, title, artifact_type, content, created_at}` | Fetches raw artifact content |
| `GET` | `/api/ingest` | None | `{status, total_chunks, transcripts: [...]}` | Reports knowledge base indexing status |

---

## 6. Agent Routing & Model Toggle Layer

```mermaid
flowchart TD
    UserQuery[User Chat / Skill Request] --> Router[API Router Layer]
    Router --> KBRetriever[TranscriptRetriever TF-IDF]
    KBRetriever --> RAGContext[Grounded Transcripts & Citations]
    
    RAGContext --> ModelToggle{Active Provider Setting}
    
    ModelToggle -->|Provider == 'local'| OllamaCheck{Ollama Accessible?}
    OllamaCheck -->|Yes| OllamaExec[Ollama Local Client: mistral/llama3]
    OllamaCheck -->|No / Offline| Fallback1[Deterministic RAG Fallback Synthesizer]
    
    ModelToggle -->|Provider == 'cloud'| CloudCheck{API Key Configured?}
    CloudCheck -->|Yes| CloudExec[OpenAI gpt-4o-mini / Anthropic Sonnet]
    CloudCheck -->|No / Key Missing| Fallback2[Deterministic RAG Fallback Synthesizer]
    
    OllamaExec --> ArtifactExtractor[Artifact Extractor & Sanitizer]
    CloudExec --> ArtifactExtractor
    Fallback1 --> ArtifactExtractor
    Fallback2 --> ArtifactExtractor
    
    ArtifactExtractor --> Response[Response JSON + Sandboxed HTML/Markdown Artifact]
```

---

## 7. Deployment Topology

### Mode 1: Bare Metal / Local Python
- Host runs Python 3.10+ directly with Uvicorn worker process.
- Database: local SQLite database file (`./lenny_assistant.db`).
- Ollama: runs as local background daemon on `http://127.0.0.1:11434`.

### Mode 2: Docker Compose Containerization
- Container: `lenny_growth_assistant` built from multi-stage lightweight Python Dockerfile.
- Port: `8000:8000`.
- Ollama Network Bridge: Host Ollama accessed via `http://host.docker.internal:11434`.
- Volumes:
  - `./data` mounted into `/app/data` (read/write transcript ingestion).
  - `./lenny_assistant.db` mounted into `/app/lenny_assistant.db` (state persistence across restarts).

