import os
import json
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Integer, Index, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import settings

logger = logging.getLogger("lenny_assistant.database")

# Normalize PostgreSQL URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs["connect_args"] = connect_args
else:
    logger.info("Configured PostgreSQL persistence engine")
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_recycle"] = 1800

def _configure_sqlite_engine(eng):
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception as e:
            logger.debug(f"SQLite PRAGMA setup ignored: {e}")

try:
    engine = create_engine(db_url, **engine_kwargs)
    if db_url.startswith("sqlite"):
        _configure_sqlite_engine(engine)
except Exception as e:
    logger.warning(f"Could not connect to {db_url}: {e}. Falling back to local SQLite.")
    db_url = "sqlite:///./lenny_assistant.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _configure_sqlite_engine(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc)

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), default="New Growth Conversation")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    provider = Column(String(50), default="local")
    model_name = Column(String(100), default="mistral")

    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")
    artifacts = relationship("ArtifactModel", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_updated_at", "updated_at"),
    )

class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    sender = Column(String(20), nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=True) # JSON list of citations
    artifact_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("SessionModel", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_session_id_created_at", "session_id", "created_at"),
    )

class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    artifact_type = Column(String(50), nullable=False) # 'html' or 'markdown'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("SessionModel", back_populates="artifacts")

    __table_args__ = (
        Index("idx_artifacts_session_id", "session_id"),
    )

def ensure_indexes(target_engine):
    """Ensures performance indexes exist on existing tables for PostgreSQL and SQLite."""
    try:
        with target_engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_session_id_created_at ON messages(session_id, created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artifacts_session_id ON artifacts(session_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at)"))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_indexes notice: {e}")

def init_db():
    global engine, SessionLocal
    try:
        # Test connecting with the configured engine
        with engine.connect() as conn:
            pass
        Base.metadata.create_all(bind=engine)
        ensure_indexes(engine)
        logger.info(f"Database initialized successfully with {engine.url.drivername}")
    except Exception as e:
        logger.warning(
            f"Configured database ({engine.url}) unreachable: {e}. "
            "Falling back to local SQLite (lenny_assistant.db)."
        )
        sqlite_url = "sqlite:///./lenny_assistant.db"
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        _configure_sqlite_engine(engine)
        SessionLocal.configure(bind=engine)
        Base.metadata.create_all(bind=engine)
        ensure_indexes(engine)
        logger.info("Local SQLite database initialized successfully as fallback.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
