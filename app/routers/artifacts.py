from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, ArtifactModel
from app.models import ArtifactResponse

router = APIRouter(prefix="/api/artifacts", tags=["Artifacts"])

@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(artifact_id: str, db: Session = Depends(get_db)):
    art = db.query(ArtifactModel).filter(ArtifactModel.id == artifact_id).first()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return ArtifactResponse(
        id=art.id,
        session_id=art.session_id,
        title=art.title,
        artifact_type=art.artifact_type,
        content=art.content,
        created_at=art.created_at
    )
