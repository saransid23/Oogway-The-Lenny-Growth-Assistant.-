import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_status"] == "connected"
    assert data["transcripts_loaded"] > 0

def test_liveness_and_readiness_probes():
    # Liveness probe
    res_live = client.get("/api/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    # Readiness probe
    res_ready = client.get("/api/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["ready"] is True
    assert res_ready.json()["database_ready"] is True

def test_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    provider_ids = [p["id"] for p in data["providers"]]
    assert "local" in provider_ids
    assert "cloud" in provider_ids

def test_session_lifecycle_and_isolation():
    """Requirement: Each session must maintain independent context and history."""
    # 1. Create Session A
    res_a = client.post("/api/sessions", json={"title": "Session A - Product Strategy"})
    assert res_a.status_code == 200
    id_a = res_a.json()["id"]

    # 2. Create Session B
    res_b = client.post("/api/sessions", json={"title": "Session B - Growth Analytics"})
    assert res_b.status_code == 200
    id_b = res_b.json()["id"]
    assert id_a != id_b

    # 3. Post Message in Session A
    res_chat_a = client.post("/api/chat", json={
        "session_id": id_a,
        "message": "Explain Shreyas Doshi's LNO framework"
    })
    assert res_chat_a.status_code == 200
    assert res_chat_a.json()["session_id"] == id_a

    # 4. Post Message in Session B
    res_chat_b = client.post("/api/chat", json={
        "session_id": id_b,
        "message": "How does Elena Verna define Product Qualified Leads?"
    })
    assert res_chat_b.status_code == 200
    assert res_chat_b.json()["session_id"] == id_b

    # 5. Verify Isolation: Session A has its own messages, Session B has its own messages
    msgs_a = client.get(f"/api/sessions/{id_a}/messages").json()
    msgs_b = client.get(f"/api/sessions/{id_b}/messages").json()

    assert any("LNO" in m["content"] for m in msgs_a)
    assert not any("Elena Verna" in m["content"] for m in msgs_a)

    assert any("Elena Verna" in m["content"] for m in msgs_b)
    assert not any("LNO framework" in m["content"] for m in msgs_b)

    # Clean up
    client.delete(f"/api/sessions/{id_a}")
    client.delete(f"/api/sessions/{id_b}")

def test_grounded_answer_and_citations():
    """Requirement: Answers PM questions with transcript grounding and citations."""
    res = client.post("/api/chat", json={
        "message": "What is Marty Cagan's perspective on product discovery risks?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_found"] is True
    assert len(data["citations"]) > 0
    assert "Marty Cagan" in data["citations"][0]["guest"] or "Cagan" in data["reply"]

def test_unsupported_question_returns_insufficient_evidence():
    """Requirement: Explicit insufficient evidence response when topic is not in transcripts."""
    res = client.post("/api/chat", json={
        "message": "What is the thermodynamic efficiency of superconducting qbits?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_found"] is False
    assert "Insufficient" in data["reply"]
    assert len(data["citations"]) == 0

def test_ship30_skill_endpoint_with_artifact():
    res = client.post("/api/skills/ship30", json={
        "topic": "Shreyas Doshi Pre-Mortem Framework",
        "target_audience": "Product Managers"
    })
    assert res.status_code == 200
    data = res.json()
    assert "Hook" in data["reply"] or "Shreyas" in data["reply"]
    assert data["artifact"] is not None
    art_id = data["artifact"]["id"]

    # Verify Artifact retrieval by ID
    res_art = client.get(f"/api/artifacts/{art_id}")
    assert res_art.status_code == 200
    assert res_art.json()["id"] == art_id

def test_ingest_diagnostics_endpoint():
    res = client.get("/api/ingest/diagnostics?query=Elena+Verna+PLG")
    assert res.status_code == 200
    data = res.json()
    assert "query" in data
    assert "top_candidates" in data
