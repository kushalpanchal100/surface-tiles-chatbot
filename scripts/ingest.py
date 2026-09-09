#!/usr/bin/env python3
"""CLI script to process raw scraped data into RAG chunks and index them into ChromaDB."""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.chunker import ContentChunker
from rag.embeddings import GeminiEmbeddingService
from rag.vector_store import SurfacesVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ingest_cli")


def main():
    logger.info("Starting ingestion pipeline for Surfaces Tiles UK knowledge base...")

    # 1. Chunking
    chunker = ContentChunker()
    chunks = chunker.process_all()

    if not chunks:
        logger.error("No chunks were generated. Please run `python scripts/scrape.py` first to collect raw data.")
        sys.exit(1)

    logger.info(f"Total chunks to embed and index: {len(chunks)}")

    # 2. Embedding
    logger.info("Generating embeddings using Gemini embedding model (gemini-embedding-001)...")
    texts = [c["text"] for c in chunks]
    embedding_service = GeminiEmbeddingService()
    embeddings = embedding_service.embed_batch(texts)

    # 3. Vector Database Indexing
    logger.info("Indexing vectors into ChromaDB...")
    vector_store = SurfacesVectorStore()
    vector_store.reset()
    vector_store.add_documents(chunks=chunks, embeddings=embeddings)

    total_indexed = vector_store.count()
    logger.info(f"Ingestion complete! Successfully indexed {total_indexed} chunks in ChromaDB.")
    logger.info(f"Vector database location: {vector_store.persist_dir}")


if __name__ == "__main__":
    main()
