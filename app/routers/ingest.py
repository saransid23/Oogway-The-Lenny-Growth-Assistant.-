import os
import re
import json
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.config import settings
from app.rag.knowledge_base import knowledge_base
from app.rag.retriever import retriever

logger = logging.getLogger("lenny_assistant.ingest")
router = APIRouter(prefix="/api/ingest", tags=["Ingestion & Knowledge Base"])

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MAX_EPISODES_PER_FILE = 500

class IngestStatusResponse(BaseModel):
    status: str
    total_chunks: int
    data_directory: str
    loaded_files: List[str]

@router.get("", response_model=IngestStatusResponse)
def get_ingestion_status():
    files = []
    if os.path.exists(settings.TRANSCRIPTS_DIR):
        files = [f for f in sorted(os.listdir(settings.TRANSCRIPTS_DIR)) if f.endswith(".json") and not f.startswith(".")]

    return IngestStatusResponse(
        status="active",
        total_chunks=len(knowledge_base.chunks),
        data_directory=settings.TRANSCRIPTS_DIR,
        loaded_files=files
    )

@router.post("/upload")
async def upload_transcript(file: UploadFile = File(...)):
    # 1. Allowlisted file type
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only JSON transcript files (.json) are permitted.")

    # 2. Filename normalization & path traversal prevention
    raw_filename = os.path.basename(file.filename)
    clean_filename = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw_filename)
    if not clean_filename or clean_filename.startswith("."):
        clean_filename = "transcript_upload.json"

    # 3. Read content with size limit enforcement
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB.")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 4. JSON parsing and schema validation
    try:
        parsed = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Malformed JSON: {str(e)}")

    episodes = parsed if isinstance(parsed, list) else [parsed]
    if len(episodes) > MAX_EPISODES_PER_FILE:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum of {MAX_EPISODES_PER_FILE} episodes.")

    for idx, ep in enumerate(episodes):
        if not isinstance(ep, dict):
            raise HTTPException(status_code=400, detail=f"Episode at index {idx} must be a JSON object.")
        if "title" not in ep and "guest" not in ep and "content" not in ep:
            raise HTTPException(
                status_code=400,
                detail=f"Episode at index {idx} missing required fields (must have at least 'title', 'guest', or 'content')."
            )

    # 5. Safe atomic file write
    os.makedirs(settings.TRANSCRIPTS_DIR, exist_ok=True)
    target_path = os.path.join(settings.TRANSCRIPTS_DIR, clean_filename)

    try:
        with open(target_path, "wb") as f:
            f.write(content)

        # 6. Incremental ingestion and reporting
        stats = knowledge_base.load_transcripts()
        logger.info(f"Ingested '{clean_filename}': {stats['chunks_created']} chunks created, {stats['duplicates_skipped']} duplicates skipped.")

        return {
            "status": "success",
            "filename": clean_filename,
            "documents_processed": stats["documents_processed"],
            "chunks_created": stats["chunks_created"],
            "duplicates_skipped": stats["duplicates_skipped"],
            "total_indexed_chunks": len(knowledge_base.chunks)
        }
    except Exception as e:
        logger.error(f"Failed to ingest file '{clean_filename}': {e}")
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Ingestion processing error: {str(e)}")

@router.post("/refresh")
def refresh_knowledge_base():
    """Forces an invalidation of embeddings cache and full re-indexing of transcript files."""
    knowledge_base.invalidate_cache()
    return {
        "status": "success",
        "message": "Knowledge base re-indexed from disk with cache refresh.",
        "total_chunks": len(knowledge_base.chunks)
    }

@router.get("/diagnostics")
def get_retrieval_diagnostics(query: str = Query(..., description="Query string to evaluate")):
    """Retrieval diagnostics endpoint for debugging search relevance scores and candidate rankings."""
    return retriever.diagnose_query(query)
