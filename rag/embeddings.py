import time
import logging
from typing import List, Optional
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


class GeminiEmbeddingService:
    """Service to generate vector embeddings using Google Gemini API (gemini-embedding-001)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        batch_size: int = 50,
        mock_mode: bool = False
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_embedding_model
        self.batch_size = batch_size
        self.mock_mode = mock_mode or not bool(self.api_key and self.api_key != "your_gemini_api_key_here")
        self.client = None

        if not self.mock_mode:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Gemini Client for embeddings with model {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize live Gemini client ({e}). Falling back to mock embeddings mode.")
                self.mock_mode = True
        else:
            logger.info("Operating GeminiEmbeddingService in mock/offline mode.")

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        results = self.embed_batch([text])
        return results[0] if results else []

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts in batches."""
        if not texts:
            return []

        if self.mock_mode or not self.client:
            return [self._generate_mock_embedding(t) for t in texts]

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            retries = 5
            backoff = 2.0

            while retries > 0:
                try:
                    from google.genai import types
                    response = self.client.models.embed_content(
                        model=self.model_name,
                        contents=batch,
                        config=types.EmbedContentConfig(output_dimensionality=768)
                    )
                    batch_vectors = []
                    if hasattr(response, "embeddings") and response.embeddings:
                        for emb in response.embeddings:
                            batch_vectors.append(list(emb.values))
                    elif hasattr(response, "embedding") and response.embedding:
                        batch_vectors.append(list(response.embedding.values))
                    else:
                        raise ValueError(f"Unexpected response format from Gemini: {response}")

                    all_embeddings.extend(batch_vectors)
                    break
                except Exception as e:
                    retries -= 1
                    err_str = str(e)
                    wait_time = backoff
                    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        import re
                        delay_match = re.search(r"retry\s+in\s+([\d\.]+)\s*s", err_str, re.IGNORECASE)
                        if delay_match:
                            wait_time = float(delay_match.group(1)) + 2.0
                        else:
                            wait_time = 35.0
                        logger.warning(f"Rate limit hit. Waiting {wait_time:.1f}s before retry... (Retries remaining: {retries})")
                    else:
                        logger.warning(f"Embedding batch error: {e}. Retries remaining: {retries}")

                    if retries == 0:
                        logger.error(f"Failed to generate embeddings after multiple attempts: {e}")
                        all_embeddings.extend([self._generate_mock_embedding(t) for t in batch])
                    else:
                        time.sleep(wait_time)
                        backoff *= 2

            # Delay to respect API rate limits
            if i + self.batch_size < len(texts):
                time.sleep(1.0)

        return all_embeddings

    def _generate_mock_embedding(self, text: str, dimension: int = 768) -> List[float]:
        """Deterministic bag-of-words hash projection for testing when offline or without API key."""
        import hashlib
        import re

        vec = np.zeros(dimension, dtype=np.float32)
        words = re.findall(r"\w+", text.lower())
        if not words:
            words = ["empty"]
        for w in words:
            idx = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
