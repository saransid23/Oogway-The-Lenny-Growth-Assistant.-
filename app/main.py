import os
import time
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import settings
from app.database import init_db
from app.routers import health, sessions, chat, skills, artifacts, ingest

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [req_id=%(name)s]: %(message)s"
)
logger = logging.getLogger("lenny_assistant.main")

app = FastAPI(
    title=settings.APP_NAME,
    description="Full-stack AI assistant for Lenny's Podcast growth & product management transcripts",
    version="1.0.0"
)

# Enable GZip Compression for payloads >= 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# Enable CORS
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")] if settings.ALLOWED_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Observability Middleware: Request-ID Tracking and Latency Logging
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    start_time = time.time()

    # Attach request ID to request state
    request.state.request_id = req_id

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        
        # Don't flood logs for static asset checks
        if not request.url.path.startswith("/static"):
            logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms) [req:{req_id}]")
            
        return response
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Unhandled server error on {request.method} {request.url.path} ({duration_ms}ms) [req:{req_id}]: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "An internal server error occurred while processing your request.",
                "request_id": req_id
            },
            headers={"X-Request-ID": req_id}
        )

# Static Asset Cache-Control Middleware
@app.middleware("http")
async def static_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        if settings.APP_ENV == "development":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"
    return response

# Initialize Database Schema
init_db()

# Include Routers
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(skills.router)
app.include_router(artifacts.router)
app.include_router(ingest.router)

# Serve Frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Lenny Growth Assistant API Server is running. Frontend static directory not found."}
