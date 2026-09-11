import re
import io
import time
import base64
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

import edge_tts

from config.settings import settings

logger = logging.getLogger(__name__)


def clean_text_for_speech(text: str) -> str:
    """Normalize markdown and technical e-commerce text into natural, spoken English.
    
    Transforms:
    - Markdown links [Product Name](url) -> 'Product Name'
    - Bare URLs -> removed or simplified
    - Bold/Italic formatting -> clean text
    - Bullet points & list markers -> conversational pauses
    - Currency £28.50 -> '28 pounds 50' or '28.50 pounds'
    - Units m² / m2 -> 'square metres'
    - Quotes, headers, code blocks -> clean conversational text
    """
    if not text:
        return ""

    cleaned = text

    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # Convert markdown links [Label](url) -> Label
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)

    # Remove raw URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # Convert currency (£XX or £XX.YY)
    def _replace_currency(match):
        val = match.group(1)
        if "." in val:
            parts = val.split(".")
            if len(parts) == 2 and parts[1] != "00":
                return f"{parts[0]} pounds and {parts[1]} pence"
            return f"{parts[0]} pounds"
        return f"{val} pounds"

    cleaned = re.sub(r"£(\d+(?:\.\d{2})?)", _replace_currency, cleaned)

    # Convert m² / m2 / m^2 to square metres
    cleaned = re.sub(r"\b(\d+)\s*(?:m²|m2|m\^2|sqm|sq\s*m)\b", r"\1 square metres", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"/(?:m²|m2|sqm)", " per square metre", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bper\s*(?:m²|m2|sqm)\b", "per square metre", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:m²|m2|m\^2|sqm)", "square metres", cleaned, flags=re.IGNORECASE)

    # Convert mm/cm dimensions like 600x600mm -> 600 by 600 millimetres
    cleaned = re.sub(r"(\d+)\s*[xX*]\s*(\d+)\s*mm\b", r"\1 by \2 millimetres", cleaned)
    cleaned = re.sub(r"(\d+)\s*[xX*]\s*(\d+)\s*cm\b", r"\1 by \2 centimetres", cleaned)

    # Remove markdown headers (### Header)
    cleaned = re.sub(r"^\s*#{1,6}\s+", "", cleaned, flags=re.MULTILINE)

    # Remove bold, italics, strikethrough: **word**, *word*, ~~word~~
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = re.sub(r"~~([^~]+)~~", r"\1", cleaned)

    # Remove list bullet markers (- , * , 1. ) and replace with slight pauses
    cleaned = re.sub(r"^\s*[-*+]\s+", ". ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", ". ", cleaned, flags=re.MULTILINE)

    # Remove reference brackets like [1], [Source 2]
    cleaned = re.sub(r"\[(?:\d+|source:\s*[^\]]+)\]", "", cleaned, flags=re.IGNORECASE)

    # Clean punctuation and multiple whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n+", ". ", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)

    return cleaned.strip()


def split_sentences(text: str) -> list[str]:
    """Split text into natural spoken sentences for chunked audio streaming."""
    if not text:
        return []
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return []
    raw = re.split(r'(?<=[.?!])\s+', cleaned)
    return [s.strip() for s in raw if s.strip()]


class BaseTTSService(ABC):
    """Abstract base class for Text-to-Speech services."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synthesize text into speech audio.
        
        Args:
            text: Input text to convert to speech.
            voice: Optional voice name/identifier.
            
        Returns:
            Dict containing 'audio_bytes', 'audio_base64', 'format', etc.
        """
        pass


class EdgeTTSService(BaseTTSService):
    """Fast, natural neural Text-to-Speech service using Microsoft Edge TTS."""

    def __init__(
        self,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ):
        self.voice = voice or settings.tts_voice
        self.rate = rate or settings.tts_rate
        self.pitch = pitch or settings.tts_pitch

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synthesize text into natural-sounding MP3 speech asynchronously."""
        selected_voice = voice or self.voice
        clean_text = clean_text_for_speech(text)

        if not clean_text:
            clean_text = "I'm sorry, I have no response to speak."

        start_time = time.time()
        try:
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=selected_voice,
                rate=self.rate,
                pitch=self.pitch
            )

            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            audio_bytes = b"".join(audio_chunks)
            elapsed_time = time.time() - start_time

            b64_str = base64.b64encode(audio_bytes).decode("utf-8")
            data_uri = f"data:audio/mp3;base64,{b64_str}"

            logger.info(
                f"Synthesized {len(clean_text)} chars in {elapsed_time:.2f}s "
                f"using {selected_voice} ({len(audio_bytes)} bytes MP3)"
            )

            return {
                "audio_bytes": audio_bytes,
                "audio_base64": data_uri,
                "audio_format": "mp3",
                "clean_text": clean_text,
                "voice": selected_voice,
                "size_bytes": len(audio_bytes),
                "latency_seconds": round(elapsed_time, 3)
            }

        except Exception as e:
            logger.error(f"Error synthesizing speech with edge-tts: {e}", exc_info=True)
            raise

    def synthesize_sync(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous helper that runs the async synthesize in an event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In an already running event loop (e.g. FastAPI), run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: asyncio.run(self.synthesize(text, voice)))
                    return future.result()
            else:
                return loop.run_until_complete(self.synthesize(text, voice))
        except RuntimeError:
            return asyncio.run(self.synthesize(text, voice))
