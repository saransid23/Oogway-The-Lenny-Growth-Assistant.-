from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, SessionModel, MessageModel, ArtifactModel
from app.models import SkillShip30Request, ChatResponse, ArtifactResponse
from app.skills.ship30 import ship30_skill
from app.skills.artifact_generator import artifact_generator
import json

router = APIRouter(prefix="/api/skills", tags=["Skills"])

@router.post("/ship30", response_model=ChatResponse)
async def trigger_ship30_skill(request: SkillShip30Request, db: Session = Depends(get_db)):
    # 1. Obtain session
    session_id = request.session_id
    if not session_id:
        s_obj = SessionModel(title=f"Ship 30 Essay: {request.topic[:30]}")
        db.add(s_obj)
        db.commit()
        db.refresh(s_obj)
        session_id = s_obj.id

    # 2. Add user prompt message
    user_msg = MessageModel(
        session_id=session_id,
        sender="user",
        content=f"Generate a Ship 30 for 30 essay on: {request.topic}"
    )
    db.add(user_msg)

    # 3. Generate essay
    essay_text, citations = await ship30_skill.generate_essay(
        topic=request.topic,
        target_audience=request.target_audience or "Product Managers & Growth Leaders"
    )

    # 4. Create artifact
    artifact_dict = artifact_generator.extract_or_create_artifact(
        session_id=session_id,
        content=essay_text,
        title_hint=f"Ship 30 Essay: {request.topic[:25]}"
    )

    artifact_obj = None
    artifact_id = None
    if artifact_dict:
        art_db = ArtifactModel(
            id=artifact_dict["id"],
            session_id=session_id,
            title=artifact_dict["title"],
            artifact_type=artifact_dict["artifact_type"],
            content=artifact_dict["content"]
        )
        db.add(art_db)
        db.commit()
        db.refresh(art_db)
        artifact_id = art_db.id
        artifact_obj = ArtifactResponse(
            id=art_db.id,
            session_id=art_db.session_id,
            title=art_db.title,
            artifact_type=art_db.artifact_type,
            content=art_db.content,
            created_at=art_db.created_at
        )

    # 5. Add assistant response
    citations_json = json.dumps([c.model_dump() for c in citations]) if citations else None
    asst_msg = MessageModel(
        session_id=session_id,
        sender="assistant",
        content=essay_text,
        citations_json=citations_json,
        artifact_id=artifact_id
    )
    db.add(asst_msg)
    db.commit()

    return ChatResponse(
        session_id=session_id,
        message_id=asst_msg.id,
        reply=essay_text,
        provider=request.provider or "local",
        model_name="ship30-skill",
        citations=citations,
        artifact=artifact_obj
    )
