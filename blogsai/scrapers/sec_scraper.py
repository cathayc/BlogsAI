"""Securities and Exchange Commission press release scraper."""

import re
import logging
import weakref
from datetime import datetime, timedelta
from typing import List, Optional
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from .base import BaseScraper
from ._common import setup_chrome_options, log_safe_content, initialize_chrome_driver

logger = logging.getLogger(__name__)


class SECScraper(BaseScraper):
    """Scraper for SEC press releases using Selenium."""
    
    def __init__(self, source_config, scraping_config):
        super().__init__(source_config, scraping_config)
        
        # Initialize ChromeDriver using the common helper function
        self.driver = initialize_chrome_driver(self.source_config.name)
        
        if self.driver:
            self.driver.implicitly_wait(10)
            logger.debug(f"ChromeDriver session ID: {self.driver.session_id}")
            
            # Use weakref.finalize for more reliable cleanup
            self._finalizer = weakref.finalize(self, self._cleanup_driver, self.driver)
    
    @staticmethod
    def _cleanup_driver(driver):
        """Static method to cleanup driver - used by weakref.finalize."""
        if driver:
            try:
                logger.warning(
                    f"Cleaning up ChromeDriver session {driver.session_id} via finalizer"
                )
                driver.quit()
            except Exception as e:
                logger.warning(f"Error in finalizer cleanup: {e}")
        
    def close(self):
        """Explicitly close the WebDriver."""
        if hasattr(self, "driver") and self.driver:
            try:
                logger.debug(f"Closing ChromeDriver for {self.source_config.name}")
                # Cancel the finalizer since we're explicitly closing
                if hasattr(self, "_finalizer"):
                    self._finalizer.detach()
                self.driver.quit()
                self.driver = None
            except Exception as e:
                logger.warning(
                    f"Error closing ChromeDriver for {self.source_config.name}: {e}"
                )
        
    def __del__(self):
        """Clean up WebDriver when scraper is destroyed."""
        # The finalizer will handle cleanup, but log if this is called
        if hasattr(self, "driver") and self.driver:
            logger.debug(
                f"SECScraper.__del__ called for {self.source_config.name} - finalizer will handle cleanup"
            )
    
    def scrape_recent(self, days_back: int = 1):
        """Scrape recent SEC press releases."""
        # Ensure days_back is an integer
        days_back = int(days_back)

        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)

        return self.scrape_date_range(start_date, end_date)

    def scrape_date_range(self, start_date, end_date, progress_callback=None):
        """Scrape SEC press releases for a specific date range using year/month filtering."""
        logger.debug(
            f"scrape_date_range called for {self.source_config.name} with driver: {self.driver}"
        )

        # Check if ChromeDriver initialization failed
        if self.driver is None:
            msg = f"Cannot scrape {self.source_config.name}: ChromeDriver failed to initialize"
            logger.error(msg)
            if progress_callback:
                progress_callback(f"Error: {msg}")
            return []
        
        articles = []
        
        # Convert dates to date objects for comparison
        start_obj = (
            start_date
            if hasattr(start_date, "year")
            else datetime.strptime(str(start_date), "%Y-%m-%d").date()
        )
        end_obj = (
            end_date
            if hasattr(end_date, "year")
            else datetime.strptime(str(end_date), "%Y-%m-%d").date()
        )

        msg = f"Scraping SEC press releases from {start_obj} to {end_obj}"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

        try:
            # Generate list of year/month combinations to scrape
            year_month_combinations = self._generate_year_month_range(
                start_obj, end_obj
            )

            for year, month in year_month_combinations:
                try:
                    msg = f"Scraping SEC releases for {year}-{month:02d}"
                    logger.info(msg)
                    if progress_callback:
                        progress_callback(msg)

                    month_articles = self._scrape_year_month(
                        year, month, start_obj, end_obj, progress_callback
                    )
                    articles.extend(month_articles)

                    logger.info(
                        f"Found {len(month_articles)} articles for {year}-{month:02d}"
                    )

                    # Add delay between month requests to be respectful
                    time.sleep(2)

                except Exception as e:
                    logger.error(f"Error scraping SEC for {year}-{month:02d}: {e}")
                    continue

            logger.info(
                f"SEC scraper found {len(articles)} total articles in date range"
            )
            return articles

        except Exception as e:
            logger.error(f"Error in SEC date range scraping: {e}")
            if progress_callback:
                progress_callback(f"Error in SEC scraping: {e}")
            return []

    def _generate_year_month_range(self, start_date, end_date):
        """Generate list of (year, month) tuples to scrape."""
        year_month_combinations = []

        current = start_date.replace(day=1)  # Start from first day of start month
        end = end_date.replace(day=1)  # End at first day of end month

        while current <= end:
            year_month_combinations.append((current.year, current.month))

            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return year_month_combinations

    def _scrape_year_month(
        self, year, month, start_date, end_date, progress_callback=None
    ):
        """Scrape SEC press releases for a specific year/month combination."""
        try:
            # Try direct URL approach first since it's more reliable
            logger.info(f"Using direct URL approach for SEC {year}-{month:02d}")
            return self._scrape_direct_url(
                year, month, start_date, end_date, progress_callback
            )

        except Exception as e:
            logger.error(f"Error scraping SEC for {year}-{month:02d}: {e}")
            return []

    def _scrape_direct_url(
        self, year, month, start_date, end_date, progress_callback=None
    ):
        """Fallback method using direct URL construction."""
        articles = []

        try:
            # Construct filtered URL directly
            press_url = "https://www.sec.gov/newsroom/press-releases"
            filtered_url = f"{press_url}?combine=&year={year}&month={month}&field_person_target_id=&speaker="

            logger.info(f"Using direct URL approach: {filtered_url}")
            self.driver.get(filtered_url)
            time.sleep(5)  # Wait for page to load

            # Now scrape the filtered results
            page = 0
            while True:
                # If not first page, add page parameter
                if page > 0:
                    paginated_url = f"{filtered_url}&page={page}"
                    logger.info(f"Loading page {page + 1}: {paginated_url}")
                    self.driver.get(paginated_url)
                    time.sleep(3)

                # Parse the page
                soup = self._parse_html(self.driver.page_source)

                # Look for press release table rows
                press_release_rows = soup.find_all("tr", class_="pr-list-page-row")

                if not press_release_rows:
                    logger.info(f"No press release rows found on page {page + 1}")
                    break

                page_articles = []
                for row in press_release_rows:
                    try:
                        article = self._extract_article_from_row(
                            row, start_date, end_date
                        )
                        if article:
                            page_articles.append(article)
                    except Exception as e:
                        logger.debug(f"Error processing press release row: {e}")
                        continue
            
                articles.extend(page_articles)
                logger.info(
                    f"Processed {len(press_release_rows)} rows on page {page + 1}, found {len(page_articles)} articles"
                )

                # Check if we should continue to next page
                if len(press_release_rows) == 0:
                    break

                page += 1

                # Safety limit to prevent infinite loops
                if page > 10:
                    logger.warning("Reached safety limit of 10 pages for SEC")
                    break

            return articles
            
        except Exception as e:
            logger.error(
                f"Error in direct URL scraping for SEC {year}-{month:02d}: {e}"
            )
            return articles

    def _extract_article_from_row(self, row, start_date, end_date):
        """Extract article data from a SEC press release table row."""
        try:
            # Extract date from the row
            # Based on HTML: <time datetime="2015-10-30T13:45:00Z" class="datetime">Oct. 30, 2015</time>
            date_elem = row.find("time", class_="datetime")
            if not date_elem:
                return None

            date_str = date_elem.get("datetime") or date_elem.get_text()
            published_date = self._parse_date(date_str)

            if not published_date:
                logger.warning(f"Could not parse date: {date_str}")
                return None

            # Check if date is in range
            if not self._is_date_in_range(published_date, start_date, end_date):
                return None

            # Extract title and link
            # Based on HTML: <a href="/newsroom/press-releases/2015-249" hreflang="en">SEC Adopts Rules to Permit Crowdfunding</a>
            title_elem = row.find("a", href=re.compile(r"/newsroom/press-releases/"))
            if not title_elem:
                return None

            title = self._clean_text(title_elem.get_text())
            url = self._resolve_url(title_elem.get("href"))

            # Check if article already exists in database by title
            if self._article_exists_by_title(title):
                logger.debug(f"Article already exists: {title}...")
                return None

            # Extract release number if available
            # Based on HTML: <td headers="view-field-release-number-table-column" class="views-field views-field-field-release-number">2015-249</td>
            release_number = None
            release_elem = row.find("td", class_="views-field-field-release-number")
            if release_elem:
                release_number = self._clean_text(release_elem.get_text())

            # Get full content from individual page
            content = self._extract_full_content(url)
            if not content:
                logger.warning(f"Could not extract content for: {title}")
                return None

            return {
                "title": title,
                "content": content,
                "url": url,
                "published_date": published_date,
                "category": "SEC Press Release",
                "release_number": release_number,
            }

        except Exception as e:
            logger.error(f"Error extracting article from SEC row: {e}")
            return None

    def _is_date_in_range(self, date: datetime, start_date, end_date) -> bool:
        """Check if a date falls within the specified range."""
        if not date:
            return False

        # Convert to date objects for comparison
        date_obj = date.date() if hasattr(date, "date") else date
        start_obj = (
            start_date
            if hasattr(start_date, "year")
            else datetime.strptime(str(start_date), "%Y-%m-%d").date()
        )
        end_obj = (
            end_date
            if hasattr(end_date, "year")
            else datetime.strptime(str(end_date), "%Y-%m-%d").date()
        )

        return start_obj <= date_obj <= end_obj

    def _extract_full_content(self, url: str, progress_callback=None) -> Optional[str]:
        """Extract full content from a SEC press release page."""
        try:
            if progress_callback:
                progress_callback(f"Loading full content from: {url}")
            else:
                logger.info(f"Loading full content from: {url}")
            self.driver.get(url)

            # Wait for page to load
            time.sleep(2)

            # Get page source and parse with BeautifulSoup
            soup = self._parse_html(self.driver.page_source)

            # SEC-specific content selectors (in order of preference)
            content_selectors = [
                ".field--name-body",  # Main body field
                ".field--name-field-display-title",  # SEC display title
                ".node-content",  # Node content wrapper
                ".region-content",  # Content region
                "#main-content",  # Main content area
                ".page-content",  # Page content
                "main",  # HTML5 main element
                "article .content",  # Article content
            ]

            content = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Remove unwanted elements
                    for unwanted in content_elem(
                        ["script", "style", "nav", "aside", "footer", "header"]
                    ):
                        unwanted.decompose()

                    # Also remove social sharing, related links, etc.
                    for unwanted_class in [
                        ".social-share",
                        ".related-links",
                        ".tags",
                        ".breadcrumb",
                    ]:
                        for elem in content_elem.select(unwanted_class):
                            elem.decompose()

                    content = self._clean_text(content_elem.get_text())

                    # Check if we got substantial content (at least 100 characters)
                    if content and len(content.strip()) > 100:
                        break
                            
            if not content or len(content.strip()) < 50:
                logger.warning(f"Insufficient content extracted from {url}")
                return None

            # Log content length instead of the actual content to avoid bloating logs
            logger.debug(
                f"Successfully extracted {len(content.strip())} characters of content from {url}"
            )
            return content.strip()
                            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")

        return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from SEC website and return UTC datetime."""
        from ..utils.timezone_utils import parse_date_to_utc
        
        if not date_str:
            return None

        # Use the timezone utility to parse and convert to UTC
        # SEC is based in Washington DC (Eastern time)
        return parse_date_to_utc(date_str, source_timezone='America/New_York')
