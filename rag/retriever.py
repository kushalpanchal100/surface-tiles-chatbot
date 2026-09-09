import logging
from typing import List, Dict, Any, Optional

from config.settings import settings
from rag.embeddings import GeminiEmbeddingService
from rag.vector_store import SurfacesVectorStore

logger = logging.getLogger(__name__)


class SurfacesRetriever:
    """Retrieves relevant website content from ChromaDB using Gemini embeddings."""

    def __init__(
        self,
        vector_store: Optional[SurfacesVectorStore] = None,
        embedding_service: Optional[GeminiEmbeddingService] = None,
        top_k: int = settings.top_k
    ):
        self.vector_store = vector_store or SurfacesVectorStore()
        self.embedding_service = embedding_service or GeminiEmbeddingService()
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
        content_type_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve relevant chunks and construct formatted context with sources."""
        k = top_k or self.top_k

        # Construct metadata filter if requested
        where_filter = None
        if category_filter and content_type_filter:
            where_filter = {
                "$and": [
                    {"category": category_filter},
                    {"content_type": content_type_filter}
                ]
            }
        elif category_filter:
            where_filter = {"category": category_filter}
        elif content_type_filter:
            where_filter = {"content_type": content_type_filter}

        # Embed query
        query_embedding = self.embedding_service.embed_text(query)
        if not query_embedding:
            logger.warning("Failed to generate embedding for query.")
            return {"context": "", "sources": [], "chunks": []}

        # Search vector store candidate pool
        candidate_k = max(k * 2, 20)
        raw_hits = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=candidate_k,
            where_filter=where_filter
        )

        # Apply room-intent and domain re-ranking
        ranked_hits = self._rerank_hits(raw_hits, query)
        hits = ranked_hits[:k]

        # Build sources list and context string
        sources: List[Dict[str, Any]] = []
        seen_urls = set()
        context_parts: List[str] = []

        for idx, hit in enumerate(hits, start=1):
            meta = hit.get("metadata", {})
            url = meta.get("url", "")
            title = meta.get("title") or meta.get("product_name") or "Surfaces Tiles UK"
            cat = meta.get("category")
            ctype = meta.get("content_type")
            price = meta.get("price")

            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append({
                    "title": title,
                    "url": url,
                    "category": cat,
                    "content_type": ctype,
                    "price": price if price else None,
                    "relevance_score": hit.get("score")
                })

            context_parts.append(
                f"--- DOCUMENT {idx} [Title: {title} | URL: {url}] ---\n"
                f"{hit.get('text', '')}"
            )

        formatted_context = "\n\n".join(context_parts)

        return {
            "context": formatted_context,
            "sources": sources,
            "chunks": hits
        }

    def _rerank_hits(self, hits: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Re-rank candidate chunks based on room intent, application suitability, and colour matching."""
        if not hits:
            return []

        q_lower = query.lower()

        has_indoor_intent = any(w in q_lower for w in ["bathroom", "bath", "shower", "kitchen", "indoor", "inside", "living", "bedroom", "hallway"])
        has_outdoor_intent = any(w in q_lower for w in ["outdoor", "patio", "terrace", "garden", "balcony", "exterior", "outside", "paving"])
        has_floor_intent = any(w in q_lower for w in ["floor", "flooring", "ground"])
        has_wall_intent = any(w in q_lower for w in ["wall", "walls", "splashback"])

        reranked = []
        for hit in hits:
            score = hit.get("score", 0.0)
            meta = hit.get("metadata", {})
            text = hit.get("text", "").lower()
            title = (meta.get("title") or meta.get("product_name") or "").lower()

            is_outdoor = bool(meta.get("is_outdoor", False)) or "outdoor" in title or "2cm" in title
            is_spc = bool(meta.get("is_spc", False)) or "spc" in title or "vinyl" in title

            boost = 0.0

            # Room & environment alignment
            if has_indoor_intent:
                if is_outdoor:
                    boost -= 0.15  # Penalize outdoor patio pavers for indoor inquiries
                else:
                    if "bathroom" in q_lower and ("bathroom" in text or "bathroom" in title):
                        boost += 0.08
                    if "kitchen" in q_lower and ("kitchen" in text or "kitchen" in title):
                        boost += 0.06
                    if has_floor_intent and ("floor" in text or "floor" in title):
                        boost += 0.04
                    if "porcelain" in text:
                        boost += 0.02
            elif has_outdoor_intent:
                if is_outdoor:
                    boost += 0.12
                else:
                    boost -= 0.08

            # Surface intent (floor vs wall)
            if has_floor_intent and not has_wall_intent:
                if "wall tiles" in title and "floor" not in title:
                    boost -= 0.05
                elif "floor" in text or "floor" in title:
                    boost += 0.03
            elif has_wall_intent and not has_floor_intent:
                if "wall" in text or "wall" in title:
                    boost += 0.04

            # Colour match boost
            colors = ["grey", "gray", "white", "black", "beige", "blue", "green", "gold", "charcoal", "cream", "anthracite", "ash"]
            for color in colors:
                if color in q_lower and (color in title or meta.get("color", "").lower() == color):
                    boost += 0.03
                    break

            adjusted_score = round(score + boost, 4)
            hit_copy = dict(hit)
            hit_copy["score"] = adjusted_score
            hit_copy["base_score"] = score
            reranked.append(hit_copy)

        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked
