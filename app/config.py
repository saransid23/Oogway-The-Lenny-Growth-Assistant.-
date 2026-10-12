import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "The Lenny Growth Assistant"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "local")  # 'local' or 'cloud'
    
    # Ollama Local Settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # Cloud LLM Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./lenny_assistant.db")

    # Transcripts
    TRANSCRIPTS_DIR: str = os.getenv("TRANSCRIPTS_DIR", "data/transcripts")

    # Performance & Local LLM Tuning
    OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "400"))
    EMBED_TIMEOUT_SECONDS: float = float(os.getenv("EMBED_TIMEOUT_SECONDS", "2.0"))
    EMBED_BACKOFF_SECONDS: float = float(os.getenv("EMBED_BACKOFF_SECONDS", "30.0"))
    EMBED_CACHE_SIZE: int = int(os.getenv("EMBED_CACHE_SIZE", "256"))

    # Chat Context Limits
    HISTORY_MAX_MESSAGES: int = int(os.getenv("HISTORY_MAX_MESSAGES", "6"))
    HISTORY_MSG_MAX_CHARS: int = int(os.getenv("HISTORY_MSG_MAX_CHARS", "600"))

    # Database Connection Pool Tuning
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))

    # Security & CORS
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
