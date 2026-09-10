import threading
from typing import Optional

from voice.stt import BaseSTTService, FasterWhisperSTTService
from voice.tts import BaseTTSService, EdgeTTSService
from voice.service import VoiceAssistantService

_stt_lock = threading.Lock()
_tts_lock = threading.Lock()
_voice_lock = threading.Lock()

_stt_service: Optional[BaseSTTService] = None
_tts_service: Optional[BaseTTSService] = None
_voice_service: Optional[VoiceAssistantService] = None


def get_stt_service() -> BaseSTTService:
    """Get or create singleton STT service instance."""
    global _stt_service
    if _stt_service is None:
        with _stt_lock:
            if _stt_service is None:
                _stt_service = FasterWhisperSTTService()
    return _stt_service


def get_tts_service() -> BaseTTSService:
    """Get or create singleton TTS service instance."""
    global _tts_service
    if _tts_service is None:
        with _tts_lock:
            if _tts_service is None:
                _tts_service = EdgeTTSService()
    return _tts_service


def get_voice_service() -> VoiceAssistantService:
    """Get or create singleton VoiceAssistantService orchestrator."""
    global _voice_service
    if _voice_service is None:
        with _voice_lock:
            if _voice_service is None:
                _voice_service = VoiceAssistantService(
                    stt_service=get_stt_service(),
                    tts_service=get_tts_service()
                )
    return _voice_service


__all__ = [
    "BaseSTTService",
    "FasterWhisperSTTService",
    "BaseTTSService",
    "EdgeTTSService",
    "VoiceAssistantService",
    "get_stt_service",
    "get_tts_service",
    "get_voice_service",
]
