"""Commodity Futures Trading Commission press release scraper."""

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


class CFTCScraper(BaseScraper):
    """Scraper for CFTC press releases using Selenium."""

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
                f"CFTCScraper.__del__ called for {self.source_config.name} - finalizer will handle cleanup"
            )

    def scrape_recent(self, days_back: int = 1):
        """Scrape recent CFTC press releases."""
        # Ensure days_back is an integer
        days_back = int(days_back)

        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)

        return self.scrape_date_range(start_date, end_date)
    
    def scrape_date_range(self, start_date, end_date, progress_callback=None):
        """Scrape CFTC press releases for a specific date range using year filtering."""
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

        msg = f"Scraping CFTC press releases from {start_obj} to {end_obj}"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

        try:
            # Generate list of years to scrape
            years_to_scrape = self._generate_years_range(start_obj, end_obj)

            for year in years_to_scrape:
                try:
                    msg = f"Scraping CFTC releases for {year}"
                    logger.info(msg)
                    if progress_callback:
                        progress_callback(msg)

                    year_articles = self._scrape_year(
                        year, start_obj, end_obj, progress_callback
                    )
                    articles.extend(year_articles)

                    logger.info(f"Found {len(year_articles)} articles for {year}")

                    # Add delay between year requests to be respectful
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error scraping CFTC for {year}: {e}")
                    continue

            logger.info(
                f"CFTC scraper found {len(articles)} total articles in date range"
            )
            return articles

        except Exception as e:
            logger.error(f"Error in CFTC date range scraping: {e}")
            if progress_callback:
                progress_callback(f"Error in CFTC scraping: {e}")
            return []

    def _generate_years_range(self, start_date, end_date):
        """Generate list of years to scrape."""
        years = []
        current_year = start_date.year
        end_year = end_date.year

        while current_year <= end_year:
            years.append(current_year)
            current_year += 1

        return years

    def _scrape_year(self, year, start_date, end_date, progress_callback=None):
        """Scrape CFTC press releases for a specific year."""
        articles = []

        try:
            # Navigate to the CFTC press releases page
            press_url = "https://www.cftc.gov/PressRoom/PressReleases"
            logger.info(f"Loading CFTC press releases page: {press_url}")
            self.driver.get(press_url)
            time.sleep(3)  # Wait for page to load

            # Click on "Show filters" to reveal filtering options
            try:
                logger.debug("Looking for 'Show filters' button")
                show_filters_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "show-filters"))
                )
                logger.debug("Clicking 'Show filters' button")
                show_filters_button.click()
                time.sleep(2)  # Wait for filters to appear

            except TimeoutException:
                logger.warning(
                    "Could not find 'Show filters' button, trying direct URL approach"
                )
                return self._scrape_direct_url(
                    year, start_date, end_date, progress_callback
                )

            # Now apply year filter - we'll use direct URL approach since it's more reliable
            filtered_url = f"{press_url}?combine=&field_press_release_types_value=All&field_release_number_value=&prtid=All&year={year}"
            logger.info(f"Using filtered URL: {filtered_url}")
            self.driver.get(filtered_url)
            time.sleep(3)

            # Now scrape the filtered results
            page = 0
            while True:
                # If not first page, add page parameter
                if page > 0:
                    current_url = self.driver.current_url
                    separator = "&" if "?" in current_url else "?"
                    paginated_url = f"{current_url}{separator}page={page}"
                    logger.info(f"Loading page {page + 1}: {paginated_url}")
                    self.driver.get(paginated_url)
                    time.sleep(3)

                # Parse the page
                soup = self._parse_html(self.driver.page_source)

                # Look for press release table
                # Based on your info: class="table table-hover table-striped"
                press_release_table = soup.find(
                    "table", class_="table table-hover table-striped"
                )

                if not press_release_table:
                    logger.info(f"No press release table found on page {page + 1}")
                    break

                # Find all rows in the table body
                table_rows = press_release_table.find("tbody")
                if not table_rows:
                    logger.info(f"No table body found on page {page + 1}")
                    break

                rows = table_rows.find_all("tr")
                if not rows:
                    logger.info(f"No table rows found on page {page + 1}")
                    break
                    
                page_articles = []
                for row in rows:
                    try:
                        article = self._extract_article_from_row(
                            row, start_date, end_date
                        )
                        if article:
                            page_articles.append(article)
                    except Exception as e:
                        logger.debug(f"Error processing CFTC press release row: {e}")
                        continue
                    
                articles.extend(page_articles)
                logger.info(
                    f"Processed {len(rows)} rows on page {page + 1}, found {len(page_articles)} articles"
                )
                    
                # Check if we should continue to next page
                if len(rows) == 0:
                    break
                        
                page += 1
            
                # Safety limit to prevent infinite loops
                if page > 10:
                    logger.warning("Reached safety limit of 10 pages for CFTC")
                    break
            
            return articles
            
        except Exception as e:
            logger.error(f"Error scraping CFTC for {year}: {e}")
            return articles
    
    def _scrape_direct_url(self, year, start_date, end_date, progress_callback=None):
        """Fallback method using direct URL construction."""
        articles = []

        try:
            # Construct filtered URL directly
            press_url = "https://www.cftc.gov/PressRoom/PressReleases"
            filtered_url = f"{press_url}?combine=&field_press_release_types_value=All&field_release_number_value=&prtid=All&year={year}"

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

                # Look for press release table
                press_release_table = soup.find(
                    "table", class_="table table-hover table-striped"
                )

                if not press_release_table:
                    logger.info(f"No press release table found on page {page + 1}")
                    break

                # Find all rows in the table body
                table_rows = press_release_table.find("tbody")
                if not table_rows:
                    logger.info(f"No table body found on page {page + 1}")
                    break

                rows = table_rows.find_all("tr")
                if not rows:
                    logger.info(f"No table rows found on page {page + 1}")
                    break

                page_articles = []
                for row in rows:
                    try:
                        article = self._extract_article_from_row(
                            row, start_date, end_date
                        )
                        if article:
                            page_articles.append(article)
                    except Exception as e:
                        logger.debug(f"Error processing CFTC press release row: {e}")
                        continue
            
                articles.extend(page_articles)
                logger.info(
                    f"Processed {len(rows)} rows on page {page + 1}, found {len(page_articles)} articles"
                )

                # Check if we should continue to next page
                if len(rows) == 0:
                    break

                page += 1

                # Safety limit to prevent infinite loops
                if page > 10:
                    logger.warning("Reached safety limit of 10 pages for CFTC")
                    break

            return articles
            
        except Exception as e:
            logger.error(f"Error in direct URL scraping for CFTC {year}: {e}")
            return articles

    def _extract_article_from_row(self, row, start_date, end_date):
        """Extract article data from a CFTC press release table row."""
        try:
            # Find all cells in the row
            cells = row.find_all("td")
            if len(cells) < 2:
                return None
    
            # Typically CFTC tables have: Date | Title | Release Number
            # Find the title cell (usually contains a link)
            title_elem = None
            url = None

            for cell in cells:
                link = cell.find("a")
                if link:
                    title_elem = link
                    url = self._resolve_url(link.get("href"))
                    break

            if not title_elem or not url:
                return None
            
            title = self._clean_text(title_elem.get_text())

            # Extract date - usually in the first cell
            published_date = None
            date_cell = cells[0]  # Assume first cell contains date
            date_text = self._clean_text(date_cell.get_text())
            published_date = self._parse_date(date_text)

            if not published_date:
                logger.warning(f"Could not parse date: {date_text}")
                return None

            # Check if date is in range
            if not self._is_date_in_range(published_date, start_date, end_date):
                return None

            # Check if article already exists in database by title
            if self._article_exists_by_title(title):
                logger.debug(f"Article already exists: {title}...")
                return None

            # Extract release number if available (usually in last cell)
            release_number = None
            if len(cells) > 2:
                release_number = self._clean_text(cells[-1].get_text())

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
                "category": "CFTC Press Release",
                "release_number": release_number,
            }

        except Exception as e:
            logger.error(f"Error extracting article from CFTC row: {e}")
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

    def _extract_full_content(self, url: str) -> Optional[str]:
        """Extract full content from a CFTC press release page."""
        try:
            logger.info(f"Loading full content from: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Get page source and parse with BeautifulSoup
            soup = self._parse_html(self.driver.page_source)

            # CFTC-specific content selectors (in order of preference)
            content_selectors = [
                ".field--name-body",  # Main body field
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
        """Parse various date formats from CFTC website and return UTC datetime."""
        from ..utils.timezone_utils import parse_date_to_utc
        
        if not date_str:
            return None

        # Use the timezone utility to parse and convert to UTC
        # CFTC is based in Washington DC (Eastern time)
        return parse_date_to_utc(date_str, source_timezone='America/New_York')
