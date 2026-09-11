import io
import os
import time
import tempfile
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union, Dict, Any, BinaryIO

from config.settings import settings

logger = logging.getLogger(__name__)


class BaseSTTService(ABC):
    """Abstract base class for Speech-to-Text services."""

    @abstractmethod
    def transcribe(
        self,
        audio_input: Union[str, Path, bytes, BinaryIO],
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transcribe audio to text.
        
        Args:
            audio_input: Audio file path, bytes, or binary stream.
            language: Optional language code (default: 'en').
            
        Returns:
            Dict containing 'text', 'language', 'duration', etc.
        """
        pass


class FasterWhisperSTTService(BaseSTTService):
    """Speech-to-Text service powered by Faster-Whisper Small optimized for CPU."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        cpu_threads: Optional[int] = None,
        default_language: Optional[str] = None
    ):
        self.model_size = model_size or settings.stt_model
        self.device = device or settings.stt_device
        self.compute_type = compute_type or settings.stt_compute_type
        self.cpu_threads = cpu_threads or settings.stt_cpu_threads
        self.default_language = default_language or settings.stt_language
        
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        """Lazy thread-safe singleton initialization of the WhisperModel."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel

                    logger.info(
                        f"Loading Faster-Whisper '{self.model_size}' model on {self.device.upper()} "
                        f"(compute_type={self.compute_type}, threads={self.cpu_threads})..."
                    )
                    start_time = time.time()
                    hf_token = getattr(settings, "hf_token", None) or os.environ.get("HF_TOKEN")
                    try:
                        # Try loading from local cache first for instant startup without network roundtrips or HF Hub warnings
                        self._model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads,
                            num_workers=1,
                            local_files_only=True
                        )
                    except Exception:
                        # Fallback to remote download if model is not yet cached locally
                        logger.info(f"Model '{self.model_size}' not in local cache, downloading from Hugging Face Hub...")
                        self._model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads,
                            num_workers=1,
                            local_files_only=False,
                            use_auth_token=hf_token
                        )
                    load_duration = time.time() - start_time
                    logger.info(f"Faster-Whisper model loaded in {load_duration:.2f}s")
        return self._model

    def warm_up(self):
        """Warm up the Whisper model in background/startup."""
        try:
            self._get_model()
            logger.info("Faster-Whisper STT service pre-warmed and ready.")
        except Exception as e:
            logger.warning(f"Faster-Whisper pre-warm encountered an issue: {e}")

    def transcribe(
        self,
        audio_input: Union[str, Path, bytes, BinaryIO],
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transcribe an audio file, bytes buffer, or binary stream.
        
        Optimized for ultra-low latency on CPU:
        - compute_type='int8' quantization
        - In-memory stream decoding via io.BytesIO (no disk I/O)
        - vad_filter=True with tuned min_silence_duration_ms
        - beam_size=1 (greedy search)
        - without_timestamps=True and condition_on_previous_text=False
        - temperature=0.0
        """
        model = self._get_model()
        target_lang = language or self.default_language

        temp_file_path = None
        try:
            # Handle input types: use in-memory stream to avoid disk temporary file I/O
            if isinstance(audio_input, (bytes, bytearray)):
                file_to_process = io.BytesIO(audio_input)
            elif hasattr(audio_input, "read"):
                raw = audio_input.read()
                file_to_process = io.BytesIO(raw) if isinstance(raw, (bytes, bytearray)) else raw
            else:
                file_to_process = str(audio_input)

            start_time = time.time()
            min_silence = getattr(settings, "stt_min_silence_duration_ms", 300)
            segments, info = model.transcribe(
                file_to_process,
                language=target_lang,
                beam_size=settings.stt_beam_size,
                vad_filter=settings.stt_vad_filter,
                vad_parameters=dict(min_silence_duration_ms=min_silence),
                without_timestamps=True,
                condition_on_previous_text=False,
                temperature=0.0,
                task="transcribe"
            )

            # Assemble transcribed text from segments
            text_segments = []
            segment_details = []
            for seg in segments:
                clean_seg = seg.text.strip()
                if clean_seg:
                    text_segments.append(clean_seg)
                    segment_details.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": clean_seg
                    })

            full_text = " ".join(text_segments).strip()
            elapsed_time = time.time() - start_time

            logger.info(
                f"Transcribed {info.duration:.2f}s audio in {elapsed_time:.2f}s "
                f"({full_text[:60]}...)"
            )

            return {
                "text": full_text,
                "language": info.language,
                "language_probability": round(info.language_probability, 3),
                "duration": round(info.duration, 2),
                "latency_seconds": round(elapsed_time, 3),
                "segments": segment_details
            }

        except Exception as e:
            logger.error(f"Error during Faster-Whisper transcription: {e}", exc_info=True)
            raise
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_err:
                    logger.warning(f"Failed to remove temp audio file {temp_file_path}: {cleanup_err}")
