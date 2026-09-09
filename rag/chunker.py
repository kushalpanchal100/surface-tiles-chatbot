import re
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)


class ContentChunker:
    """Transforms raw scraped website data into semantically dense chunks

    enriched with metadata optimized for RAG retrieval.
    """

    def __init__(
        self,
        raw_dir: Path = settings.data_raw_dir,
        processed_dir: Path = settings.data_processed_dir,
        max_chunk_chars: int = 1200,
        chunk_overlap_chars: int = 150
    ):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.max_chunk_chars = max_chunk_chars
        self.chunk_overlap_chars = chunk_overlap_chars
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def process_all(self) -> List[Dict[str, Any]]:
        """Process all raw datasets into unified chunks with metadata."""
        chunks: List[Dict[str, Any]] = []

        # 1. Process Products
        products_file = self.raw_dir / "products.json"
        if products_file.exists():
            with open(products_file, "r", encoding="utf-8") as f:
                products = json.load(f)
            prod_chunks = self.chunk_products(products)
            chunks.extend(prod_chunks)
            logger.info(f"Chunked {len(products)} products into {len(prod_chunks)} chunks.")

        # 2. Process Informational & Policy Pages
        pages_file = self.raw_dir / "pages.json"
        if pages_file.exists():
            with open(pages_file, "r", encoding="utf-8") as f:
                pages = json.load(f)
            page_chunks = self.chunk_pages(pages)
            chunks.extend(page_chunks)
            logger.info(f"Chunked {len(pages)} pages into {len(page_chunks)} chunks.")

        # 3. Process Blogs
        blogs_file = self.raw_dir / "blogs.json"
        if blogs_file.exists():
            with open(blogs_file, "r", encoding="utf-8") as f:
                blogs = json.load(f)
            blog_chunks = self.chunk_blogs(blogs)
            chunks.extend(blog_chunks)
            logger.info(f"Chunked {len(blogs)} blogs into {len(blog_chunks)} chunks.")

        # 4. Process Collections
        collections_file = self.raw_dir / "collections.json"
        if collections_file.exists():
            with open(collections_file, "r", encoding="utf-8") as f:
                collections = json.load(f)
            col_chunks = self.chunk_collections(collections)
            chunks.extend(col_chunks)
            logger.info(f"Chunked {len(collections)} collections into {len(col_chunks)} chunks.")

        # Save processed chunks
        output_file = self.processed_dir / "chunks.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved total {len(chunks)} processed chunks to {output_file}")
        return chunks

    def _load_collection_mapping(self) -> Dict[str, List[str]]:
        """Map product titles (normalized lowercase) to collections from collections.json."""
        mapping: Dict[str, List[str]] = {}
        cols_file = self.raw_dir / "collections.json"
        if not cols_file.exists():
            return mapping

        try:
            with open(cols_file, "r", encoding="utf-8") as f:
                collections = json.load(f)

            for col in collections:
                col_name = (col.get("title") or "").strip()
                if not col_name or col_name in ["All Collection Tiles", "PRODUCTS ON SALE", "New Arrivals"]:
                    continue
                raw_text = col.get("raw_text", "")
                for line in raw_text.split("\n"):
                    clean = line.strip().lower()
                    if clean and len(clean) > 5:
                        if clean not in mapping:
                            mapping[clean] = []
                        if col_name not in mapping[clean]:
                            mapping[clean].append(col_name)
        except Exception as e:
            logger.warning(f"Could not load collection mapping: {e}")

        return mapping

    def chunk_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create dense product chunks with specifications, collection memberships, and room suitability."""
        collection_map = self._load_collection_mapping()
        chunks = []

        for idx, p in enumerate(products):
            title = p.get("title") or ""
            url = p.get("url") or ""
            category = p.get("category") or "Tiles"
            price = p.get("price") or "N/A"
            dims = p.get("dimensions") or "See specifications"
            finish = p.get("finish") or "See specifications"
            material = p.get("material") or "Porcelain"
            color = p.get("color") or "See description"
            sku = p.get("sku") or "N/A"
            availability = "In Stock / Available" if p.get("available") else "Out of Stock"
            desc = p.get("description") or ""
            specs = p.get("specifications") or {}
            tags = p.get("tags") or []

            # Match collections from website
            title_clean = title.strip().lower()
            matched_cols = list(collection_map.get(title_clean, []))

            # Deduce room suitability and specific applications
            tags_str = " ".join(str(t) for t in tags)
            full_context_str = f"{title} {category} {tags_str} {desc}".lower()
            is_outdoor = "outdoor" in full_context_str or "2cm" in full_context_str or "Outdoor Tiles" in matched_cols
            is_spc = "spc" in full_context_str or "vinyl" in full_context_str or "flooring" in title_clean or "SPC FLOORING" in matched_cols

            if is_outdoor:
                if "Outdoor Tiles" not in matched_cols:
                    matched_cols.append("Outdoor Tiles")
                category = "Outdoor Tiles"
                suitability = "Outdoor Patios, Terraces, Balconies, Garden Pathways, Exterior Living Spaces (2cm Porcelain Slabs - Not for indoor bathrooms)"
            elif is_spc:
                if "SPC FLOORING" not in matched_cols:
                    matched_cols.append("SPC FLOORING")
                category = "SPC Flooring"
                suitability = "Indoor Living Areas, Bedrooms, Hallways, Commercial Spaces (Waterproof Rigid Core SPC Vinyl Flooring)"
            else:
                # Indoor porcelain / ceramic tiles
                is_pure_wall = "wall tiles" in full_context_str and "floor" not in full_context_str and "30x60" in full_context_str and "feature" in full_context_str
                if is_pure_wall:
                    if "Wall Tiles" not in matched_cols:
                        matched_cols.append("Wall Tiles")
                    category = "Wall Tiles"
                    suitability = "Bathroom Walls, Shower Walls, Kitchen Splashbacks, Feature Walls (Indoor Wall Tiles)"
                else:
                    # Versatile porcelain tiles (suitable for indoor floors and walls in bathrooms, kitchens, hallways, etc.)
                    for c in ["Floor Tiles", "Bathroom Tiles", "Kitchen Tiles"]:
                        if c not in matched_cols:
                            matched_cols.append(c)
                    if category in ["Tiles", ""]:
                        category = "Floor & Wall Tiles"
                    suitability = "Bathroom Floor & Wall, Kitchen Floor & Wall, Living Areas, Hallways (Indoor Porcelain Floor & Wall Tiles)"

            cols_str = ", ".join(matched_cols) if matched_cols else category

            specs_str = "\n".join([f"- {k}: {v}" for k, v in specs.items()]) if specs else ""

            header = (
                f"Product: {title}\n"
                f"Category: {category}\n"
                f"Collections: {cols_str}\n"
                f"Suitable Rooms & Surfaces: {suitability}\n"
                f"Price: {price}\n"
                f"Dimensions / Size: {dims}\n"
                f"Finish: {finish}\n"
                f"Material: {material}\n"
                f"Colour: {color}\n"
                f"SKU: {sku}\n"
                f"Availability: {availability}\n"
                f"Product Link: {url}\n"
            )

            body_content = f"Description:\n{desc}\n"
            if specs_str:
                body_content += f"\nTechnical Specifications:\n{specs_str}\n"

            # Check if variants have different prices or sizes
            variants = p.get("variants") or []
            if len(variants) > 1:
                var_str = "\nAvailable Options / Variants:\n" + "\n".join([
                    f"- {v.get('title', 'Option')}: {v.get('price', 'N/A')} (SKU: {v.get('sku', 'N/A')})"
                    for v in variants if isinstance(v, dict)
                ])
                body_content += f"{var_str}\n"
            full_text = f"{header}\n{body_content}".strip()
            prod_identifier = str(p.get("id") or p.get("handle") or f"idx_{idx}")
            chunk = {
                "id": f"prod_{prod_identifier}",
                "text": full_text,
                "metadata": {
                    "url": url,
                    "title": title,
                    "product_name": title,
                    "category": category,
                    "collections": cols_str,
                    "suitability": suitability,
                    "is_outdoor": is_outdoor,
                    "is_spc": is_spc,
                    "content_type": "product",
                    "price": str(price),
                    "dimensions": str(dims),
                    "finish": str(finish),
                    "material": str(material),
                    "color": str(color),
                    "sku": str(sku),
                    "available": bool(p.get("available", True))
                }
            }
            chunks.append(chunk)

        return chunks

    def chunk_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split content and policy pages into contextual sections or Q&A chunks."""
        chunks = []
        for idx, page in enumerate(pages):
            url = page.get("url", "")
            title = page.get("title", "")
            category = page.get("category", "General")
            content_type = page.get("content_type", "page")
            raw_text = page.get("raw_text", "")

            # If it's an FAQ page, extract discrete questions and answers
            if content_type == "faq" or "faq" in url.lower():
                faq_chunks = self._chunk_faqs(raw_text, url, title, category)
                chunks.extend(faq_chunks)
                continue

            # For policy or general pages, break into meaningful paragraphs/sections
            sections = self._split_into_sections(raw_text)
            for s_idx, section in enumerate(sections):
                chunk_id = f"page_{idx}_{s_idx}"
                section_text = f"Page: {title}\nCategory: {category}\nURL: {url}\n\n{section}"

                chunk = {
                    "id": chunk_id,
                    "text": section_text,
                    "metadata": {
                        "url": url,
                        "title": title,
                        "product_name": "",
                        "category": category,
                        "content_type": content_type,
                        "price": "",
                        "dimensions": "",
                        "finish": "",
                        "material": "",
                        "color": "",
                        "sku": "",
                        "available": True
                    }
                }
                chunks.append(chunk)

        return chunks

    def chunk_blogs(self, blogs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunk blog articles preserving context and attribution."""
        chunks = []
        for idx, blog in enumerate(blogs):
            url = blog.get("url", "")
            title = blog.get("title", "")
            category = blog.get("category", "Blog & Guides")
            raw_text = blog.get("raw_text", "")

            sections = self._split_into_sections(raw_text)
            for s_idx, section in enumerate(sections):
                chunk_id = f"blog_{idx}_{s_idx}"
                section_text = f"Article: {title}\nTopic: {category}\nURL: {url}\n\n{section}"

                chunk = {
                    "id": chunk_id,
                    "text": section_text,
                    "metadata": {
                        "url": url,
                        "title": title,
                        "product_name": "",
                        "category": category,
                        "content_type": "blog",
                        "price": "",
                        "dimensions": "",
                        "finish": "",
                        "material": "",
                        "color": "",
                        "sku": "",
                        "available": True
                    }
                }
                chunks.append(chunk)

        return chunks

    def chunk_collections(self, collections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create structured overview chunks for store collections."""
        chunks = []
        for idx, c in enumerate(collections):
            title = c.get("title") or ""
            url = c.get("url") or ""
            raw_text = c.get("raw_text") or ""
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            snippet = "\n".join(lines[:20]) if lines else ""
            slug = url.rstrip("/").split("/")[-1] if url else f"idx_{idx}"

            chunk = {
                "id": f"col_{slug}",
                "text": f"Collection: {title}\nURL: {url}\nOverview:\n{snippet}",
                "metadata": {
                    "url": url,
                    "title": f"Collection: {title}",
                    "product_name": "",
                    "category": "Collection",
                    "collections": title,
                    "suitability": title,
                    "is_outdoor": "outdoor" in title.lower(),
                    "is_spc": "spc" in title.lower(),
                    "content_type": "collection",
                    "price": "",
                    "dimensions": "",
                    "finish": "",
                    "material": "",
                    "color": "",
                    "sku": "",
                    "available": True
                }
            }
            chunks.append(chunk)
        return chunks

    def _chunk_faqs(self, text: str, url: str, title: str, category: str) -> List[Dict[str, Any]]:
        """Parse FAQ text into question-answer blocks."""
        chunks = []
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        current_q = None
        current_a: List[str] = []
        q_count = 0

        for line in lines:
            if "?" in line and len(line) < 150:
                # Save previous Q&A if complete
                if current_q and current_a:
                    ans_text = " ".join(current_a)
                    q_count += 1
                    chunks.append({
                        "id": f"faq_{q_count}",
                        "text": f"Frequently Asked Question: {current_q}\nAnswer: {ans_text}\nURL: {url}",
                        "metadata": {
                            "url": url,
                            "title": f"FAQ: {current_q}",
                            "product_name": "",
                            "category": category,
                            "content_type": "faq",
                            "price": "",
                            "dimensions": "",
                            "finish": "",
                            "material": "",
                            "color": "",
                            "sku": "",
                            "available": True
                        }
                    })
                current_q = line
                current_a = []
            else:
                if current_q:
                    current_a.append(line)

        # Append last Q&A
        if current_q and current_a:
            q_count += 1
            chunks.append({
                "id": f"faq_{q_count}",
                "text": f"Frequently Asked Question: {current_q}\nAnswer: {' '.join(current_a)}\nURL: {url}",
                "metadata": {
                    "url": url,
                    "title": f"FAQ: {current_q}",
                    "product_name": "",
                    "category": category,
                    "content_type": "faq",
                    "price": "",
                    "dimensions": "",
                    "finish": "",
                    "material": "",
                    "color": "",
                    "sku": "",
                    "available": True
                }
            })

        # Fallback if no specific question lines matched
        if not chunks:
            sections = self._split_into_sections(text)
            for idx, sec in enumerate(sections):
                chunks.append({
                    "id": f"faq_sec_{idx}",
                    "text": f"FAQ Information: {title}\nURL: {url}\n\n{sec}",
                    "metadata": {
                        "url": url,
                        "title": title,
                        "product_name": "",
                        "category": category,
                        "content_type": "faq",
                        "price": "",
                        "dimensions": "",
                        "finish": "",
                        "material": "",
                        "color": "",
                        "sku": "",
                        "available": True
                    }
                })

        return chunks

    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into chunks of roughly max_chunk_chars, respecting paragraph breaks."""
        paragraphs = text.split("\n\n")
        sections = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue

            if current_len + len(p) > self.max_chunk_chars and current_chunk:
                sections.append("\n\n".join(current_chunk))
                current_chunk = [p]
                current_len = len(p)
            else:
                current_chunk.append(p)
                current_len += len(p) + 2

        if current_chunk:
            sections.append("\n\n".join(current_chunk))

        return [s for s in sections if len(s) > 30]
