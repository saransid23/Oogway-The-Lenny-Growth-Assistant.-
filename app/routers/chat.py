import json
import uuid
import logging
from typing import Tuple, List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db, SessionLocal, SessionModel, MessageModel, ArtifactModel
from app.models import ChatRequest, ChatResponse, ArtifactResponse, Citation
from app.llm.agent_router import agent_router
from app.llm.provider import llm_provider
from app.skills.artifact_generator import artifact_generator

logger = logging.getLogger("lenny_assistant.chat")
router = APIRouter(prefix="/api/chat", tags=["Chat"])

def _begin_turn(
    db: Session, request: ChatRequest
) -> Tuple[str, SessionModel, MessageModel, List[Dict[str, str]]]:
    """
    Initializes or resolves the chat session and records the user message in ONE single commit.
    Loads bounded chat history excluding the current user message.
    """
    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        session_obj = SessionModel(
            id=session_id,
            title=request.message[:40] + "..." if len(request.message) > 40 else request.message,
            provider=request.provider or "local",
            model_name=request.model_name or "mistral"
        )
        db.add(session_obj)
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

    user_msg = MessageModel(
        session_id=session_id,
        sender="user",
        content=request.message
    )
    db.add(user_msg)
    # Commit #1: session + user message
    db.commit()

    # Query only the latest HISTORY_MAX_MESSAGES excluding the current user message
    past_messages = (
        db.query(MessageModel)
        .filter(MessageModel.session_id == session_id, MessageModel.id != user_msg.id)
        .order_by(MessageModel.created_at.desc())
        .limit(settings.HISTORY_MAX_MESSAGES)
        .all()
    )
    past_messages.reverse()
    history = [{"role": m.sender, "content": m.content} for m in past_messages]

    return session_id, session_obj, user_msg, history

def _finish_turn(
    db: Session,
    session_id: str,
    session_obj: SessionModel,
    reply_text: str,
    provider_used: str,
    model_used: str,
    citations: List[Any],
    artifact_dict: Optional[Dict[str, Any]],
    evidence_found: bool
) -> ChatResponse:
    """
    Persists assistant message, optional artifact, and updates session in ONE single commit.
    """
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
        db.flush()
        artifact_id = artifact_db.id
        artifact_obj = ArtifactResponse(
            id=artifact_db.id,
            session_id=artifact_db.session_id,
            title=artifact_db.title,
            artifact_type=artifact_db.artifact_type,
            content=artifact_db.content,
            created_at=artifact_db.created_at
        )

    citations_objs: List[Citation] = []
    citations_data: List[Dict[str, Any]] = []
    for c in citations:
        if isinstance(c, dict):
            citations_objs.append(Citation(**c))
            citations_data.append(c)
        else:
            citations_objs.append(c)
            citations_data.append(c.model_dump() if hasattr(c, "model_dump") else c.dict())

    citations_json = json.dumps(citations_data) if citations_data else None

    assistant_msg = MessageModel(
        session_id=session_id,
        sender="assistant",
        content=reply_text,
        citations_json=citations_json,
        artifact_id=artifact_id
    )
    db.add(assistant_msg)

    session_obj.provider = provider_used
    session_obj.model_name = model_used

    db.flush()

    response = ChatResponse(
        session_id=session_id,
        message_id=assistant_msg.id,
        reply=reply_text,
        provider=provider_used,
        model_name=model_used,
        citations=citations_objs,
        artifact=artifact_obj,
        evidence_found=evidence_found
    )

    # Commit #2: assistant message + artifact + session
    db.commit()

    return response

@router.post("", response_model=ChatResponse)
async def handle_chat(request: ChatRequest, db: Session = Depends(get_db)):
    session_id, session_obj, user_msg, history = _begin_turn(db, request)

    execution_result = await agent_router.route_and_execute(
        session_id=session_id,
        user_message=request.message,
        chat_history=history,
        requested_provider=request.provider,
        requested_skill=request.use_skill,
        model_name=request.model_name
    )

    return _finish_turn(
        db=db,
        session_id=session_id,
        session_obj=session_obj,
        reply_text=execution_result["reply"],
        provider_used=execution_result["provider"],
        model_used=execution_result["model_name"],
        citations=execution_result["citations"],
        artifact_dict=execution_result["artifact_dict"],
        evidence_found=execution_result.get("evidence_found", True)
    )

@router.post("/stream")
async def handle_chat_stream(request: ChatRequest):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint for grounded chat interactions.
    Streams tokens for local RAG route; other routes yield a single done event.
    """
    async def stream_generator():
        db = SessionLocal()
        try:
            session_id, session_obj, user_msg, history = _begin_turn(db, request)
            provider = (request.provider or "local").lower()
            route = agent_router.classify(request.message, request.use_skill, provider)

            if route == "rag" and provider == "local":
                accumulated_text = []
                citations = []
                provider_used = "local"
                model_used = request.model_name or settings.OLLAMA_MODEL
                evidence_found = True

                async for item in llm_provider.stream_response(
                    query=request.message,
                    chat_history=history,
                    requested_provider=provider,
                    model_name=request.model_name
                ):
                    event_name = item.get("event")
                    event_data = item.get("data", {})

                    if event_name == "meta":
                        citations = event_data.get("citations", [])
                        provider_used = event_data.get("provider", provider_used)
                        model_used = event_data.get("model", model_used)
                        evidence_found = event_data.get("evidence_found", True)
                        yield f"event: meta\ndata: {json.dumps(event_data)}\n\n"

                    elif event_name == "token":
                        token = event_data.get("token", "")
                        accumulated_text.append(token)
                        yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

                    elif event_name == "final":
                        final_reply = event_data.get("reply", "".join(accumulated_text))
                        citations = event_data.get("citations", citations)
                        provider_used = event_data.get("provider", provider_used)
                        model_used = event_data.get("model", model_used)
                        evidence_found = event_data.get("evidence_found", evidence_found)

                        artifact_dict = artifact_generator.extract_or_create_artifact(
                            session_id=session_id,
                            content=final_reply,
                            title_hint=request.message[:30]
                        )

                        chat_res = _finish_turn(
                            db=db,
                            session_id=session_id,
                            session_obj=session_obj,
                            reply_text=final_reply,
                            provider_used=provider_used,
                            model_used=model_used,
                            citations=citations,
                            artifact_dict=artifact_dict,
                            evidence_found=evidence_found
                        )
                        res_json = chat_res.model_dump() if hasattr(chat_res, "model_dump") else chat_res.dict()
                        yield f"event: done\ndata: {json.dumps(res_json, default=str)}\n\n"
            else:
                execution_result = await agent_router.route_and_execute(
                    session_id=session_id,
                    user_message=request.message,
                    chat_history=history,
                    requested_provider=request.provider,
                    requested_skill=request.use_skill,
                    model_name=request.model_name
                )

                chat_res = _finish_turn(
                    db=db,
                    session_id=session_id,
                    session_obj=session_obj,
                    reply_text=execution_result["reply"],
                    provider_used=execution_result["provider"],
                    model_used=execution_result["model_name"],
                    citations=execution_result["citations"],
                    artifact_dict=execution_result["artifact_dict"],
                    evidence_found=execution_result.get("evidence_found", True)
                )

                res_json = chat_res.model_dump() if hasattr(chat_res, "model_dump") else chat_res.dict()
                yield f"event: done\ndata: {json.dumps(res_json, default=str)}\n\n"

        except Exception as e:
            logger.error(f"Error in chat stream: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
        finally:
            db.close()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity"
        }
    )
