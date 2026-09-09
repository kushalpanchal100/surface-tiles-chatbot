import pytest
from rag.chunker import ContentChunker


def test_chunk_products():
    chunker = ContentChunker()
    products = [
        {
            "id": "12345",
            "title": "Snow Sheen 30x60 CM Polished Porcelain",
            "handle": "snow-sheen-30x60",
            "url": "https://surfacestiles.co.uk/products/snow-sheen-30x60",
            "category": "Bathroom Tiles",
            "price": "£19.99",
            "available": True,
            "sku": "POL3060A6",
            "dimensions": "30X60 CM",
            "finish": "Polished",
            "material": "Porcelain",
            "color": "White",
            "description": "Luxurious marble-inspired porcelain tiles for wall and floor.",
            "specifications": {"Size": "30x60 CM", "Finish": "Polished"}
        }
    ]
    chunks = chunker.chunk_products(products)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["id"] == "prod_12345"
    assert "Snow Sheen 30x60 CM Polished Porcelain" in chunk["text"]
    assert "Price: £19.99" in chunk["text"]
    assert chunk["metadata"]["category"] == "Bathroom Tiles"
    assert chunk["metadata"]["content_type"] == "product"
    assert chunk["metadata"]["url"] == "https://surfacestiles.co.uk/products/snow-sheen-30x60"


def test_chunk_faqs():
    chunker = ContentChunker()
    faq_text = """
    Do you offer samples of your porcelain tiles?
    Yes, we offer 100% free samples of our porcelain tiles for wall tiles, floor tiles, kitchen tiles, and bathroom tiles.
    Do the website prices include VAT?
    Yes, all prices displayed on our website include VAT at the standard UK rate.
    """
    chunks = chunker._chunk_faqs(faq_text, "https://surfacestiles.co.uk/pages/faqs", "FAQs", "FAQs")
    assert len(chunks) == 2
    assert any("free samples" in c["text"].lower() for c in chunks)
    assert any("vat" in c["text"].lower() for c in chunks)
