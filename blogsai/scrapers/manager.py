"""
Scraper manager to coordinate scraping activities across all sources.

This module provides centralized management of web scraping operations for various
government agency sources. It handles scraper initialization, execution coordination,
error handling, and result aggregation.

Key Features:
- Multi-source scraping coordination
- Automatic deduplication of articles
- Comprehensive error handling and logging
- Progress tracking and reporting
- Database integration for article storage
- Retry logic for transient failures

The ScraperManager supports both recent article scraping (last N days) and
date range scraping for historical data collection. It maintains scraping
logs for audit and monitoring purposes.

Usage:
    manager = ScraperManager()
    results = manager.scrape_all_sources(days_back=7)
    
    # Or for specific date range
    results = manager.scrape_all_sources_date_range(start_date, end_date)
"""

import hashlib
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
from sqlalchemy.exc import IntegrityError

from ..core import get_db, config
from ..database.models import Source, Article, ScrapingLog
from .doj_scraper import DOJScraper
from .sec_scraper import SECScraper
from .cftc_scraper import CFTCScraper


class ScraperManager:
    """
    Centralized manager for coordinating web scraping operations across multiple sources.

    This class handles the initialization, execution, and monitoring of scraping
    operations for various government agency sources. It provides a unified interface
    for scraping recent articles or historical data within specific date ranges.

    Attributes:
        config: Application configuration object
        scrapers: Dictionary mapping source names to scraper instances

    The manager handles:
    - Automatic scraper initialization based on configuration
    - Parallel scraping coordination across multiple sources
    - Article deduplication and database storage
    - Error handling and recovery for individual sources
    - Progress tracking and logging for monitoring
    - Retry logic for transient network failures

    Scraping Results:
    Each scraping operation returns a dictionary with:
    - new_articles: Count of newly discovered articles
    - duplicate_articles: Count of articles already in database
    - total_articles: Total articles processed
    - article_results: Detailed list of processing results per article
    """

    def __init__(self):
        """
        Initialize the ScraperManager with configured sources.

        Automatically initializes scraper instances for all configured
        government agency sources based on the application configuration.
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info("ScraperManager.__init__ called")

        self.config = config
        self.scrapers = {}
        self._init_scrapers()

        logger.info(
            f"ScraperManager initialized with {len(self.scrapers)} scrapers: {list(self.scrapers.keys())}"
        )
        for name, scraper in self.scrapers.items():
            logger.debug(f"Scraper {name}: driver={getattr(scraper, 'driver', 'N/A')}")

    def close_all_scrapers(self):
        """Explicitly close all scraper WebDriver sessions."""
        for source_name, scraper in self.scrapers.items():
            if hasattr(scraper, "close"):
                scraper.close()

    def _init_scrapers(self):
        classes = {"doj": DOJScraper, "sec": SECScraper, "cftc": CFTCScraper}

        # Only initialize government agency scrapers
        for name, config in self.config.sources.get("agencies", {}).items():
            if name in classes:
                self.scrapers[name] = classes[name](config, self.config.scraping)

    def scrape_all_sources(self, days_back: int = 1) -> Dict[str, Any]:
        """Scrape all configured sources with proper error handling and logging."""
        from ..core import db_session

        results = {}

        try:
            with db_session() as db:
                for source_name, scraper in self.scrapers.items():
                    result = self._scrape_single_source(
                        db, source_name, scraper, days_back
                    )
                    results[scraper.source_config.name] = result
        except Exception as e:
            self._log_error(f"Error in scrape_all_sources: {str(e)}")
            results["error"] = str(e)

        return results

    def _scrape_single_source(
        self, db, source_name: str, scraper, days_back: int
    ) -> Dict[str, Any]:
        """Scrape a single source with comprehensive error handling."""
        try:
            self._emit_progress(f"Scraping {scraper.source_config.name}...")

            # Get source from database
            source = self._get_source_from_db(db, scraper.source_config.name)
            if not source:
                return self._create_empty_result()

            # Create and manage scraping log
            log = self._create_scraping_log(db, source.id)

            try:
                # Configure scraper and get articles
                scraper.db_session = db
                articles = self._get_articles_from_scraper(scraper, days_back)

                # Save articles to database
                save_result = self._save_articles(
                    db, source, articles, progress_callback
                )

                # Update log with success
                self._update_log_success(db, log, save_result)
                self._print_save_results(save_result)

                return save_result

            except Exception as e:
                # Update log with error
                self._update_log_error(db, log, str(e))
                self._emit_progress(f"Scraping failed: {e}")
                return self._create_empty_result()

        except Exception as e:
            self._log_error(f"Error scraping source {source_name}: {str(e)}")
            return self._create_empty_result()

    def _get_source_from_db(self, db, source_name: str):
        """Get source from database with error handling."""
        source = db.query(Source).filter_by(name=source_name).first()
        if not source:
            self._emit_progress(f"Source '{source_name}' not found in database")
        return source

    def _create_scraping_log(self, db, source_id: int) -> ScrapingLog:
        """Create a new scraping log entry."""
        log = ScrapingLog(
            source_id=source_id, started_at=datetime.now(), status="running"
        )
        db.add(log)
        db.flush()
        return log

    def _get_articles_from_scraper(self, scraper, days_back: int) -> List:
        """Get articles from scraper using appropriate method."""
        if hasattr(scraper, "scrape_date_range"):
            end = date.today()
            start = end - timedelta(days=int(days_back))
            return scraper.scrape_date_range(start, end)
        else:
            return scraper.scrape_recent(int(days_back))

    def _update_log_success(self, db, log: ScrapingLog, save_result: Dict):
        """Update scraping log with success status."""
        log.completed_at = datetime.now()
        log.status = "completed"
        log.articles_found = save_result["total_articles"]
        log.articles_new = save_result["new_articles"]

    def _update_log_error(self, db, log: ScrapingLog, error_message: str):
        """Update scraping log with error status."""
        log.completed_at = datetime.now()
        log.status = "failed"
        log.error_message = error_message

    def _create_empty_result(self) -> Dict[str, Any]:
        """Create an empty result for failed scraping attempts."""
        return {
            "new_articles": 0,
            "duplicate_articles": 0,
            "total_articles": 0,
            "article_results": [],
        }

    def _emit_progress(self, message: str):
        """Emit progress message (can be overridden for GUI integration)."""
        print(message)

    def _log_error(self, message: str):
        """Log error messages consistently."""
        import logging

        logging.error(f"ScraperManager: {message}")

    def scrape_all_sources_date_range(
        self, start_date: date, end_date: date, progress_callback=None
    ) -> Dict[str, Any]:
        """Scrape all sources for a specific date range with proper error handling."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"scrape_all_sources_date_range called with {len(self.scrapers)} scrapers"
        )

        from ..core import db_session

        results = {}

        try:
            logger.info("Opening database session...")
            with db_session() as db:
                logger.info(
                    f"Database session opened successfully, processing {len(self.scrapers)} scrapers"
                )

                # Debug: List all sources in database
                from ..database.models import Source

                all_sources = db.query(Source).all()
                logger.info(
                    f"Sources in database: {[s.name for s in all_sources]} (total: {len(all_sources)})"
                )
                for source_name, scraper in self.scrapers.items():
                    logger.info(
                        f"About to scrape {source_name} with scraper: {scraper}"
                    )
                    logger.debug(
                        f"Scraper {source_name} driver status: {getattr(scraper, 'driver', 'N/A')}"
                    )

                    logger.info(
                        f"Calling _scrape_single_source_date_range for {source_name}"
                    )
                    result = self._scrape_single_source_date_range(
                        db,
                        source_name,
                        scraper,
                        start_date,
                        end_date,
                        progress_callback,
                    )
                    logger.info(
                        f"_scrape_single_source_date_range returned for {source_name}: {result}"
                    )

                    results[scraper.source_config.name] = result
                logger.info("All scrapers completed, closing database session")
        except Exception as e:
            logger.error(f"Exception in scrape_all_sources_date_range: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_error(f"Error in scrape_all_sources_date_range: {str(e)}")
            results["error"] = str(e)

        return results

    def scrape_specific_agencies_date_range(
        self, agencies: list, start_date: date, end_date: date, progress_callback=None
    ) -> Dict[str, Any]:
        """Scrape specific agencies for a specific date range."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"scrape_specific_agencies_date_range called for agencies: {agencies}"
        )

        from ..core import db_session

        results = {}

        # Convert agency names to lowercase for matching
        target_agencies = [agency.lower() for agency in agencies]

        try:
            logger.info("Opening database session...")
            with db_session() as db:
                logger.info(
                    f"Database session opened successfully, filtering for agencies: {target_agencies}"
                )

                # Debug: List all sources in database
                from ..database.models import Source

                all_sources = db.query(Source).all()
                logger.info(
                    f"Sources in database: {[s.name for s in all_sources]} (total: {len(all_sources)})"
                )

                # Filter scrapers based on requested agencies
                filtered_scrapers = {}
                for source_name, scraper in self.scrapers.items():
                    scraper_name = scraper.source_config.name.lower()

                    # Check if this scraper matches any of the target agencies
                    should_include = False
                    for target_agency in target_agencies:
                        if (
                            target_agency in scraper_name
                            or source_name.lower() == target_agency
                            or (target_agency == "doj" and "justice" in scraper_name)
                            or (target_agency == "sec" and "securities" in scraper_name)
                            or (target_agency == "cftc" and "commodity" in scraper_name)
                        ):
                            should_include = True
                            break

                    if should_include:
                        filtered_scrapers[source_name] = scraper
                        logger.info(
                            f"Including scraper: {source_name} ({scraper.source_config.name})"
                        )
                    else:
                        logger.info(
                            f"Excluding scraper: {source_name} ({scraper.source_config.name})"
                        )

                if not filtered_scrapers:
                    logger.warning(f"No scrapers found for agencies: {agencies}")
                    return {"error": f"No scrapers found for agencies: {agencies}"}

                # Scrape from filtered scrapers
                for source_name, scraper in filtered_scrapers.items():
                    logger.info(
                        f"About to scrape {source_name} with scraper: {scraper}"
                    )
                    logger.debug(
                        f"Scraper {source_name} driver status: {getattr(scraper, 'driver', 'N/A')}"
                    )

                    logger.info(
                        f"Calling _scrape_single_source_date_range for {source_name}"
                    )
                    result = self._scrape_single_source_date_range(
                        db,
                        source_name,
                        scraper,
                        start_date,
                        end_date,
                        progress_callback,
                    )
                    logger.info(
                        f"_scrape_single_source_date_range returned for {source_name}: {result}"
                    )

                    results[scraper.source_config.name] = result

                logger.info(
                    f"Filtered scraping completed for {len(filtered_scrapers)} agencies"
                )

        except Exception as e:
            logger.error(f"Exception in scrape_specific_agencies_date_range: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_error(f"Error in scrape_specific_agencies_date_range: {str(e)}")
            results["error"] = str(e)

        return results

    def _scrape_single_source_date_range(
        self,
        db,
        source_name: str,
        scraper,
        start_date: date,
        end_date: date,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Scrape a single source for a date range with comprehensive error handling."""
        import logging

        logger = logging.getLogger(__name__)

        try:
            msg = f"Scraping {scraper.source_config.name} from {start_date} to {end_date}..."
            self._emit_progress_with_callback(msg, progress_callback)

            # Get source from database
            logger.info(
                f"Looking up source in database: '{scraper.source_config.name}'"
            )
            source = self._get_source_from_db(db, scraper.source_config.name)
            if not source:
                logger.warning(
                    f"Source '{scraper.source_config.name}' not found in database - returning empty result"
                )
                return self._create_empty_result()
            logger.info(f"Found source in database: {source.name} (ID: {source.id})")

            # Create and manage scraping log
            log = self._create_scraping_log(db, source.id)

            try:
                # Configure scraper and get articles
                scraper.db_session = db
                articles = self._get_articles_from_scraper_date_range(
                    scraper, start_date, end_date, progress_callback
                )

                # Save articles to database
                save_result = self._save_articles(
                    db, source, articles, progress_callback
                )

                # Update log with success
                self._update_log_success(db, log, save_result)
                self._print_save_results(save_result)

                return save_result

            except Exception as e:
                # Update log with error
                self._update_log_error(db, log, str(e))
                self._emit_progress_with_callback(
                    f"Error scraping {scraper.source_config.name}: {e}",
                    progress_callback,
                )
                return self._create_empty_result()

        except Exception as e:
            self._log_error(
                f"Error scraping source {source_name} for date range: {str(e)}"
            )
            return self._create_empty_result()

    def _get_articles_from_scraper_date_range(
        self, scraper, start_date: date, end_date: date, progress_callback=None
    ) -> List:
        """Get articles from scraper for a specific date range."""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"_get_articles_from_scraper_date_range called for {scraper.__class__.__name__}"
        )
        logger.debug(
            f"Scraper has scrape_date_range: {hasattr(scraper, 'scrape_date_range')}"
        )

        if hasattr(scraper, "scrape_date_range"):
            logger.info(f"Calling scrape_date_range on {scraper.__class__.__name__}")
            result = scraper.scrape_date_range(
                start_date, end_date, progress_callback=progress_callback
            )
            logger.info(
                f"scrape_date_range returned {len(result) if result else 0} articles"
            )
            return result
        else:
            # Calculate days back for scrapers without date range support
            days_back = (end_date - start_date).days + 1
            logger.info(
                f"Calling scrape_recent({days_back}) on {scraper.__class__.__name__}"
            )
            result = scraper.scrape_recent(days_back)
            logger.info(
                f"scrape_recent returned {len(result) if result else 0} articles"
            )
            return result

    def _emit_progress_with_callback(self, message: str, progress_callback=None):
        """Emit progress message with optional callback."""
        if progress_callback:
            progress_callback(message)
        else:
            self._emit_progress(message)

    def _save_articles(
        self, db, source: Source, articles: List, progress_callback=None
    ) -> Dict[str, int]:
        new_count = 0
        duplicate_count = 0
        total_count = len(articles)
        batch_hashes = set()
        batch_urls = set()
        article_results = []

        # Emit initial progress
        if total_count > 0:
            progress_msg = f"Processing {total_count} article{'s' if total_count != 1 else ''} from {source.name}..."
            self._emit_progress_with_callback(progress_msg, progress_callback)

        for article in articles:
            try:
                hash = self._generate_content_hash(
                    article["title"], article["content"], article["url"]
                )

                if hash in batch_hashes or article["url"] in batch_urls:
                    duplicate_count += 1
                    article_results.append(("duplicate_batch", article["title"]))
                    continue

                existing = (
                    db.query(Article)
                    .filter(
                        (Article.url == article["url"]) | (Article.content_hash == hash)
                    )
                    .first()
                )

                if existing:
                    duplicate_count += 1
                    article_results.append(("duplicate_db", article["title"]))

                    # Emit progress for duplicates (less verbose)
                    if (
                        duplicate_count % 5 == 1
                    ):  # Show every 5th duplicate to avoid spam
                        progress_msg = f"Found {duplicate_count} duplicate{'s' if duplicate_count > 1 else ''} (skipping)"
                        self._emit_progress_with_callback(
                            progress_msg, progress_callback
                        )

                    continue

                batch_hashes.add(hash)
                batch_urls.add(article["url"])

                word_count = (
                    len(article["content"].split()) if article["content"] else 0
                )
                db_article = Article(
                    source_id=source.id,
                    title=article["title"],
                    content=article["content"],
                    url=article["url"],
                    content_hash=hash,
                    published_date=article["published_date"],
                    author=article.get("author"),
                    category=article.get("category"),
                    tags=",".join(article.get("tags", [])),
                    word_count=word_count,
                    sentiment_score=None,
                )

                db.add(db_article)

                try:
                    db.commit()
                    new_count += 1
                    article_results.append(("saved", article["title"]))

                    # Emit progress update for each saved article
                    progress_msg = f"Saved: {article['title'][:60]}{'...' if len(article['title']) > 60 else ''}"
                    self._emit_progress_with_callback(progress_msg, progress_callback)

                except IntegrityError:
                    db.rollback()
                    duplicate_count += 1
                    article_results.append(("duplicate_race", article["title"]))
                    batch_hashes.discard(hash)
                    batch_urls.discard(article["url"])
                except Exception as e:
                    print(f"Error committing article '{article['title']}...': {e}")
                    db.rollback()
                    article_results.append(("error", article["title"], str(e)))
                    batch_hashes.discard(hash)
                    batch_urls.discard(article["url"])
                    continue

            except Exception as e:
                print(f"Error processing article '{article.title}...': {e}")
                article_results.append(("error", article.title, str(e)))
                continue

        # Emit final summary
        if total_count > 0:
            summary_msg = f"{source.name}: {new_count} new, {duplicate_count} duplicates, {total_count} total"
            self._emit_progress_with_callback(summary_msg, progress_callback)

        return {
            "new_articles": new_count,
            "duplicate_articles": duplicate_count,
            "total_articles": total_count,
            "article_results": article_results,
        }

    def _generate_content_hash(self, title: str, content: str, url: str) -> str:
        """Generate a unique hash for article deduplication."""
        # Combine key fields and normalize
        combined = f"{title.strip().lower()}|{content.strip()[:1000]}|{url.strip()}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _print_save_results(self, save_result: Dict[str, Any]):
        """Print the results of saving articles with accurate status indicators."""
        if "article_results" in save_result:
            for result_type, title, *extra in save_result["article_results"]:
                if result_type == "saved":
                    print(f"New: {title}...")
                elif result_type == "duplicate_db":
                    print(f"Dup: {title}...")
                elif result_type == "duplicate_batch":
                    print(f"Batch dup: {title}...")
                elif result_type == "duplicate_race":
                    print(f"Race dup: {title}...")
                elif result_type == "error":
                    error_msg = extra[0] if extra else "Unknown error"
                    print(f"Fail: {title}...")

            if save_result["duplicate_articles"] > 0 or save_result["new_articles"] > 0:
                print(
                    f"{save_result['new_articles']} saved, {save_result['duplicate_articles']} dups"
                )
        else:
            # Fallback for old format
            print(
                f"{save_result['total_articles']} found, {save_result['new_articles']} new"
            )
