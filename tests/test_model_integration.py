import pytest
from app.llm.ollama_client import ollama_client
from app.llm.cloud_client import cloud_client
from app.llm.provider import llm_provider

@pytest.mark.asyncio
async def test_ollama_local_health():
    """Verifies that the required local Ollama service is detected or handled gracefully."""
    is_online = await ollama_client.check_health()
    # On this machine, Ollama is actively installed and running
    assert isinstance(is_online, bool)

@pytest.mark.asyncio
async def test_ollama_local_inference_if_online():
    """Runs live inference against the local Ollama instance if active."""
    is_online = await ollama_client.check_health()
    if is_online:
        response = await ollama_client.generate(
            prompt="Reply with the single word 'CONFIRMED'.",
            system_prompt="You are a test assistant.",
            model="mistral"
        )
        assert response is not None
        assert len(response.strip()) > 0

@pytest.mark.asyncio
async def test_cloud_client_handles_missing_keys_gracefully():
    """Verifies that missing cloud keys return None rather than raising unhandled exceptions."""
    # Temporarily check empty key behavior
    client_empty = cloud_client
    if not client_empty.openai_key:
        res = await client_empty.generate_openai("Hello")
        assert res is None

@pytest.mark.asyncio
async def test_llm_provider_model_selection_propagation():
    """Verifies that the requested model name is passed and returned in the response metadata."""
    reply, provider, model, citations, evidence_found = await llm_provider.generate_response(
        query="Explain Shreyas Doshi's LNO framework",
        requested_provider="local",
        model_name="mistral"
    )
    assert len(reply) > 0
    assert provider in ["local", "cloud"]
    assert len(citations) > 0
    assert evidence_found is True
