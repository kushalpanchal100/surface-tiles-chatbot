import time
import logging
from typing import Optional, Union, Dict, Any, List, BinaryIO
from pathlib import Path

from config.settings import settings
from voice.stt import BaseSTTService, FasterWhisperSTTService
from voice.tts import BaseTTSService, EdgeTTSService
from rag.chatbot import SurfacesChatbot

logger = logging.getLogger(__name__)


class VoiceAssistantService:
    """Orchestrates end-to-end Voice Assistant interactions:
    User Audio -> Faster-Whisper STT -> RAG Chatbot -> Neural Edge-TTS -> Audio Response
    """

    def __init__(
        self,
        stt_service: Optional[BaseSTTService] = None,
        tts_service: Optional[BaseTTSService] = None,
        chatbot: Optional[SurfacesChatbot] = None
    ):
        self.stt_service = stt_service or FasterWhisperSTTService()
        self.tts_service = tts_service or EdgeTTSService()
        self.chatbot = chatbot

    async def process_voice_chat(
        self,
        audio_input: Union[str, Path, bytes, BinaryIO],
        session_id: str,
        chatbot: SurfacesChatbot,
        history: Optional[List[Any]] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute the full voice interaction pipeline."""
        start_time = time.time()

        # 1. Step 1: Speech-to-Text (STT) via Faster-Whisper Small (CPU)
        stt_result = self.stt_service.transcribe(audio_input, language=language)
        transcribed_text = (stt_result.get("text") or "").strip()

        logger.info(f"[VoiceAssistant] Transcribed user audio: '{transcribed_text}'")

        # Handle case where no speech was detected
        if not transcribed_text:
            empty_msg = "I couldn't clearly hear or understand the audio. Could you please try speaking again?"
            tts_res = await self.tts_service.synthesize(empty_msg)
            return {
                "transcribed_text": "",
                "response_text": empty_msg,
                "audio_base64": tts_res["audio_base64"],
                "audio_format": "mp3",
                "sources": [],
                "session_id": session_id,
                "timings": {
                    "stt_seconds": stt_result.get("latency_seconds", 0),
                    "rag_seconds": 0,
                    "tts_seconds": tts_res.get("latency_seconds", 0),
                    "total_seconds": round(time.time() - start_time, 3)
                }
            }

        # 2. Step 2: RAG Chatbot query
        # Resolve history: if passed use it, otherwise get from session_manager
        from api.session_manager import session_manager

        if history:
            resolved_history = history[-settings.max_chat_history:]
            session_manager.set_history(session_id, resolved_history)
        else:
            resolved_history = session_manager.get_history(session_id)

        rag_start = time.time()
        chatbot_result = chatbot.answer_question(
            message=transcribed_text,
            history=resolved_history
        )
        rag_latency = time.time() - rag_start

        response_text = chatbot_result.get("answer", "")
        raw_sources = chatbot_result.get("sources", [])
        raw_products = chatbot_result.get("products", [])

        # 3. Step 3: Text-to-Speech (TTS) via Neural Edge-TTS
        tts_result = await self.tts_service.synthesize(response_text)

        # 4. Step 4: Update session memory
        session_manager.add_turn(
            session_id=session_id,
            user_message=transcribed_text,
            assistant_response=response_text
        )

        total_latency = time.time() - start_time
        logger.info(
            f"[VoiceAssistant] Completed full pipeline in {total_latency:.2f}s "
            f"(STT: {stt_result.get('latency_seconds'):.2f}s, "
            f"RAG: {rag_latency:.2f}s, "
            f"TTS: {tts_result.get('latency_seconds'):.2f}s)"
        )

        return {
            "transcribed_text": transcribed_text,
            "response_text": response_text,
            "audio_base64": tts_result["audio_base64"],
            "audio_format": "mp3",
            "sources": raw_sources,
            "products": raw_products,
            "session_id": session_id,
            "timings": {
                "stt_seconds": stt_result.get("latency_seconds", 0),
                "rag_seconds": round(rag_latency, 3),
                "tts_seconds": tts_result.get("latency_seconds", 0),
                "total_seconds": round(total_latency, 3)
            }
        }
