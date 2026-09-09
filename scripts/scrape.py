#!/usr/bin/env python3
"""CLI script to scrape products, pages, FAQs, policies, and blogs from Surfaces Tiles UK."""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.scraper import SurfacesScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("scrape_cli")


def main():
    logger.info("Starting manual scrape of Surfaces Tiles UK (https://surfacestiles.co.uk)...")
    scraper = SurfacesScraper()
    result = scraper.run()

    counts = result.get("counts", {})
    logger.info("Scraping finished successfully!")
    logger.info(f"Products scraped:    {counts.get('products', 0)}")
    logger.info(f"Pages/Policies:      {counts.get('pages', 0)}")
    logger.info(f"Blog articles:       {counts.get('blogs', 0)}")
    logger.info(f"Collections:         {counts.get('collections', 0)}")
    logger.info(f"Total items saved:   {counts.get('total', 0)}")
    logger.info(f"Raw data location:   {result.get('output_directory')}")


if __name__ == "__main__":
    main()
