import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["transcripts_loaded"] > 0

def test_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data

def test_session_lifecycle():
    # 1. Create Session
    res_create = client.post("/api/sessions", json={"title": "Test Growth Chat"})
    assert res_create.status_code == 200
    session_data = res_create.json()
    session_id = session_data["id"]
    assert session_data["title"] == "Test Growth Chat"

    # 2. List Sessions
    res_list = client.get("/api/sessions")
    assert res_list.status_code == 200
    sessions = res_list.json()
    assert any(s["id"] == session_id for s in sessions)

    # 3. Chat in Session
    res_chat = client.post("/api/chat", json={
        "session_id": session_id,
        "message": "What is Marty Cagan's view on feature factories?"
    })
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert chat_data["session_id"] == session_id
    assert len(chat_data["reply"]) > 0

    # 4. Get Messages
    res_msgs = client.get(f"/api/sessions/{session_id}/messages")
    assert res_msgs.status_code == 200
    msgs = res_msgs.json()
    assert len(msgs) >= 2 # user + assistant

    # 5. Delete Session
    res_del = client.delete(f"/api/sessions/{session_id}")
    assert res_del.status_code == 200

def test_ship30_skill_endpoint():
    res = client.post("/api/skills/ship30", json={
        "topic": "Product-Led Growth",
        "target_audience": "Growth PMs"
    })
    assert res.status_code == 200
    data = res.json()
    assert "Ship 30 for 30" in data["reply"] or "Hook" in data["reply"]
    assert data["artifact"] is not None

def test_ingest_status_endpoint():
    res = client.get("/api/ingest")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "active"
    assert data["total_chunks"] > 0

