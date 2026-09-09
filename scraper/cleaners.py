import re
import html
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup


def clean_html_text(raw_html: str) -> str:
    """Clean HTML content into human-readable plain text, removing scripts,

    styles, and excess whitespace while preserving paragraph structure.
    """
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove script, style, and metadata elements
    for tag in soup(["script", "style", "noscript", "svg", "button", "iframe"]):
        tag.decompose()

    # Replace block level elements with newlines
    for tag in soup(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br"]):
        tag.insert_after("\n")

    text = soup.get_text()
    text = html.unescape(text)

    # Normalize whitespace: remove redundant horizontal whitespace and limit newlines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join([line for line in lines if line])
    # Collapse multiple consecutive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_specifications_table(soup_or_html: Any) -> Dict[str, str]:
    """Extract key-value specifications from HTML tables, definition lists,

    or known specification containers.
    """
    specs: Dict[str, str] = {}
    if isinstance(soup_or_html, str):
        soup = BeautifulSoup(soup_or_html, "html.parser")
    else:
        soup = soup_or_html

    if not soup:
        return specs

    # Look for tables (like product-specifications or standard tables)
    tables = soup.find_all(["table", "dl"])
    for table in tables:
        # Table rows
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = clean_html_text(str(cells[0])).rstrip(":").strip()
                val = clean_html_text(str(cells[1])).strip()
                if key and val and len(key) < 50:
                    specs[key] = val

        # Definition lists
        dts = table.find_all("dt")
        dds = table.find_all("dd")
        if len(dts) == len(dds):
            for dt, dd in zip(dts, dds):
                k = clean_html_text(str(dt)).rstrip(":").strip()
                v = clean_html_text(str(dd)).strip()
                if k and v:
                    specs[k] = v

    return specs


def extract_dimensions(text: str) -> Optional[str]:
    """Extract tile dimensions (e.g., '30x60 CM', '60x120 CM', '600x600 mm') from text."""
    pattern = r"\b(\d{2,4}\s*[xX*×]\s*\d{2,4}\s*(?:cm|mm)?)\b"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def extract_finish(text: str) -> Optional[str]:
    """Detect common tile finishes in text."""
    finishes = [
        "Polished",
        "Matt",
        "Matte",
        "Lappato",
        "Carving",
        "Satin",
        "Glossy",
        "Textured",
        "Sugar",
        "Rustic",
        "Grip",
        "Anti-slip"
    ]
    found = []
    text_lower = text.lower()
    for f in finishes:
        if re.search(rf"\b{re.escape(f.lower())}\b", text_lower):
            found.append(f)
    return ", ".join(found) if found else None


def extract_material(text: str) -> Optional[str]:
    """Detect tile material from text."""
    materials = ["Porcelain", "Ceramic", "Glass", "Marble", "Stone", "SPC", "Vinyl"]
    for m in materials:
        if re.search(rf"\b{re.escape(m.lower())}\b", text, re.IGNORECASE):
            return m
    return "Porcelain"  # default standard for Surfaces Tiles UK


def extract_color(text: str) -> Optional[str]:
    """Detect common colors from text."""
    colors = [
        "White", "Grey", "Gray", "Black", "Beige", "Cream", "Ivory",
        "Blue", "Green", "Brown", "Gold", "Silver", "Anthracite",
        "Charcoal", "Calacatta", "Statuario", "Carrara", "Travertine"
    ]
    found = []
    text_lower = text.lower()
    for c in colors:
        if re.search(rf"\b{re.escape(c.lower())}\b", text_lower):
            found.append(c)
    return ", ".join(found) if found else None
