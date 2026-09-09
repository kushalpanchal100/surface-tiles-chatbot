import pytest
import shutil
from pathlib import Path
from rag.vector_store import SurfacesVectorStore
from rag.embeddings import GeminiEmbeddingService


@pytest.fixture
def temp_vector_store(tmp_path):
    store = SurfacesVectorStore(persist_dir=tmp_path / "test_chroma")
    yield store
    shutil.rmtree(tmp_path / "test_chroma", ignore_errors=True)


def test_vector_store_crud_and_search(temp_vector_store):
    chunks = [
        {
            "id": "prod_1",
            "text": "Snow Sheen 30x60 CM Polished Porcelain Marble Look Wall and Floor Tile",
            "metadata": {
                "title": "Snow Sheen 30x60",
                "url": "https://surfacestiles.co.uk/products/snow-sheen",
                "category": "Floor Tiles",
                "content_type": "product"
            }
        },
        {
            "id": "policy_1",
            "text": "Delivery Information: Pallet delivery for bulk orders, kerbside service across the UK.",
            "metadata": {
                "title": "Delivery Policy",
                "url": "https://surfacestiles.co.uk/pages/delivery",
                "category": "Delivery",
                "content_type": "policy"
            }
        }
    ]

    emb_service = GeminiEmbeddingService(mock_mode=True)
    embeddings = emb_service.embed_batch([c["text"] for c in chunks])

    temp_vector_store.reset()
    count = temp_vector_store.add_documents(chunks=chunks, embeddings=embeddings)
    assert count == 2
    assert temp_vector_store.count() == 2

    # Query search
    query_emb = emb_service.embed_text("Snow Sheen marble floor tile")
    results = temp_vector_store.search(query_emb, n_results=2)
    assert len(results) >= 1
    assert "Snow Sheen" in results[0]["text"]

    # Filtered search
    policy_results = temp_vector_store.search(
        query_emb,
        n_results=2,
        where_filter={"content_type": "policy"}
    )
    assert len(policy_results) == 1
    assert policy_results[0]["metadata"]["content_type"] == "policy"
