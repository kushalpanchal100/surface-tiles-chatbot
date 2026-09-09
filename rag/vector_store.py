import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings

logger = logging.getLogger(__name__)


class SurfacesVectorStore:
    """ChromaDB-backed persistent vector database supporting similarity search

    and metadata filtering for Surfaces Tiles UK knowledge base.
    """

    COLLECTION_NAME = "surfaces_tiles_kb"

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Connected to ChromaDB at {self.persist_dir} (Collection: {self.COLLECTION_NAME})")

    def count(self) -> int:
        """Return total number of vectors in the collection."""
        return self.collection.count()

    def reset(self) -> None:
        """Delete all vectors in the collection to prepare for regeneration."""
        try:
            self.client.delete_collection(name=self.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("ChromaDB collection reset.")

    def add_documents(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> int:
        """Insert or upsert document chunks and their corresponding embeddings into ChromaDB."""
        if not chunks or not embeddings or len(chunks) != len(embeddings):
            raise ValueError(f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must match in length.")

        # Deduplicate chunks by ID defensively
        seen_ids = set()
        deduped_chunks = []
        deduped_embeddings = []
        for idx, chunk in enumerate(chunks):
            cid = str(chunk.get("id") or f"chunk_{idx}")
            if cid in seen_ids:
                cid = f"{cid}_{idx}"
            seen_ids.add(cid)
            chunk_copy = dict(chunk)
            chunk_copy["id"] = cid
            deduped_chunks.append(chunk_copy)
            deduped_embeddings.append(embeddings[idx])

        ids = [chunk["id"] for chunk in deduped_chunks]
        documents = [chunk["text"] for chunk in deduped_chunks]

        # ChromaDB metadata values must be str, int, float, or bool
        metadatas = []
        for chunk in deduped_chunks:
            raw_meta = chunk.get("metadata", {})
            clean_meta = {}
            for k, v in raw_meta.items():
                if v is None:
                    clean_meta[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

        batch_size = 200
        total = len(ids)
        for i in range(0, total, batch_size):
            end_idx = min(i + batch_size, total)
            self.collection.upsert(
                ids=ids[i:end_idx],
                documents=documents[i:end_idx],
                embeddings=deduped_embeddings[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

        logger.info(f"Successfully upserted {total} documents into ChromaDB.")
        return total

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform cosine similarity vector search with optional metadata filtering."""
        if not query_embedding:
            logger.warning("Empty query embedding passed to search.")
            return []

        if self.count() == 0:
            logger.warning("Vector store is empty. No documents to search.")
            return []

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self.count()),
            "include": ["documents", "metadatas", "distances"]
        }

        if where_filter:
            kwargs["where"] = where_filter

        try:
            results = self.collection.query(**kwargs)
        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}", exc_info=True)
            return []

        hits: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return hits

        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for idx in range(len(ids)):
            dist = distances[idx] if idx < len(distances) else 1.0
            # For cosine distance, similarity = 1.0 - distance
            similarity = max(0.0, 1.0 - dist)
            hits.append({
                "id": ids[idx],
                "text": docs[idx] if idx < len(docs) else "",
                "metadata": metas[idx] if idx < len(metas) else {},
                "score": round(similarity, 4),
                "distance": round(dist, 4)
            })

        return hits

    def get_stats(self) -> Dict[str, Any]:
        """Return collection stats."""
        total = self.count()
        return {
            "collection_name": self.COLLECTION_NAME,
            "total_documents": total,
            "persist_dir": str(self.persist_dir)
        }
