import json
import logging
from typing import Dict, Any, List
from pathlib import Path

from config.settings import settings
from scraper.crawler import WebsiteCrawler

logger = logging.getLogger(__name__)


class SurfacesScraper:
    """Orchestrates scraping of all products, policies, FAQs, blogs, and collections

    from Surfaces Tiles UK.
    """

    def __init__(self, raw_data_dir: Path = settings.data_raw_dir):
        self.raw_data_dir = raw_data_dir
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.crawler = WebsiteCrawler()

    def run(self) -> Dict[str, Any]:
        """Execute full scrape and save structured raw JSON datasets."""
        logger.info("Starting Surfaces Tiles UK website scrape...")

        # 1. Scrape Products
        products = self.crawler.crawl_all_products_json()
        logger.info(f"Scraped {len(products)} products.")

        # 2. Discover Sitemaps
        sitemaps = self.crawler.fetch_sitemap_urls()
        page_urls = sitemaps.get("pages", [])
        blog_urls = sitemaps.get("blogs", [])
        collection_urls = sitemaps.get("collections", [])

        # Priority static pages to ensure they are always crawled
        priority_pages = [
            f"{self.crawler.base_url}/pages/delivery",
            f"{self.crawler.base_url}/pages/returns-and-cancellations-policy",
            f"{self.crawler.base_url}/pages/faqs",
            f"{self.crawler.base_url}/pages/about-us",
            f"{self.crawler.base_url}/pages/contact",
            f"{self.crawler.base_url}/pages/trade-account",
            f"{self.crawler.base_url}/pages/payment",
            f"{self.crawler.base_url}/pages/terms-and-conditions",
            f"{self.crawler.base_url}/pages/tiles-calculator",
            f"{self.crawler.base_url}/pages/catalogs",
        ]
        all_pages_to_crawl = list(dict.fromkeys(priority_pages + page_urls))

        # 3. Crawl Pages (Policies, FAQs, About, Contact)
        pages = []
        for url in all_pages_to_crawl:
            data = self.crawler.crawl_page(url)
            if data and data.get("raw_text"):
                pages.append(data)
        logger.info(f"Scraped {len(pages)} informational/policy pages.")

        # 4. Crawl Blogs
        blogs = []
        for url in blog_urls:
            data = self.crawler.crawl_page(url)
            if data and data.get("raw_text"):
                blogs.append(data)
        logger.info(f"Scraped {len(blogs)} blog articles.")

        # 5. Crawl Collections
        collections = []
        for url in collection_urls:
            data = self.crawler.crawl_page(url)
            if data and data.get("raw_text"):
                collections.append(data)
        logger.info(f"Scraped {len(collections)} collection pages.")

        # Save datasets to disk
        self._save_json("products.json", products)
        self._save_json("pages.json", pages)
        self._save_json("blogs.json", blogs)
        self._save_json("collections.json", collections)

        summary = {
            "status": "success",
            "counts": {
                "products": len(products),
                "pages": len(pages),
                "blogs": len(blogs),
                "collections": len(collections),
                "total": len(products) + len(pages) + len(blogs) + len(collections)
            },
            "output_directory": str(self.raw_data_dir)
        }
        logger.info(f"Scrape completed: {summary['counts']}")
        return summary

    def _save_json(self, filename: str, data: List[Dict[str, Any]]) -> Path:
        filepath = self.raw_data_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath
