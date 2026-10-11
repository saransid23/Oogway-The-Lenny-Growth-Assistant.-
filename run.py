import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting The Lenny Growth Assistant Application Server")
    print(f"🌐 Server URL: http://localhost:{settings.PORT}")
    print(f"🤖 Default LLM Provider: {settings.DEFAULT_LLM_PROVIDER}")
    print("=" * 60)
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
