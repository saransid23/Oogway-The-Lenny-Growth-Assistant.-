import os
import json
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Dict, Any
from app.config import settings
from app.rag.knowledge_base import knowledge_base

logger = logging.getLogger("lenny_assistant.ingest")
router = APIRouter(prefix="/api/ingest", tags=["Ingestion & Knowledge Base"])

class IngestStatusResponse(BaseModel):
    status: str
    total_chunks: int
    data_directory: str
    loaded_files: List[str]

@router.get("", response_model=IngestStatusResponse)
def get_ingestion_status():
    files = []
    if os.path.exists(settings.TRANSCRIPTS_DIR):
        files = [f for f in os.listdir(settings.TRANSCRIPTS_DIR) if f.endswith(".json")]

    return IngestStatusResponse(
        status="active",
        total_chunks=len(knowledge_base.chunks),
        data_directory=settings.TRANSCRIPTS_DIR,
        loaded_files=files
    )

@router.post("/upload")
async def upload_transcript(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON transcript files are supported.")

    target_path = os.path.join(settings.TRANSCRIPTS_DIR, file.filename)
    try:
        content = await file.read()
        parsed = json.loads(content.decode("utf-8"))
        
        with open(target_path, "wb") as f:
            f.write(content)

        # Reload knowledge base index
        knowledge_base.load_transcripts()
        logger.info(f"Successfully ingested {file.filename}. New total chunks: {len(knowledge_base.chunks)}")

        return {
            "status": "success",
            "message": f"Transcript file '{file.filename}' successfully ingested and indexed.",
            "total_chunks": len(knowledge_base.chunks)
        }
    except Exception as e:
        logger.error(f"Error ingesting transcript file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@router.post("/refresh")
def refresh_knowledge_base():
    knowledge_base.load_transcripts()
    return {
        "status": "success",
        "message": "Knowledge base re-indexed from disk.",
        "total_chunks": len(knowledge_base.chunks)
    }
