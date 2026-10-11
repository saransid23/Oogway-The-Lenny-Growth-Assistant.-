from fastapi import APIRouter
from app.models import HealthResponse
from app.config import settings
from app.llm.ollama_client import ollama_client
from app.llm.cloud_client import cloud_client
from app.rag.knowledge_base import knowledge_base

router = APIRouter(prefix="/api", tags=["Health & Status"])

@router.get("/health", response_model=HealthResponse)
async def get_health():
    ollama_ok = await ollama_client.check_health()
    cloud_ok = await cloud_client.check_health()

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        active_provider=settings.DEFAULT_LLM_PROVIDER,
        ollama_status="online" if ollama_ok else "offline (fallback active)",
        cloud_status="configured" if cloud_ok else "not_configured",
        transcripts_loaded=len(knowledge_base.chunks)
    )

@router.get("/models")
async def get_models():
    return {
        "providers": [
            {
                "id": "local",
                "name": "Local LLM (Ollama)",
                "models": ["mistral", "llama3", "phi3"],
                "default_model": settings.OLLAMA_MODEL
            },
            {
                "id": "cloud",
                "name": "Cloud LLM (OpenAI / Anthropic)",
                "models": [settings.OPENAI_MODEL, settings.ANTHROPIC_MODEL],
                "default_model": settings.OPENAI_MODEL
            }
        ]
    }
