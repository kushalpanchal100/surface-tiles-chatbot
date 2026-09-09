import pytest
from scraper.cleaners import (
    clean_html_text,
    extract_specifications_table,
    extract_dimensions,
    extract_finish,
    extract_material,
    extract_color
)


def test_clean_html_text():
    html = "<div><p>Snow Sheen <b>Polished Porcelain</b></p><script>alert('bad');</script><p>Price: £19.99</p></div>"
    cleaned = clean_html_text(html)
    assert "Snow Sheen" in cleaned
    assert "Polished Porcelain" in cleaned
    assert "Price: £19.99" in cleaned
    assert "alert" not in cleaned
    assert "<p>" not in cleaned


def test_extract_specifications_table():
    html_table = """
    <table class="product-specifications">
        <tr><th>Size</th><td>60x120 CM</td></tr>
        <tr><th>Finish</th><td>Polished</td></tr>
        <tr><th>Material</th><td>Porcelain</td></tr>
        <tr><th>Suitability</th><td>Wall & Floor</td></tr>
    </table>
    """
    specs = extract_specifications_table(html_table)
    assert specs.get("Size") == "60x120 CM"
    assert specs.get("Finish") == "Polished"
    assert specs.get("Material") == "Porcelain"
    assert specs.get("Suitability") == "Wall & Floor"


def test_extract_dimensions():
    assert extract_dimensions("Snow Sheen 30x60 CM Polished Tile") == "30X60 CM"
    assert extract_dimensions("Grande Marble 60x120 CM") == "60X120 CM"
    assert extract_dimensions("Outdoor slab 600x600 mm") == "600X600 MM"


def test_extract_finish():
    assert "Polished" in extract_finish("High gloss polished marble look")
    assert "Matt" in extract_finish("Contemporary Matt Grey Bathroom Tile")


def test_extract_material():
    assert extract_material("Luxury porcelain slabs") == "Porcelain"
    assert extract_material("SPC vinyl click flooring") == "SPC"


def test_extract_color():
    colors = extract_color("Stunning Calacatta Gold with subtle grey veins")
    assert "Gold" in colors
    assert "Grey" in colors
