import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional

from config.settings import settings
from api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatData,
    ResponseMeta,
    HealthResponse,
    ScrapeRequest,
    ScrapeResponse,
    IngestRequest,
    IngestResponse,
)
from rag.chatbot import SurfacesChatbot
from rag.vector_store import SurfacesVectorStore
from rag.retriever import SurfacesRetriever
from rag.embeddings import GeminiEmbeddingService
from rag.chunker import ContentChunker
from scraper.scraper import SurfacesScraper

logger = logging.getLogger(__name__)

router = APIRouter()

# Global singletons
_vector_store: Optional[SurfacesVectorStore] = None
_embedding_service: Optional[GeminiEmbeddingService] = None
_chatbot: Optional[SurfacesChatbot] = None


def get_vector_store() -> SurfacesVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = SurfacesVectorStore()
    return _vector_store


def get_embedding_service() -> GeminiEmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = GeminiEmbeddingService()
    return _embedding_service


def get_chatbot(
    vstore: SurfacesVectorStore = Depends(get_vector_store),
    embs: GeminiEmbeddingService = Depends(get_embedding_service)
) -> SurfacesChatbot:
    global _chatbot
    if _chatbot is None:
        retriever = SurfacesRetriever(vector_store=vstore, embedding_service=embs)
        _chatbot = SurfacesChatbot(retriever=retriever)
    return _chatbot


@router.get("/health", response_model=HealthResponse, summary="API and Knowledge Base Health Check")
def health_check(vstore: SurfacesVectorStore = Depends(get_vector_store)):
    """Check status of API, vector store document count, and Gemini API readiness."""
    has_key = bool(settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here")
    count = vstore.count()
    return HealthResponse(
        status="healthy",
        document_count=count,
        gemini_configured=has_key,
        embedding_model=settings.gemini_embedding_model,
        llm_model=settings.gemini_model,
        version="1.0.0"
    )


@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True, summary="Ask the Surfaces Tiles UK Chatbot")
def chat_endpoint(
    request: ChatRequest,
    chatbot: SurfacesChatbot = Depends(get_chatbot)
):
    """Customer-facing RAG endpoint for questions about tiles, specs, delivery, pricing, and policies."""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="The 'message' field cannot be empty.")

    try:
        result = chatbot.answer_question(
            message=request.message
        )

        response_text = result.get("answer", "")

        return ChatResponse(
            meta=ResponseMeta(
                status=1,
                message="Successfully processed user measurements and preferences"
            ),
            data=ChatData(
                Response=response_text
            ),
            statusCode=200
        )
    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal chat error: {str(e)}")


def _run_scrape_job():
    try:
        scraper = SurfacesScraper()
        scraper.run()
    except Exception as e:
        logger.error(f"Background scrape failed: {e}", exc_info=True)


@router.post("/scrape", response_model=ScrapeResponse, summary="Trigger Website Scrape")
def scrape_endpoint(
    request: ScrapeRequest = ScrapeRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Scrape product catalog, policies, FAQs, and blogs from surfacestiles.co.uk."""
    if request.run_in_background:
        background_tasks.add_task(_run_scrape_job)
        return ScrapeResponse(
            status="accepted",
            message="Scraping started in the background."
        )

    try:
        scraper = SurfacesScraper()
        result = scraper.run()
        return ScrapeResponse(
            status="success",
            message="Website scrape completed successfully.",
            counts=result.get("counts")
        )
    except Exception as e:
        logger.error(f"Scrape failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scrape error: {str(e)}")


def _run_ingest_job(force_reset: bool = True):
    try:
        chunker = ContentChunker()
        chunks = chunker.process_all()
        if not chunks:
            logger.warning("No chunks to ingest.")
            return

        texts = [c["text"] for c in chunks]
        emb_svc = get_embedding_service()
        embeddings = emb_svc.embed_batch(texts)

        vstore = get_vector_store()
        if force_reset:
            vstore.reset()
        vstore.add_documents(chunks=chunks, embeddings=embeddings)
        logger.info(f"Ingested {len(chunks)} chunks into vector store.")
    except Exception as e:
        logger.error(f"Background ingestion failed: {e}", exc_info=True)


@router.post("/ingest", response_model=IngestResponse, summary="Chunk Data, Generate Embeddings, and Populate Vector Store")
def ingest_endpoint(
    request: IngestRequest = IngestRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    vstore: SurfacesVectorStore = Depends(get_vector_store),
    emb_svc: GeminiEmbeddingService = Depends(get_embedding_service)
):
    """Process scraped data into chunks, compute gemini-embedding-001 vectors, and index in ChromaDB."""
    if request.run_in_background:
        background_tasks.add_task(_run_ingest_job, request.force_reset)
        return IngestResponse(
            status="accepted",
            message="Ingestion process launched in background.",
            chunks_indexed=0
        )

    try:
        chunker = ContentChunker()
        chunks = chunker.process_all()
        if not chunks:
            return IngestResponse(
                status="warning",
                message="No chunks were generated. Please run /scrape first.",
                chunks_indexed=0
            )

        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        texts = [c["text"] for c in chunks]
        embeddings = emb_svc.embed_batch(texts)

        if request.force_reset:
            vstore.reset()

        vstore.add_documents(chunks=chunks, embeddings=embeddings)
        total_indexed = vstore.count()

        return IngestResponse(
            status="success",
            message=f"Successfully indexed {len(chunks)} chunks into ChromaDB.",
            chunks_indexed=total_indexed
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")
