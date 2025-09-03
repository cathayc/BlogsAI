"""Worker thread for scraping tasks."""

import sys
import time
from pathlib import Path
from .base_worker import BaseWorker

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.scrapers.manager import ScraperManager


class ScrapingWorker(BaseWorker):
    """Worker for scraping news from agencies."""

    def execute_task(self):
        """Execute the scraping task."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info("ScrapingWorker.execute_task started")

        self.progress.emit("Initializing scraper manager...")
        manager = ScraperManager()
        logger.info("ScraperManager created successfully")

        try:
            start_date = self.kwargs["start_date"]
            end_date = self.kwargs["end_date"]
            agencies = self.kwargs["agencies"]

            logger.info(
                f"About to scrape from {start_date} to {end_date} for agencies: {agencies}"
            )
            self.progress.emit(f"Scraping from {start_date} to {end_date}...")

            # Create progress callback
            progress_callback = lambda msg: self.progress.emit(msg)

            if agencies == "all":
                logger.info("Calling scrape_all_sources_date_range")
                result = manager.scrape_all_sources_date_range(
                    start_date, end_date, progress_callback=progress_callback
                )
            else:
                # For specific agencies, use the new filtering method
                logger.info(
                    f"Calling scrape_specific_agencies_date_range for agencies: {agencies}"
                )
                # Convert single agency string to list
                agency_list = [agencies] if isinstance(agencies, str) else agencies
                result = manager.scrape_specific_agencies_date_range(
                    agency_list,
                    start_date,
                    end_date,
                    progress_callback=progress_callback,
                )

            logger.info(f"Scraping completed with result: {result}")
            self.progress.emit("Scraping completed!")
            return result

        except Exception as e:
            logger.error(f"Exception in execute_task: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        finally:
            # Explicitly close all scrapers to prevent __del__ issues
            logger.info("Closing all scrapers")
            if hasattr(manager, "close_all_scrapers"):
                manager.close_all_scrapers()
            logger.info("ScrapingWorker.execute_task finished")


class URLScrapingWorker(BaseWorker):
    """Worker for scraping content from a single URL."""

    def execute_task(self):
        """Execute the URL scraping task."""
        from blogsai.scrapers.url_scraper import URLScraper
        from blogsai.core import config

        self.progress.emit("Initializing URL scraper...")
        url = self.kwargs["url"]

        # Initialize the URL scraper
        scraper = URLScraper(config.scraping)

        self.progress.emit(f"Scraping content from: {url}")

        # Scrape the URL
        result = scraper.scrape_url(url)

        if result["success"]:
            self.progress.emit("Content scraped successfully! Parsing with AI...")
            time.sleep(1)  # Brief pause for UI feedback
            self.progress.emit("Article saved to database!")
        else:
            self.progress.emit(
                f"Scraping failed: {result.get('error', 'Unknown error')}"
            )

        return result
