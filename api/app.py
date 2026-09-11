import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from api.routes import router
from api.interaction_logger import cleanup_old_logs

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("surfaces_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Surfaces Tiles UK Chatbot API...")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Gemini Embedding Model: {settings.gemini_embedding_model}")
    logger.info(f"Vector Store Directory: {settings.chroma_persist_dir}")
    logger.info(f"Logs Directory: {settings.logs_dir}")

    # Perform initial cleanup of expired log files (> 2 days)
    try:
        deleted = cleanup_old_logs()
        if deleted:
            logger.info(f"Startup log cleanup removed {len(deleted)} expired log files.")
    except Exception as e:
        logger.warning(f"Error during startup log cleanup: {e}")

    # Pre-warm Voice STT model in background executor to eliminate first-request cold-start latency
    try:
        import asyncio
        from voice import get_stt_service
        stt = get_stt_service()
        if hasattr(stt, "warm_up"):
            asyncio.get_event_loop().run_in_executor(None, stt.warm_up)
    except Exception as e:
        logger.warning(f"Voice service warm-up skipped: {e}")

    yield
    logger.info("Shutting down Surfaces Tiles UK Chatbot API...")


app = FastAPI(
    title="Surfaces Tiles UK AI Chatbot API",
    description=(
        "Retrieval-Augmented Generation (RAG) REST API for Surfaces Tiles UK (https://surfacestiles.co.uk). "
        "Built with Google Gemini API, gemini-embedding-001, and ChromaDB."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
from fastapi.responses import JSONResponse, FileResponse

# Include routes
app.include_router(router)


@app.get("/demo", summary="Interactive Demo Page", include_in_schema=True)
def get_demo():
    demo_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if demo_path.exists():
        return FileResponse(str(demo_path), media_type="text/html")
    return JSONResponse({"error": "frontend/index.html not found"}, status_code=404)


@app.get("/", summary="Root Endpoint")
def root():
    return JSONResponse({
        "message": "Welcome to Surfaces Tiles UK AI Chatbot API",
        "documentation": "/docs",
        "demo": "/demo",
        "health": "/health",
        "endpoints": {
            "chat": "POST /chat",
            "chat_stream": "POST /chat/stream",
            "voice_chat": "POST /voice/chat",
            "voice_chat_stream": "POST /voice/chat/stream",
            "voice_transcribe": "POST /voice/transcribe",
            "voice_synthesize": "POST /voice/synthesize",
            "products": "GET /products",
            "health": "GET /health",
            "sessions": "GET /sessions",
            "jobs_status": "GET /jobs/status"
        }
    })
