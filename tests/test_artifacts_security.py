import pytest
from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app
from app.skills.artifact_generator import artifact_generator, MAX_ARTIFACT_SIZE_BYTES

client = TestClient(app)

def test_dynamic_artifact_extraction_html():
    """Artifact extraction correctly parses ```html blocks without returning static PLG dashboard."""
    sample_response = """Here is your custom revenue model calculator:
```html
<div class="calculator">
  <h2>SaaS LTV Calculator</h2>
  <span class="metric">$12,000</span>
</div>
```
Hope this helps!"""
    artifact = artifact_generator.extract_or_create_artifact("sess-1", sample_response, "SaaS Calculator")
    assert artifact is not None
    assert artifact["artifact_type"] == "html"
    assert "SaaS LTV Calculator" in artifact["content"]
    assert "PLG Activation & PQL Tracker" not in artifact["content"]

def test_csp_header_injected_into_html_artifacts():
    """Security requirement: HTML artifacts must include restrictive Content-Security-Policy."""
    raw_html = "<html><body><h1>Hello World</h1></body></html>"
    artifact = artifact_generator.create_dynamic_html_artifact("sess-1", "Test", raw_html)
    assert artifact is not None
    assert "Content-Security-Policy" in artifact["content"]
    assert "default-src 'none'" in artifact["content"]

def test_artifact_size_limit_enforced():
    """Security requirement: oversized artifacts are bounded to prevent memory exhaustion."""
    oversized_html = "<div>" + ("A" * (MAX_ARTIFACT_SIZE_BYTES + 5000)) + "</div>"
    artifact = artifact_generator.extract_or_create_artifact("sess-1", f"```html\n{oversized_html}\n```", "Oversized")
    assert artifact is not None
    assert len(artifact["content"].encode("utf-8")) <= MAX_ARTIFACT_SIZE_BYTES + 1000

def test_upload_path_traversal_prevention():
    """Security requirement: file upload prevents path traversal like ../../bad.json."""
    malicious_filename = "../../evil_transcript.json"
    valid_content = b'[{"title": "Test Episode", "guest": "Test Guest", "content": [{"text": "Hello"}]}]'

    response = client.post(
        "/api/ingest/upload",
        files={"file": (malicious_filename, BytesIO(valid_content), "application/json")}
    )
    assert response.status_code == 200
    data = response.json()
    # The filename must be sanitized to basename only
    assert ".." not in data["filename"]
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]

def test_upload_rejects_invalid_file_type():
    """Security requirement: only .json files are accepted."""
    response = client.post(
        "/api/ingest/upload",
        files={"file": ("malicious.exe", BytesIO(b"binarycontent"), "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Only JSON" in response.json()["detail"]

def test_upload_rejects_malformed_json():
    """Security requirement: malformed JSON returns 400 without crashing."""
    response = client.post(
        "/api/ingest/upload",
        files={"file": ("bad.json", BytesIO(b"{invalid json syntax: missing quotes"), "application/json")}
    )
    assert response.status_code == 400
    assert "Malformed JSON" in response.json()["detail"]
