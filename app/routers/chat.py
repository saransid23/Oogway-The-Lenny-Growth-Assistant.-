import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, SessionModel, MessageModel, ArtifactModel
from app.models import ChatRequest, ChatResponse, ArtifactResponse
from app.llm.agent_router import agent_router
from app.llm.provider import llm_provider
from app.skills.artifact_generator import artifact_generator
from app.skills.ship30 import ship30_skill

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("", response_model=ChatResponse)
async def handle_chat(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. Obtain or create session
    session_id = request.session_id
    if not session_id:
        session_obj = SessionModel(
            title=request.message[:40] + "..." if len(request.message) > 40 else request.message,
            provider=request.provider or "local",
            model_name=request.model_name or "mistral"
        )
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
        session_id = session_obj.id
    else:
        session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session_obj:
            session_obj = SessionModel(
                id=session_id,
                title=request.message[:40] + "..." if len(request.message) > 40 else request.message,
                provider=request.provider or "local",
                model_name=request.model_name or "mistral"
            )
            db.add(session_obj)
            db.commit()

    # 2. Store User Message
    user_msg = MessageModel(
        session_id=session_id,
        sender="user",
        content=request.message
    )
    db.add(user_msg)
    db.commit()

    # 3. Retrieve history context
    past_messages = db.query(MessageModel).filter(MessageModel.session_id == session_id).order_by(MessageModel.created_at.asc()).all()
    history = [{"role": m.sender, "content": m.content} for m in past_messages[:-1]]

    # 4. Route and execute through the Agent Router Layer (Anthropic Agent SDK, Ship 30, or Grounded RAG)
    execution_result = await agent_router.route_and_execute(
        session_id=session_id,
        user_message=request.message,
        chat_history=history,
        requested_provider=request.provider,
        requested_skill=request.use_skill,
        model_name=request.model_name
    )

    reply_text = execution_result["reply"]
    provider_used = execution_result["provider"]
    model_used = execution_result["model_name"]
    citations = execution_result["citations"]
    artifact_dict = execution_result["artifact_dict"]


    artifact_obj = None
    artifact_id = None
    if artifact_dict:
        artifact_db = ArtifactModel(
            id=artifact_dict["id"],
            session_id=session_id,
            title=artifact_dict["title"],
            artifact_type=artifact_dict["artifact_type"],
            content=artifact_dict["content"]
        )
        db.add(artifact_db)
        db.commit()
        db.refresh(artifact_db)
        artifact_id = artifact_db.id
        artifact_obj = ArtifactResponse(
            id=artifact_db.id,
            session_id=artifact_db.session_id,
            title=artifact_db.title,
            artifact_type=artifact_db.artifact_type,
            content=artifact_db.content,
            created_at=artifact_db.created_at
        )

    # 6. Save Assistant Response Message
    citations_json = json.dumps([c.model_dump() for c in citations]) if citations else None
    assistant_msg = MessageModel(
        session_id=session_id,
        sender="assistant",
        content=reply_text,
        citations_json=citations_json,
        artifact_id=artifact_id
    )
    db.add(assistant_msg)
    
    # Update session provider and model metadata
    session_obj.provider = provider_used
    session_obj.model_name = model_used
    db.commit()
    db.refresh(assistant_msg)

    return ChatResponse(
        session_id=session_id,
        message_id=assistant_msg.id,
        reply=reply_text,
        provider=provider_used,
        model_name=model_used,
        citations=citations,
        artifact=artifact_obj,
        evidence_found=execution_result.get("evidence_found", True)
    )
