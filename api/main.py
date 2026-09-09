import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from api.routes import router

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.get("/", summary="Root Endpoint")
def root():
    return JSONResponse({
        "message": "Welcome to Surfaces Tiles UK AI Chatbot API",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "scrape": "POST /scrape",
            "ingest": "POST /ingest"
        }
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
