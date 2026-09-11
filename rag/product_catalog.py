"""Product Catalog service for Surfaces Tiles UK.

Loads and indexes all scraped product data from data/raw/products.json
providing fast lookups by ID, handle, URL, and query matching, with rich
metadata for product cards (images, prices, variants, Add to Cart, Buy Now).
"""
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class ProductCatalog:
    """In-memory index and lookup service for Surfaces Tiles products."""

    _instance: Optional["ProductCatalog"] = None

    def __init__(self, products_file: Optional[Path] = None):
        self.products_file = products_file or (settings.data_raw_dir / "products.json")
        self.products: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._by_handle: Dict[str, Dict[str, Any]] = {}
        self._by_url: Dict[str, Dict[str, Any]] = {}
        self._by_title: Dict[str, Dict[str, Any]] = {}
        self.load()

    @property
    def all_products(self) -> List[Dict[str, Any]]:
        return self.products

    def get_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        return self._by_handle.get(str(handle).strip().lower())

    @classmethod
    def get_instance(cls, products_file: Optional[Path] = None) -> "ProductCatalog":
        if cls._instance is None:
            cls._instance = ProductCatalog(products_file)
        return cls._instance

    def load(self) -> None:
        """Load and index products from JSON file."""
        if not self.products_file.exists():
            logger.warning(f"Products file not found at {self.products_file}")
            return

        try:
            with open(self.products_file, "r", encoding="utf-8") as f:
                raw_products = json.load(f)

            self.products = raw_products
            self._by_id.clear()
            self._by_handle.clear()
            self._by_url.clear()
            self._by_title.clear()

            for p in raw_products:
                pid = str(p.get("id") or "").strip()
                handle = str(p.get("handle") or "").strip().lower()
                url = str(p.get("url") or "").strip()
                title = str(p.get("title") or "").strip()

                if pid:
                    self._by_id[pid] = p
                if handle:
                    self._by_handle[handle] = p
                if url:
                    self._by_url[url] = p
                    clean_url = url.rstrip("/")
                    self._by_url[clean_url] = p
                    # Also index relative path /products/{handle}
                    if "/products/" in url:
                        rel_path = "/" + url.split("surfacestiles.co.uk/")[-1].lstrip("/")
                        self._by_url[rel_path] = p
                        self._by_url[rel_path.rstrip("/")] = p

                if title:
                    norm_title = self._normalize_text(title)
                    self._by_title[norm_title] = p

            logger.info(f"Loaded {len(self.products)} products into ProductCatalog index.")
        except Exception as e:
            logger.error(f"Failed to load product catalog: {e}", exc_info=True)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

    def get_product_card(self, product_or_id: Any) -> Optional[Dict[str, Any]]:
        """Transform raw product record into a standardized product card dictionary."""
        p = None
        if isinstance(product_or_id, dict):
            p = product_or_id
        elif isinstance(product_or_id, str):
            p = self.find(product_or_id)

        if not p:
            return None

        pid = str(p.get("id") or "")
        handle = str(p.get("handle") or "")
        title = str(p.get("title") or "Surfaces Tile")
        url = str(p.get("url") or f"https://surfacestiles.co.uk/products/{handle}")

        raw_price = str(p.get("price") or "")
        if not raw_price.startswith("£") and raw_price:
            raw_price = f"£{raw_price}"
        if not raw_price:
            raw_price = "£19.99"

        price_per_m2 = f"{raw_price} / m²" if not raw_price.endswith("/ m²") and not raw_price.endswith("/m²") else raw_price

        # Primary and gallery images
        images = p.get("images") or []
        image_url = images[0] if images else ""

        variants = p.get("variants") or []
        first_variant = variants[0] if variants else {}
        variant_id = str(first_variant.get("id") or pid)

        # Checkout permalink directly adds item and navigates to Shopify checkout
        checkout_url = f"https://surfacestiles.co.uk/cart/{variant_id}:1"
        add_to_cart_url = f"https://surfacestiles.co.uk/cart/add?id={variant_id}&quantity=1"

        dims = p.get("dimensions") or ""
        finish = p.get("finish") or ""
        material = p.get("material") or "Porcelain"
        category = p.get("category") or "Floor & Wall Tiles"
        sku = p.get("sku") or (first_variant.get("sku") if first_variant else "")

        # Generate a clean 1-2 sentence description snippet
        raw_desc = p.get("description") or ""
        first_sentence = raw_desc.split(".")[0].strip() if raw_desc else ""
        if first_sentence and len(first_sentence) > 10:
            snippet = first_sentence + "."
        else:
            snippet = f"Premium {finish.lower() if finish else ''} {material.lower()} tile suitable for {category.lower()}."

        return {
            "id": pid,
            "title": title,
            "handle": handle,
            "url": url,
            "price": raw_price,
            "price_per_m2": price_per_m2,
            "image_url": image_url,
            "images": images[:4],
            "dimensions": dims,
            "finish": finish,
            "material": material,
            "category": category,
            "sku": sku,
            "available": bool(p.get("available", True)),
            "variant_id": variant_id,
            "variants": variants,
            "checkout_url": checkout_url,
            "add_to_cart_url": add_to_cart_url,
            "description_snippet": snippet
        }

    def find(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Find product by ID, handle, URL, or title."""
        if not identifier:
            return None

        ident_str = str(identifier).strip()

        # 1. Direct ID lookup
        if ident_str in self._by_id:
            return self._by_id[ident_str]

        # 2. URL lookup
        clean_url = ident_str.rstrip("/")
        if clean_url in self._by_url:
            return self._by_url[clean_url]

        # Extract handle from URL if present
        if "/products/" in ident_str:
            extracted_handle = ident_str.split("/products/")[-1].split("?")[0].rstrip("/").lower()
            if extracted_handle in self._by_handle:
                return self._by_handle[extracted_handle]

        # 3. Handle lookup
        lower_handle = ident_str.lower()
        if lower_handle in self._by_handle:
            return self._by_handle[lower_handle]

        # 4. Title lookup
        norm_title = self._normalize_text(ident_str)
        if norm_title in self._by_title:
            return self._by_title[norm_title]

        # Partial title match
        for key, prod in self._by_title.items():
            if norm_title in key or key in norm_title:
                return prod

        return None

    def search(
        self,
        query: str,
        top_k: int = 4,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search products using keyword relevance matching."""
        if not query:
            return self.get_popular_tiles(top_k=top_k)

        norm_q = self._normalize_text(query)
        words = set(norm_q.split())
        scored: List[tuple[float, Dict[str, Any]]] = []

        for p in self.products:
            score = 0.0
            title = self._normalize_text(p.get("title") or "")
            desc = self._normalize_text(p.get("description") or "")
            cat = self._normalize_text(p.get("category") or "")
            color = self._normalize_text(p.get("color") or "")
            finish = self._normalize_text(p.get("finish") or "")

            if category and category.lower() not in cat:
                continue

            # Exact phrase match in title
            if norm_q in title:
                score += 50.0

            # Word matches
            for w in words:
                if len(w) <= 2:
                    continue
                if w in title.split():
                    score += 10.0
                elif w in title:
                    score += 5.0
                if w in color:
                    score += 8.0
                if w in finish:
                    score += 6.0
                if w in cat:
                    score += 4.0
                if w in desc:
                    score += 1.0

            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [p for _, p in scored[:top_k]]

        # If too few matches, supplement with popular tiles
        if len(results) < min(top_k, 2):
            for pop in self.get_popular_tiles(top_k=top_k):
                if pop not in results:
                    results.append(pop)
                if len(results) >= top_k:
                    break

        return [card for p in results if (card := self.get_product_card(p))]

    def get_popular_tiles(self, top_k: int = 4) -> List[Dict[str, Any]]:
        """Return a curated selection of premier featured tiles."""
        preferred_handles = [
            "starlit-white-30x60-cm-polished",  # Snow Sheen Marble
            "render-grey-60x120-cm-matt-porcelain-tiles",
            "brick-effect-grey-30x60-cm-feature-wall-tiles",
            "nexo-snow-60x120-cm-matt-porcelain-tiles",
            "lorenzo-gold-60x120-cm-polished-porcelain-tiles"
        ]

        cards = []
        for handle in preferred_handles:
            p = self._by_handle.get(handle)
            if p:
                card = self.get_product_card(p)
                if card:
                    cards.append(card)
            if len(cards) >= top_k:
                break

        # If we need more, grab first available products
        if len(cards) < top_k:
            for p in self.products:
                if p.get("id") not in [c["id"] for c in cards]:
                    card = self.get_product_card(p)
                    if card:
                        cards.append(card)
                if len(cards) >= top_k:
                    break

        return cards


# Global catalog singleton instance
catalog = ProductCatalog.get_instance()


def get_product_catalog(products_file: Optional[Path] = None) -> ProductCatalog:
    """Convenience getter for singleton ProductCatalog instance."""
    return ProductCatalog.get_instance(products_file)
