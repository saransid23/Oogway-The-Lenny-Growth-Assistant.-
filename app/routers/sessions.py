import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db, SessionModel, MessageModel, ArtifactModel
from app.models import SessionCreate, SessionResponse, MessageResponse, Citation, ArtifactResponse

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

@router.get("", response_model=List[SessionResponse])
def list_sessions(db: Session = Depends(get_db)):
    # Single grouped COUNT query to eliminate N+1 queries
    counts = dict(
        db.query(MessageModel.session_id, func.count(MessageModel.id))
        .group_by(MessageModel.session_id)
        .all()
    )
    sessions = db.query(SessionModel).order_by(SessionModel.updated_at.desc()).all()
    result = [
        SessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            provider=s.provider,
            model_name=s.model_name,
            message_count=counts.get(s.id, 0)
        )
        for s in sessions
    ]
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
def get_session_messages(
    session_id: str,
    limit: Optional[int] = Query(None, description="Max messages to return"),
    offset: Optional[int] = Query(None, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    q = db.query(MessageModel).filter(MessageModel.session_id == session_id).order_by(MessageModel.created_at.asc())
    if offset is not None:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    messages = q.all()

    # Batch fetch artifacts in a single IN (...) query
    artifact_ids = {m.artifact_id for m in messages if m.artifact_id}
    artifacts_by_id = {}
    if artifact_ids:
        arts = db.query(ArtifactModel).filter(ArtifactModel.id.in_(artifact_ids)).all()
        artifacts_by_id = {a.id: a for a in arts}
    
    res = []
    for m in messages:
        citations = []
        if m.citations_json:
            try:
                raw_c = json.loads(m.citations_json)
                citations = [Citation(**item) for item in raw_c]
            except Exception:
                pass
        
        artifact_obj = None
        if m.artifact_id and m.artifact_id in artifacts_by_id:
            art_db = artifacts_by_id[m.artifact_id]
            artifact_obj = ArtifactResponse(
                id=art_db.id,
                session_id=art_db.session_id,
                title=art_db.title,
                artifact_type=art_db.artifact_type,
                content=art_db.content,
                created_at=art_db.created_at
            )

        res.append(
            MessageResponse(
                id=m.id,
                session_id=m.session_id,
                sender=m.sender,
                content=m.content,
                citations=citations,
                artifact_id=m.artifact_id,
                artifact=artifact_obj,
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
