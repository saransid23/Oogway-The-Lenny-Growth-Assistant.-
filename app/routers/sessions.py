import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db, SessionModel, MessageModel
from app.models import SessionCreate, SessionResponse, MessageResponse, Citation

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

@router.get("", response_model=List[SessionResponse])
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(SessionModel).order_by(SessionModel.updated_at.desc()).all()
    result = []
    for s in sessions:
        msg_count = db.query(MessageModel).filter(MessageModel.session_id == s.id).count()
        result.append(
            SessionResponse(
                id=s.id,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
                provider=s.provider,
                model_name=s.model_name,
                message_count=msg_count
            )
        )
    return result

@router.post("", response_model=SessionResponse)
def create_session(session_in: SessionCreate, db: Session = Depends(get_db)):
    session_obj = SessionModel(
        title=session_in.title or "New Growth Conversation",
        provider=session_in.provider or "local",
        model_name=session_in.model_name or "mistral"
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return SessionResponse(
        id=session_obj.id,
        title=session_obj.title,
        created_at=session_obj.created_at,
        updated_at=session_obj.updated_at,
        provider=session_obj.provider,
        model_name=session_obj.model_name,
        message_count=0
    )

@router.get("/{session_id}/messages", response_model=List[MessageResponse])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(MessageModel).filter(MessageModel.session_id == session_id).order_by(MessageModel.created_at.asc()).all()
    
    res = []
    for m in messages:
        citations = []
        if m.citations_json:
            try:
                raw_c = json.loads(m.citations_json)
                citations = [Citation(**item) for item in raw_c]
            except Exception:
                pass
        res.append(
            MessageResponse(
                id=m.id,
                session_id=m.session_id,
                sender=m.sender,
                content=m.content,
                citations=citations,
                artifact_id=m.artifact_id,
                created_at=m.created_at
            )
        )
    return res

@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session_obj)
    db.commit()
    return {"status": "success", "message": "Session deleted"}
