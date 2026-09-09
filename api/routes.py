import uuid
import logging
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional, Dict, Any, List

from config.settings import settings
from api.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatData,
    ResponseMeta,
    SourceItem,
    HealthResponse,
    ScrapeRequest,
    ScrapeResponse,
    IngestRequest,
    IngestResponse,
    SessionDetailResponse,
    SessionListResponse,
    JobStatusResponse,
)
from api.session_manager import session_manager
from api.interaction_logger import log_interaction_background
from rag.chatbot import SurfacesChatbot
from rag.vector_store import SurfacesVectorStore
from rag.retriever import SurfacesRetriever
from rag.embeddings import GeminiEmbeddingService
from rag.chunker import ContentChunker
from scraper.scraper import SurfacesScraper

logger = logging.getLogger(__name__)

router = APIRouter()

# Global state and synchronization locks
_state_lock = threading.Lock()
_vector_store: Optional[SurfacesVectorStore] = None
_embedding_service: Optional[GeminiEmbeddingService] = None
_chatbot: Optional[SurfacesChatbot] = None

# Background job tracking
_scrape_lock = threading.Lock()
_ingest_lock = threading.Lock()
_job_status: Dict[str, Any] = {
    "scrape_running": False,
    "ingest_running": False,
    "last_scrape": None,
    "last_ingest": None
}


def get_vector_store() -> SurfacesVectorStore:
    global _vector_store
    if _vector_store is None:
        with _state_lock:
            if _vector_store is None:
                _vector_store = SurfacesVectorStore()
    return _vector_store


def get_embedding_service() -> GeminiEmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        with _state_lock:
            if _embedding_service is None:
                _embedding_service = GeminiEmbeddingService()
    return _embedding_service


def get_chatbot(
    vstore: SurfacesVectorStore = Depends(get_vector_store),
    embs: GeminiEmbeddingService = Depends(get_embedding_service)
) -> SurfacesChatbot:
    global _chatbot
    if _chatbot is None:
        with _state_lock:
            if _chatbot is None:
                retriever = SurfacesRetriever(vector_store=vstore, embedding_service=embs)
                _chatbot = SurfacesChatbot(retriever=retriever)
    return _chatbot


@router.get("/health", response_model=HealthResponse, summary="API and Knowledge Base Health Check")
def health_check(vstore: SurfacesVectorStore = Depends(get_vector_store)):
    """Check status of API, vector store document count, and Gemini API readiness."""
    has_key = bool(settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here")
    try:
        count = vstore.count()
        status_str = "healthy"
    except Exception as e:
        logger.warning(f"ChromaDB health check degraded: {e}")
        count = 0
        status_str = "degraded"

    return HealthResponse(
        status=status_str,
        document_count=count,
        gemini_configured=has_key,
        embedding_model=settings.gemini_embedding_model,
        llm_model=settings.gemini_model,
        version="1.0.0"
    )


@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True, summary="Ask the Surfaces Tiles UK Chatbot")
def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    chatbot: SurfacesChatbot = Depends(get_chatbot)
):
    """Customer-facing RAG endpoint for questions about tiles, specs, delivery, pricing, and policies."""
    interaction_time = datetime.now()
    clean_message = (request.message or "").strip()
    session_id = request.session_id

    if not clean_message:
        error_payload = {"detail": "The 'message' field cannot be empty."}
        log_interaction_background(
            background_tasks=None,
            user_input=request.message or "",
            internal_response={"status_code": 400, "validation_error": "Empty message"},
            ai_response="None (Validation error)",
            user_response=error_payload,
            timestamp=interaction_time,
        )
        raise HTTPException(status_code=400, detail="The 'message' field cannot be empty.")

    # Resolve chat history:
    # 1. If explicit client-provided history is given, use it (and seed session memory)
    # 2. Otherwise retrieve from server-side session memory
    resolved_history: List[Any] = []
    if request.history:
        resolved_history = request.history[-settings.max_chat_history:]
        session_manager.set_history(session_id, resolved_history)
    else:
        resolved_history = session_manager.get_history(session_id)

    try:
        result = chatbot.answer_question(
            message=clean_message,
            history=resolved_history
        )

        response_text = result.get("answer", "")
        raw_sources = result.get("sources", [])

        # Format sources for response payload
        formatted_sources = []
        for s in raw_sources:
            try:
                formatted_sources.append(SourceItem(
                    title=s.get("title") or "Surfaces Tiles UK",
                    url=s.get("url") or settings.base_url,
                    category=s.get("category"),
                    content_type=s.get("content_type"),
                    price=s.get("price"),
                    relevance_score=s.get("relevance_score")
                ))
            except Exception:
                continue

        # Update session memory
        updated_history = session_manager.add_turn(
            session_id=session_id,
            user_message=clean_message,
            assistant_response=response_text
        )

        chat_response = ChatResponse(
            meta=ResponseMeta(
                status=1,
                message="Successfully processed user measurements and preferences"
            ),
            data=ChatData(
                Response=response_text
            ),
            statusCode=200
        )

        internal_system_details = {
            "status_code": 200,
            "session_id": session_id,
            "history_length": len(resolved_history),
            "system_meta": chat_response.meta.model_dump(),
            "retrieved_sources_count": len(raw_sources),
            "retrieved_sources": raw_sources,
        }

        # Asynchronously log the interaction (non-blocking for the client)
        log_interaction_background(
            background_tasks=background_tasks,
            user_input=clean_message,
            internal_response=internal_system_details,
            ai_response=response_text,
            user_response=chat_response.model_dump(),
            timestamp=interaction_time,
        )

        return chat_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        error_payload = {"detail": f"Internal chat error: {str(e)}"}
        log_interaction_background(
            background_tasks=None,
            user_input=clean_message,
            internal_response={"status_code": 500, "error": str(e)},
            ai_response="None (Error occurred during generation)",
            user_response=error_payload,
            timestamp=interaction_time,
        )
        raise HTTPException(status_code=500, detail=f"Internal chat error: {str(e)}")


@router.get("/sessions", response_model=SessionListResponse, summary="List Active Sessions")
def list_sessions_endpoint():
    """Retrieve list of active session IDs and total session count."""
    return SessionListResponse(
        total_sessions=session_manager.get_session_count(),
        sessions=session_manager.list_sessions()
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, summary="Get Session History")
def get_session_endpoint(session_id: str):
    """Retrieve full conversation history for a specific session UUID."""
    try:
        valid_sid = str(uuid.UUID(session_id.strip()))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid session_id '{session_id}'. Must be a valid UUID.")

    history = session_manager.get_history(valid_sid)
    return SessionDetailResponse(
        session_id=valid_sid,
        message_count=len(history),
        history=history
    )


@router.delete("/sessions/{session_id}", summary="Clear Session History")
def clear_session_endpoint(session_id: str):
    """Reset or clear conversation memory for a specific session UUID."""
    try:
        valid_sid = str(uuid.UUID(session_id.strip()))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid session_id '{session_id}'. Must be a valid UUID.")

    success = session_manager.clear_session(valid_sid)
    return {
        "status": "success" if success else "not_found",
        "session_id": valid_sid,
        "message": f"Session '{valid_sid}' cleared." if success else f"Session '{valid_sid}' was not active."
    }


def _run_scrape_job():
    global _job_status
    try:
        scraper = SurfacesScraper()
        result = scraper.run()
        _job_status["last_scrape"] = {
            "status": "success",
            "finished_at": datetime.now().isoformat(),
            "counts": result.get("counts")
        }
    except Exception as e:
        logger.error(f"Background scrape failed: {e}", exc_info=True)
        _job_status["last_scrape"] = {
            "status": "error",
            "finished_at": datetime.now().isoformat(),
            "error": str(e)
        }
    finally:
        _job_status["scrape_running"] = False
        if _scrape_lock.locked():
            _scrape_lock.release()


@router.post("/scrape", response_model=ScrapeResponse, summary="Trigger Website Scrape")
def scrape_endpoint(
    background_tasks: BackgroundTasks,
    request: ScrapeRequest = ScrapeRequest()
):
    """Scrape product catalog, policies, FAQs, and blogs from surfacestiles.co.uk."""
    if not _scrape_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A scrape job is already currently in progress. Please check /jobs/status."
        )

    _job_status["scrape_running"] = True
    _job_status["last_scrape"] = {"status": "running", "started_at": datetime.now().isoformat()}

    if request.run_in_background:
        background_tasks.add_task(_run_scrape_job)
        return ScrapeResponse(
            status="accepted",
            message="Scraping started in the background. Check /jobs/status for progress."
        )

    try:
        scraper = SurfacesScraper()
        result = scraper.run()
        _job_status["last_scrape"] = {
            "status": "success",
            "finished_at": datetime.now().isoformat(),
            "counts": result.get("counts")
        }
        return ScrapeResponse(
            status="success",
            message="Website scrape completed successfully.",
            counts=result.get("counts")
        )
    except Exception as e:
        logger.error(f"Scrape failed: {e}", exc_info=True)
        _job_status["last_scrape"] = {
            "status": "error",
            "finished_at": datetime.now().isoformat(),
            "error": str(e)
        }
        raise HTTPException(status_code=500, detail=f"Scrape error: {str(e)}")
    finally:
        _job_status["scrape_running"] = False
        if _scrape_lock.locked():
            _scrape_lock.release()


def _run_ingest_job(force_reset: bool = True):
    global _job_status
    try:
        chunker = ContentChunker()
        chunks = chunker.process_all()
        if not chunks:
            logger.warning("No chunks to ingest.")
            _job_status["last_ingest"] = {
                "status": "warning",
                "finished_at": datetime.now().isoformat(),
                "message": "No chunks found to ingest."
            }
            return

        texts = [c["text"] for c in chunks]
        emb_svc = get_embedding_service()
        embeddings = emb_svc.embed_batch(texts)

        vstore = get_vector_store()
        if force_reset:
            vstore.reset()
        vstore.add_documents(chunks=chunks, embeddings=embeddings)
        total_indexed = vstore.count()
        logger.info(f"Ingested {len(chunks)} chunks into vector store.")
        _job_status["last_ingest"] = {
            "status": "success",
            "finished_at": datetime.now().isoformat(),
            "chunks_indexed": total_indexed
        }
    except Exception as e:
        logger.error(f"Background ingestion failed: {e}", exc_info=True)
        _job_status["last_ingest"] = {
            "status": "error",
            "finished_at": datetime.now().isoformat(),
            "error": str(e)
        }
    finally:
        _job_status["ingest_running"] = False
        if _ingest_lock.locked():
            _ingest_lock.release()


@router.post("/ingest", response_model=IngestResponse, summary="Chunk Data, Generate Embeddings, and Populate Vector Store")
def ingest_endpoint(
    background_tasks: BackgroundTasks,
    request: IngestRequest = IngestRequest(),
    vstore: SurfacesVectorStore = Depends(get_vector_store),
    emb_svc: GeminiEmbeddingService = Depends(get_embedding_service)
):
    """Process scraped data into chunks, compute gemini-embedding-001 vectors, and index in ChromaDB."""
    if not _ingest_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="An ingestion job is already currently running. Please check /jobs/status."
        )

    _job_status["ingest_running"] = True
    _job_status["last_ingest"] = {"status": "running", "started_at": datetime.now().isoformat()}

    if request.run_in_background:
        background_tasks.add_task(_run_ingest_job, request.force_reset)
        return IngestResponse(
            status="accepted",
            message="Ingestion process launched in background. Check /jobs/status for progress.",
            chunks_indexed=0
        )

    try:
        chunker = ContentChunker()
        chunks = chunker.process_all()
        if not chunks:
            _job_status["last_ingest"] = {
                "status": "warning",
                "finished_at": datetime.now().isoformat(),
                "message": "No chunks generated."
            }
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

        _job_status["last_ingest"] = {
            "status": "success",
            "finished_at": datetime.now().isoformat(),
            "chunks_indexed": total_indexed
        }
        return IngestResponse(
            status="success",
            message=f"Successfully indexed {len(chunks)} chunks into ChromaDB.",
            chunks_indexed=total_indexed
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        _job_status["last_ingest"] = {
            "status": "error",
            "finished_at": datetime.now().isoformat(),
            "error": str(e)
        }
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")
    finally:
        _job_status["ingest_running"] = False
        if _ingest_lock.locked():
            _ingest_lock.release()


@router.get("/jobs/status", response_model=JobStatusResponse, summary="Background Job Status")
def get_jobs_status():
    """Check whether scraping or ingestion jobs are currently running and view last run results."""
    return JobStatusResponse(
        scrape_running=_job_status["scrape_running"],
        ingest_running=_job_status["ingest_running"],
        last_scrape=_job_status["last_scrape"],
        last_ingest=_job_status["last_ingest"]
    )
