import logging
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from app.models import HealthResponse
from app.config import settings
from app.database import SessionLocal
from app.llm.ollama_client import ollama_client
from app.llm.cloud_client import cloud_client
from app.rag.knowledge_base import knowledge_base

logger = logging.getLogger("lenny_assistant.health")
router = APIRouter(prefix="/api", tags=["Health & Observability"])

@router.get("/health", response_model=HealthResponse)
async def get_health(response: Response):
    # 1. Probe database
    db_ok = False
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Health probe database error: {e}")
        db_ok = False

    # 2. Probe LLM providers
    ollama_ok = await ollama_client.check_health()
    cloud_ok = await cloud_client.check_health()

    is_overall_healthy = db_ok and (len(knowledge_base.chunks) > 0)
    if not is_overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if is_overall_healthy else "degraded",
        version="1.0.0",
        active_provider=settings.DEFAULT_LLM_PROVIDER,
        database_status="connected" if db_ok else "disconnected",
        ollama_status="online" if ollama_ok else "offline",
        cloud_status="configured" if cloud_ok else "not_configured",
        transcripts_loaded=len(knowledge_base.chunks)
    )

@router.get("/health/live")
def get_liveness():
    """Kubernetes / Docker liveness probe: returns 200 if process is responsive."""
    return {"status": "alive", "service": "lenny-growth-assistant"}

@router.get("/health/ready")
def get_readiness(response: Response):
    """Readiness probe: validates critical dependencies (database and knowledge base)."""
    db_ok = False
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception:
        db_ok = False

    kb_ready = len(knowledge_base.chunks) > 0

    if not (db_ok and kb_ready):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "ready": False,
            "database_ready": db_ok,
            "knowledge_base_ready": kb_ready,
            "detail": "Service not ready to serve traffic"
        }

    return {
        "ready": True,
        "database_ready": True,
        "knowledge_base_ready": True,
        "total_chunks": len(knowledge_base.chunks)
    }

@router.get("/models")
async def get_models():
    ollama_online = await ollama_client.check_health()
    cloud_ready = await cloud_client.check_health()

    return {
        "providers": [
            {
                "id": "local",
                "name": "Local LLM (Ollama)",
                "models": ["mistral", "llama3", "phi3"],
                "default_model": settings.OLLAMA_MODEL,
                "is_available": ollama_online
            },
            {
                "id": "cloud",
                "name": "Cloud LLM (OpenAI / Anthropic)",
                "models": [settings.OPENAI_MODEL, settings.ANTHROPIC_MODEL],
                "default_model": settings.OPENAI_MODEL,
                "is_available": cloud_ready
            }
        ]
    }
