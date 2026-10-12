from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class Citation(BaseModel):
    transcript_id: str
    guest: str
    title: str
    timestamp: str
    topic: str
    quote: str
    source_url: Optional[str] = None
    score: float = 0.0

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    provider: Optional[str] = None # 'local' or 'cloud'
    model_name: Optional[str] = None
    use_skill: Optional[str] = None # e.g. 'ship30'

class ArtifactResponse(BaseModel):
    id: str
    session_id: str
    title: str
    artifact_type: str # 'html' or 'markdown'
    content: str
    created_at: datetime

class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    reply: str
    provider: str
    model_name: str
    citations: List[Citation] = []
    artifact: Optional[ArtifactResponse] = None
    evidence_found: bool = True

class SessionCreate(BaseModel):
    title: Optional[str] = "New Growth Conversation"
    provider: Optional[str] = "local"
    model_name: Optional[str] = "mistral"

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    provider: str
    model_name: str
    message_count: int = 0

class MessageResponse(BaseModel):
    id: str
    session_id: str
    sender: str
    content: str
    citations: List[Citation] = []
    artifact_id: Optional[str] = None
    artifact: Optional[ArtifactResponse] = None
    created_at: datetime

class SkillShip30Request(BaseModel):
    session_id: Optional[str] = None
    topic: str
    target_audience: Optional[str] = "Product Managers & Growth Leaders"
    provider: Optional[str] = None
    model_name: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    active_provider: str
    database_status: str = "connected"
    ollama_status: str
    cloud_status: str
    transcripts_loaded: int
