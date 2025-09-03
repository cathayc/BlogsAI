"""Base scraper classes and utilities."""

import time
import requests
import hashlib

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from ..config.config import SourceConfig, ScrapingConfig


class BaseScraper:
    def __init__(self, source_config: SourceConfig, scraping_config: ScrapingConfig):
        self.source_config = source_config
        self.scraping_config = scraping_config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": scraping_config.user_agent})
        self.db_session = None

    def scrape_recent(self, days_back: int = 1):
        raise NotImplementedError

    def _make_request(self, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited HTTP request."""
        response = None
        for attempt in range(self.scraping_config.max_retries):
            try:
                response = self.session.get(
                    url, timeout=self.scraping_config.timeout, **kwargs
                )
                response.raise_for_status()

                # Rate limiting
                if attempt < self.scraping_config.max_retries - 1:
                    time.sleep(self.scraping_config.delay_between_requests)

                return response

            except requests.RequestException as e:
                if attempt == self.scraping_config.max_retries - 1:
                    raise e
                time.sleep(2**attempt)  # Exponential backoff

        return response

    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, "html.parser")

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        return " ".join(text.strip().split())

    def _resolve_url(self, url: str) -> str:
        """Resolve relative URLs to absolute URLs."""
        if url.startswith("http"):
            return url
        return urljoin(self.source_config.base_url, url)

    def _is_recent(self, published_date: datetime, days_back: int) -> bool:
        """Check if an article is within the lookback period."""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        return published_date >= cutoff_date

    def _generate_title_hash(self, title: str) -> str:
        """Generate a unique hash for the article title."""
        # Normalize title: strip whitespace, convert to lowercase
        normalized_title = title.strip().lower()
        return hashlib.sha256(normalized_title.encode("utf-8")).hexdigest()

    def _article_exists_by_title(self, title: str) -> bool:
        """Check if an article with this title already exists in the database."""
        if not self.db_session:
            return False

        try:
            from ..database.models import Article as DBArticle

            # Check if article exists by exact title match
            existing = (
                self.db_session.query(DBArticle)
                .filter(DBArticle.title == title.strip())
                .first()
            )

            return existing is not None

        except Exception as e:
            print(f"Error checking article existence: {e}")
            return False
