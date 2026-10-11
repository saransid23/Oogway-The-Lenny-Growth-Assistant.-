import os
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import settings

# Setup engine with appropriate parameters for SQLite/PostgreSQL
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc)

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), default="New Growth Conversation")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    provider = Column(String(50), default="local")
    model_name = Column(String(100), default="mistral")

    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")
    artifacts = relationship("ArtifactModel", back_populates="session", cascade="all, delete-orphan")

class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    sender = Column(String(20), nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=True) # JSON list of citations
    artifact_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("SessionModel", back_populates="messages")

class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    title = Column(String(255), nullable=False)
    artifact_type = Column(String(50), nullable=False) # 'html' or 'markdown'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("SessionModel", back_populates="artifacts")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
