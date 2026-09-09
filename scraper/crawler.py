import time
import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Set, Optional
from bs4 import BeautifulSoup

from config.settings import settings
from scraper.cleaners import (
    clean_html_text,
    extract_specifications_table,
    extract_dimensions,
    extract_finish,
    extract_material,
    extract_color
)

logger = logging.getLogger(__name__)


class WebsiteCrawler:
    """Crawls Surfaces Tiles UK website for products, pages, FAQs, policies,

    blogs, and categories.
    """

    def __init__(
        self,
        base_url: str = settings.base_url,
        timeout: int = settings.request_timeout,
        user_agent: str = settings.user_agent,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })
        self.visited_urls: Set[str] = set()

    def get(self, url: str) -> Optional[requests.Response]:
        """Make safe GET request with error handling and retry."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp
            logger.warning(f"Failed to fetch {url}, status code: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
        return None

    def crawl_all_products_json(self) -> List[Dict[str, Any]]:
        """Fetch all products using Shopify's official products.json endpoint.

        This provides clean, complete, structured data for all products.
        """
        products = []
        page = 1
        limit = 250

        logger.info("Fetching products from Shopify JSON endpoint...")
        while True:
            url = f"{self.base_url}/products.json?limit={limit}&page={page}"
            resp = self.get(url)
            if not resp:
                break
            try:
                data = resp.json()
                page_products = data.get("products", [])
                if not page_products:
                    break

                for p in page_products:
                    handle = p.get("handle", "")
                    product_url = f"{self.base_url}/products/{handle}"
                    title = p.get("title", "")
                    raw_body = p.get("body_html", "") or ""
                    cleaned_body = clean_html_text(raw_body)
                    specs = extract_specifications_table(raw_body)

                    # Extract variants info
                    variants = p.get("variants", [])
                    prices = [float(v.get("price", 0)) for v in variants if v.get("price")]
                    min_price = min(prices) if prices else 0.0
                    max_price = max(prices) if prices else 0.0
                    price_str = f"£{min_price:.2f}" if min_price == max_price else f"£{min_price:.2f} - £{max_price:.2f}"

                    skus = [v.get("sku") for v in variants if v.get("sku")]
                    availability = any(v.get("available", False) for v in variants)

                    # Extract sizes, finish, color, material
                    options = p.get("options", [])
                    option_values = []
                    for opt in options:
                        option_values.extend(opt.get("values", []))

                    combined_text = f"{title} {' '.join(option_values)} {cleaned_body}"
                    dimensions = extract_dimensions(combined_text)
                    finish = extract_finish(combined_text)
                    material = extract_material(combined_text)
                    color = extract_color(combined_text)

                    # Categorization heuristics
                    category = p.get("product_type", "").strip()
                    if not category:
                        tags = [t.lower() for t in p.get("tags", [])]
                        title_lower = title.lower()
                        if "bathroom" in title_lower or "bathroom" in tags:
                            category = "Bathroom Tiles"
                        elif "kitchen" in title_lower or "kitchen" in tags:
                            category = "Kitchen Tiles"
                        elif "floor" in title_lower or "floor" in tags:
                            category = "Floor Tiles"
                        elif "wall" in title_lower or "wall" in tags:
                            category = "Wall Tiles"
                        elif "outdoor" in title_lower or "outdoor" in tags:
                            category = "Outdoor Tiles"
                        elif "spc" in title_lower or "spc" in tags or "flooring" in title_lower:
                            category = "SPC Flooring"
                        elif "glass" in title_lower or "glass" in tags:
                            category = "Glass Tiles"
                        else:
                            category = "Tiles"

                    product_item = {
                        "id": str(p.get("id")),
                        "title": title,
                        "handle": handle,
                        "url": product_url,
                        "category": category,
                        "tags": p.get("tags", []),
                        "price": price_str,
                        "min_price": min_price,
                        "max_price": max_price,
                        "available": availability,
                        "sku": skus[0] if skus else "",
                        "all_skus": skus,
                        "variants": [
                            {
                                "id": str(v.get("id")),
                                "title": v.get("title"),
                                "price": f"£{float(v.get('price', 0)):.2f}" if v.get("price") else "N/A",
                                "compare_at_price": f"£{float(v.get('compare_at_price', 0)):.2f}" if v.get("compare_at_price") else None,
                                "sku": v.get("sku"),
                                "available": v.get("available", False)
                            }
                            for v in variants
                        ],
                        "dimensions": dimensions,
                        "finish": finish,
                        "material": material,
                        "color": color,
                        "specifications": specs,
                        "description": cleaned_body,
                        "content_type": "product",
                        "images": [img.get("src") for img in p.get("images", []) if img.get("src")]
                    }
                    products.append(product_item)

                logger.info(f"Loaded page {page}: {len(page_products)} products (total: {len(products)})")
                page += 1
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"Error parsing products JSON from {url}: {e}")
                break

        return products

    def fetch_sitemap_urls(self) -> Dict[str, List[str]]:
        """Discover URLs from sitemaps."""
        sitemap_types = {
            "pages": [],
            "blogs": [],
            "collections": [],
            "products": []
        }

        index_url = f"{self.base_url}/sitemap.xml"
        resp = self.get(index_url)
        if not resp:
            return sitemap_types

        try:
            root = ET.fromstring(resp.content)
            namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            sub_sitemaps = [elem.text.strip() for elem in root.findall(".//ns:loc", namespace) if elem.text]

            for s_url in sub_sitemaps:
                sub_resp = self.get(s_url)
                if not sub_resp:
                    continue
                sub_root = ET.fromstring(sub_resp.content)
                locs = [elem.text.strip() for elem in sub_root.findall(".//ns:loc", namespace) if elem.text]

                if "pages" in s_url:
                    sitemap_types["pages"].extend(locs)
                elif "blogs" in s_url:
                    sitemap_types["blogs"].extend(locs)
                elif "collections" in s_url:
                    sitemap_types["collections"].extend(locs)
                elif "products" in s_url:
                    sitemap_types["products"].extend(locs)

        except Exception as e:
            logger.error(f"Error parsing sitemaps: {e}")

        return sitemap_types

    def crawl_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl an individual HTML page (e.g. delivery, FAQ, returns, blog)."""
        if url in self.visited_urls:
            return None
        self.visited_urls.add(url)

        resp = self.get(url)
        if not resp:
            return None

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            title = title.replace("– Surfaces Tiles", "").replace("- Surfaces Tiles", "").strip()

            # Remove header, footer, navigation elements
            for el in soup(["header", "footer", "nav", "style", "script", "noscript", "svg", "form"]):
                el.decompose()

            # Main content search
            main_elem = (
                soup.find("main")
                or soup.find(id="MainContent")
                or soup.find(class_="main-content")
                or soup.find("article")
                or soup.body
            )

            if not main_elem:
                return None

            clean_text = clean_html_text(str(main_elem))

            # Determine content type and category
            content_type = "page"
            category = "General"
            url_lower = url.lower()

            if "delivery" in url_lower:
                content_type = "policy"
                category = "Delivery & Shipping"
            elif "return" in url_lower or "cancellation" in url_lower:
                content_type = "policy"
                category = "Returns & Cancellations"
            elif "faq" in url_lower:
                content_type = "faq"
                category = "FAQs"
            elif "trade-account" in url_lower:
                content_type = "info"
                category = "Trade Accounts"
            elif "contact" in url_lower:
                content_type = "info"
                category = "Contact Us"
            elif "about" in url_lower:
                content_type = "info"
                category = "About Us"
            elif "/blogs/" in url_lower:
                content_type = "blog"
                category = "Blog & Guides"
            elif "/collections/" in url_lower:
                content_type = "collection"
                category = "Collections"

            return {
                "url": url,
                "title": title,
                "content_type": content_type,
                "category": category,
                "raw_text": clean_text
            }
        except Exception as e:
            logger.error(f"Error crawling page {url}: {e}")
            return None
