import uuid
import base64
import logging
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, UploadFile, File, Form
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
    VoiceChatResponse,
    VoiceChatData,
    TranscribeResponse,
    SynthesizeRequest,
    SynthesizeResponse,
)
from voice import get_voice_service, get_stt_service, get_tts_service
from voice.service import VoiceAssistantService
from voice.stt import BaseSTTService
from voice.tts import BaseTTSService
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


@router.post("/voice/chat", response_model=VoiceChatResponse, response_model_exclude_none=True, summary="Voice Chat: Audio In -> STT -> RAG -> TTS -> Audio Out")
async def voice_chat_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    chatbot: SurfacesChatbot = Depends(get_chatbot),
    voice_service: VoiceAssistantService = Depends(get_voice_service)
):
    """Customer-facing voice chat endpoint.
    
    Accepts user audio (via multipart/form-data upload or application/json with base64 audio),
    transcribes it with Faster-Whisper Small (CPU int8), queries the Surfaces Tiles RAG chatbot,
    and synthesizes natural neural speech with Edge-TTS.
    """
    interaction_time = datetime.now()
    audio_bytes: Optional[bytes] = None
    session_id: Optional[str] = None
    content_type = request.headers.get("content-type", "")

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload = form.get("audio") or form.get("file")
            session_id = form.get("session_id")
            if upload and hasattr(upload, "read"):
                audio_bytes = await upload.read()
        elif "application/json" in content_type:
            body = await request.json()
            session_id = body.get("session_id")
            raw_b64 = body.get("audio_base64") or body.get("audio") or ""
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            if raw_b64:
                audio_bytes = base64.b64decode(raw_b64)
        else:
            # Fallback: attempt to read raw request body directly
            raw_body = await request.body()
            if raw_body:
                audio_bytes = raw_body

        if not audio_bytes or len(audio_bytes) < 100:
            raise HTTPException(
                status_code=400,
                detail="No valid audio data provided or audio file is empty."
            )

        # Validate or generate session UUID
        if not session_id or not str(session_id).strip():
            session_id = str(uuid.uuid4())
        else:
            try:
                session_id = str(uuid.UUID(str(session_id).strip()))
            except (ValueError, AttributeError):
                session_id = str(uuid.uuid4())

        # Process voice through STT -> RAG -> TTS
        result = await voice_service.process_voice_chat(
            audio_input=audio_bytes,
            session_id=session_id,
            chatbot=chatbot
        )

        user_transcript = result.get("transcribed_text", "")
        response_text = result.get("response_text", "")
        raw_sources = result.get("sources", [])

        # Format sources
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

        voice_chat_response = VoiceChatResponse(
            meta=ResponseMeta(
                status=1,
                message="Voice chat processed successfully"
            ),
            data=VoiceChatData(
                user_transcript=user_transcript,
                Response=response_text,
                audio_base64=result.get("audio_base64", ""),
                audio_format=result.get("audio_format", "mp3"),
                session_id=session_id,
                sources=formatted_sources if formatted_sources else None,
                timings=result.get("timings")
            ),
            statusCode=200
        )

        # Non-blocking background interaction logging
        internal_details = {
            "status_code": 200,
            "session_id": session_id,
            "mode": "voice",
            "timings": result.get("timings"),
            "sources_count": len(raw_sources),
        }
        log_interaction_background(
            background_tasks=background_tasks,
            user_input=f"[VOICE] {user_transcript}",
            internal_response=internal_details,
            ai_response=response_text,
            user_response=voice_chat_response.model_dump(),
            timestamp=interaction_time,
        )

        return voice_chat_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing voice chat: {e}", exc_info=True)
        error_payload = {"detail": f"Internal voice error: {str(e)}"}
        log_interaction_background(
            background_tasks=None,
            user_input="[VOICE ERROR]",
            internal_response={"status_code": 500, "error": str(e)},
            ai_response="None (Error in voice processing)",
            user_response=error_payload,
            timestamp=interaction_time,
        )
        raise HTTPException(status_code=500, detail=f"Internal voice chat error: {str(e)}")


@router.post("/voice/transcribe", response_model=TranscribeResponse, summary="Transcribe Audio to Text (STT Only)")
async def voice_transcribe_endpoint(
    request: Request,
    stt_service: BaseSTTService = Depends(get_stt_service)
):
    """Standalone Speech-to-Text endpoint using Faster-Whisper Small."""
    content_type = request.headers.get("content-type", "")
    audio_bytes: Optional[bytes] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("audio") or form.get("file")
        if upload and hasattr(upload, "read"):
            audio_bytes = await upload.read()
    elif "application/json" in content_type:
        body = await request.json()
        raw_b64 = body.get("audio_base64") or body.get("audio") or ""
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        if raw_b64:
            audio_bytes = base64.b64decode(raw_b64)
    else:
        raw_body = await request.body()
        if raw_body:
            audio_bytes = raw_body

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio file or data provided.")

    try:
        result = stt_service.transcribe(audio_bytes)
        return TranscribeResponse(
            text=result.get("text", ""),
            language=result.get("language", "en"),
            duration=result.get("duration", 0.0),
            latency_seconds=result.get("latency_seconds", 0.0)
        )
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")


@router.post("/voice/synthesize", response_model=SynthesizeResponse, summary="Synthesize Text to Speech (TTS Only)")
async def voice_synthesize_endpoint(
    request: SynthesizeRequest,
    tts_service: BaseTTSService = Depends(get_tts_service)
):
    """Standalone Text-to-Speech endpoint using Edge-TTS with British English voice."""
    clean_input = (request.text or "").strip()
    if not clean_input:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        result = await tts_service.synthesize(text=clean_input, voice=request.voice)
        return SynthesizeResponse(
            audio_base64=result["audio_base64"],
            audio_format=result["audio_format"],
            clean_text=result["clean_text"],
            latency_seconds=result["latency_seconds"]
        )
    except Exception as e:
        logger.error(f"Error synthesizing speech: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech synthesis error: {str(e)}")


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
