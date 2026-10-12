import json
import math
import asyncio
import pytest
import httpx
from sqlalchemy import inspect, text
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import engine, init_db, SessionLocal, SessionModel, MessageModel, ArtifactModel
from app.rag.knowledge_base import KnowledgeBase, TranscriptChunk
from app.rag.retriever import TranscriptRetriever, retriever
from app.llm.ollama_client import OllamaClient

client = TestClient(app)

# -------------------------------------------------------------
# 1. Vectorized semantic scores equal a pure-Python cosine
# -------------------------------------------------------------
def test_vectorized_semantic_scores_equal_pure_python():
    kb = KnowledgeBase(data_dir="data/transcripts")
    assert len(kb.chunks) > 0

    first_chunk = kb.chunks[0]
    dim = len(first_chunk.embedding) if first_chunk.embedding else 768
    
    # Deterministic query vector
    query_vec = [math.sin(i * 0.1) for i in range(dim)]

    result = kb.semantic_scores(query_vec)
    assert result is not None, "semantic_scores should return a tuple"
    scores, has_score = result

    for idx, chunk in enumerate(kb.chunks):
        if chunk.embedding and has_score[idx]:
            pure_score = TranscriptRetriever._cosine_similarity(query_vec, chunk.embedding)
            vec_score = float(scores[idx])
            assert abs(vec_score - pure_score) <= 1e-4, f"Mismatch at index {idx}: {vec_score} vs {pure_score}"


# -------------------------------------------------------------
# 2. Missing and mismatched-dimension embeddings handled
# -------------------------------------------------------------
def test_missing_and_mismatched_dimension_embeddings_handled():
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb.data_dir = "data/transcripts"
    kb._seen_hashes = set()
    kb._chunk_map = {}
    kb._matrix = None
    kb._matrix_indices = []
    kb._embedding_dim = None
    kb._indexed_chunk_count = None

    c1 = TranscriptChunk("c1", "t1", "Ep 1", "Guest 1", "2023", "", "00:00", "Topic", "Text 1")
    c1.embedding = [1.0, 0.0, 0.0, 0.0]

    c2 = TranscriptChunk("c2", "t1", "Ep 1", "Guest 1", "2023", "", "00:00", "Topic", "Text 2")
    c2.embedding = None  # Missing embedding

    c3 = TranscriptChunk("c3", "t1", "Ep 1", "Guest 1", "2023", "", "00:00", "Topic", "Text 3")
    c3.embedding = [0.0, 1.0, 0.0, 0.0]

    kb.chunks = [c1, c2, c3]

    # Valid 4-dim query
    res = kb.semantic_scores([1.0, 0.0, 0.0, 0.0])
    assert res is not None
    scores, has_score = res
    assert has_score[0] is True or has_score[0] == 1
    assert has_score[1] is False or has_score[1] == 0
    assert has_score[2] is True or has_score[2] == 1
    assert abs(scores[0] - 1.0) < 1e-4
    assert scores[1] == 0.0

    # Mismatched dimension (e.g. 5 dims)
    assert kb.semantic_scores([1.0, 0.0, 0.0, 0.0, 0.0]) is None

    # None query
    assert kb.semantic_scores(None) is None

    # Index rebuilds when chunks change
    c4 = TranscriptChunk("c4", "t1", "Ep 1", "Guest 1", "2023", "", "00:00", "Topic", "Text 4")
    c4.embedding = [0.0, 0.0, 1.0, 0.0]
    kb.chunks.append(c4)

    res_new = kb.semantic_scores([0.0, 0.0, 1.0, 0.0])
    assert res_new is not None
    scores_new, has_score_new = res_new
    assert len(scores_new) == 4
    assert abs(scores_new[3] - 1.0) < 1e-4


# -------------------------------------------------------------
# 3. asearch and search return same ranking & whitespace cache
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_asearch_and_search_return_same_ranking_and_cache_hit():
    query = "Shreyas Doshi LNO framework"

    # Deterministic mock embedding to compare ranking algorithmically
    dim = 768
    fixed_embedding = [0.05] * dim

    test_retriever = TranscriptRetriever()
    test_retriever._get_query_embedding_sync = lambda q: fixed_embedding

    async def mock_async_embed(q):
        return fixed_embedding
    test_retriever._get_query_embedding_async = mock_async_embed

    chunks_sync, cit_sync = test_retriever.search(query, top_k=3)
    chunks_async, cit_async = await test_retriever.asearch(query, top_k=3)

    assert [c.chunk_id for c in chunks_sync] == [c.chunk_id for c in chunks_async]
    assert [c.score for c in cit_sync] == [c.score for c in cit_async]

    # Test whitespace-normalized cache key hit
    cache_retriever = TranscriptRetriever()
    cache_retriever._save_cache("shreyas doshi lno framework", fixed_embedding)
    
    # Query with irregular whitespace and casing
    whitespace_query = "   Shreyas   Doshi   LNO   framework   "
    assert cache_retriever._check_cache(cache_retriever._normalize_key(whitespace_query)) == fixed_embedding


# -------------------------------------------------------------
# 4. Failure back-off and bounded cache
# -------------------------------------------------------------
def test_embedding_failure_backoff_and_bounded_cache():
    tr = TranscriptRetriever()
    assert tr._is_backing_off() is False

    # Record failure
    tr._record_failure()
    assert tr._is_backing_off() is True

    # During back-off, sync getter immediately returns None without external call
    res = tr._get_query_embedding_sync("any query")
    assert res is None

    # Verify cache size is bounded
    capacity = settings.EMBED_CACHE_SIZE
    for i in range(capacity + 25):
        tr._save_cache(f"query_{i}", [float(i)])

    assert len(tr._embed_cache) <= capacity
    # Latest item should exist, earliest should have been evicted
    assert f"query_{capacity + 24}" in tr._embed_cache
    assert "query_0" not in tr._embed_cache


# -------------------------------------------------------------
# 5. Ollama stream_generate parses NDJSON, sends options, handles 500
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_stream_generate_with_mock_transport():
    received_requests = []

    def mock_handler(request: httpx.Request):
        received_requests.append(request)
        if request.url.path == "/api/generate":
            payload = json.loads(request.content.decode("utf-8"))
            if payload.get("prompt") == "trigger_error":
                return httpx.Response(500, json={"error": "Internal Ollama Error"})
            
            ndjson_content = (
                b'{"response":"The ","done":false}\n'
                b'{"response":"LNO ","done":false}\n'
                b'{"response":"framework","done":true}\n'
            )
            return httpx.Response(200, content=ndjson_content)
        return httpx.Response(404)

    client_mock = OllamaClient()
    mock_transport = httpx.MockTransport(mock_handler)
    client_mock._client = httpx.AsyncClient(transport=mock_transport)
    client_mock._client_loop = asyncio.get_running_loop()

    # 1. Successful NDJSON streaming
    tokens = []
    async for t in client_mock.stream_generate("Explain LNO"):
        tokens.append(t)

    assert tokens == ["The ", "LNO ", "framework"]
    assert len(received_requests) == 1

    req_data = json.loads(received_requests[0].content.decode("utf-8"))
    assert req_data["stream"] is True
    assert req_data["keep_alive"] == settings.OLLAMA_KEEP_ALIVE
    assert req_data["options"]["num_predict"] == settings.OLLAMA_NUM_PREDICT

    # 2. HTTP 500 yields nothing cleanly without raising
    tokens_err = []
    async for t in client_mock.stream_generate("trigger_error"):
        tokens_err.append(t)

    assert tokens_err == []


# -------------------------------------------------------------
# 6. Database indexes exist on messages, artifacts, and sessions
# -------------------------------------------------------------
def test_database_indexes_exist():
    init_db()
    inspector = inspect(engine)

    messages_indexes = [idx["name"] for idx in inspector.get_indexes("messages")]
    artifacts_indexes = [idx["name"] for idx in inspector.get_indexes("artifacts")]
    sessions_indexes = [idx["name"] for idx in inspector.get_indexes("sessions")]

    assert any("idx_messages_session_id_created_at" in name for name in messages_indexes)
    assert any("idx_artifacts_session_id" in name for name in artifacts_indexes)
    assert any("idx_sessions_updated_at" in name for name in sessions_indexes)


# -------------------------------------------------------------
# 7. /api/chat/stream emits meta, token, done for off-topic query
# -------------------------------------------------------------
def test_chat_stream_off_topic_emits_expected_events_and_persists():
    unsupported_query = "Quantum physics superstring theory dilution refrigerators"
    response = client.post(
        "/api/chat/stream",
        json={"message": unsupported_query, "provider": "local"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse SSE stream chunks
    events = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_type = line.replace("event:", "").strip()
            elif line.startswith("data:"):
                data = json.loads(line.replace("data:", "").strip())
        if event_type:
            events.append((event_type, data))

    event_types = [e[0] for e in events]
    assert "meta" in event_types
    assert "token" in event_types
    assert "done" in event_types

    # First event should be meta
    meta_event = next(e[1] for e in events if e[0] == "meta")
    assert meta_event["evidence_found"] is False

    # Done event should have structured data
    done_event = next(e[1] for e in events if e[0] == "done")
    assert done_event["evidence_found"] is False
    assert len(done_event["citations"]) == 0
    assert "Insufficient Transcript Evidence" in done_event["reply"]

    # Verify session and message persistence in DB
    session_id = done_event["session_id"]
    db = SessionLocal()
    try:
        msgs = db.query(MessageModel).filter(MessageModel.session_id == session_id).all()
        assert len(msgs) >= 2  # user and assistant
    finally:
        db.close()


# -------------------------------------------------------------
# 8. /api/sessions returns correct message_count
# -------------------------------------------------------------
def test_list_sessions_returns_correct_message_count():
    db = SessionLocal()
    try:
        test_session = SessionModel(title="Count Test Session", provider="local", model_name="mistral")
        db.add(test_session)
        db.commit()
        db.refresh(test_session)

        m1 = MessageModel(session_id=test_session.id, sender="user", content="Hello 1")
        m2 = MessageModel(session_id=test_session.id, sender="assistant", content="Hello 2")
        m3 = MessageModel(session_id=test_session.id, sender="user", content="Hello 3")
        db.add_all([m1, m2, m3])
        db.commit()

        target_id = test_session.id
    finally:
        db.close()

    res = client.get("/api/sessions")
    assert res.status_code == 200
    sessions_data = res.json()
    match = next((s for s in sessions_data if s["id"] == target_id), None)
    assert match is not None
    assert match["message_count"] == 3
