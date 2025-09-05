"""Department of Justice press release scraper."""

import logging
import weakref
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin, urlencode
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
from ._common import setup_chrome_options, log_safe_content

logger = logging.getLogger(__name__)


class DOJScraper(BaseScraper):
    """Scraper for Department of Justice press releases using Selenium."""
    
    def __init__(self, source_config, scraping_config):
        super().__init__(source_config, scraping_config)
        
        # Set up headless Chrome WebDriver with proper binary path
        chrome_options = setup_chrome_options()
        
        # Initialize WebDriver with automatic driver management
        # Use stable ChromeDriver version to avoid macOS security issues
        self.driver = None
        
        try:
            # Try multiple ChromeDriver initialization strategies
            service = None
            driver_error = None
            
            # Strategy 1: Try latest version first
            try:
                logger.info(f"Attempting ChromeDriver initialization (latest version) for {self.source_config.name}")
                service = Service(ChromeDriverManager().install())
            except Exception as e1:
                driver_error = f"Latest version failed: {e1}"
                logger.warning(f"ChromeDriverManager (latest) failed: {e1}")
                
                # Strategy 2: Try specific stable version
                try:
                    logger.info(f"Attempting ChromeDriver initialization (v138.0.7204.183) for {self.source_config.name}")
                    service = Service(
                        ChromeDriverManager(driver_version="138.0.7204.183").install()
                    )
                except Exception as e2:
                    driver_error = f"Specific version failed: {e2}"
                    logger.warning(f"ChromeDriverManager (specific version) failed: {e2}")

            if service:
                try:
                    logger.debug(
                        f"Creating ChromeDriver instance for {self.source_config.name}"
                    )
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.driver.implicitly_wait(10)
                    logger.info(
                        f"ChromeDriver initialized successfully for {self.source_config.name}"
                    )
                    logger.debug(f"ChromeDriver session ID: {self.driver.session_id}")
                    
                    # Use weakref.finalize for more reliable cleanup
                    self._finalizer = weakref.finalize(self, self._cleanup_driver, self.driver)
                except Exception as e:
                    logger.error(f"Failed to create Chrome webdriver for {self.source_config.name}: {e}")
                    self.driver = None
            else:
                logger.error(
                    f"Could not initialize ChromeDriverManager for {self.source_config.name}: {driver_error}"
                )
                self.driver = None

        except Exception as e:
            logger.error(
                f"Unexpected error during ChromeDriver initialization for {self.source_config.name}: {e}"
            )
            self.driver = None
        
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
                f"DOJScraper.__del__ called for {self.source_config.name} - finalizer will handle cleanup"
            )
    
    def scrape_recent(self, days_back: int = 1):
        """Scrape recent DOJ press releases."""
        # Ensure days_back is an integer
        days_back = int(days_back)
        
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        return self.scrape_date_range(start_date, end_date)
    
    def scrape_date_range(self, start_date, end_date, progress_callback=None):
        """Scrape DOJ press releases for a specific date range using date filtering."""
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
        
        msg = f"Scraping DOJ press releases from {start_obj} to {end_obj}"
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)
        
        # Try to use DOJ's built-in date filtering first
        try:
            return self._scrape_with_date_filter(start_obj, end_obj, progress_callback)
        except Exception as e:
            msg = f"Date filtering failed ({e}), falling back to pagination method"
            logger.warning(msg)
            if progress_callback:
                progress_callback(msg)
            return self._scrape_with_pagination_fallback(
                start_obj, end_obj, progress_callback
            )
    
    def _scrape_with_date_filter(self, start_date, end_date, progress_callback=None):
        """Use DOJ's date filtering interface."""
        articles = []
        
        logger.info("Using DOJ date filtering interface...")
        if progress_callback:
            progress_callback("Using DOJ date filtering interface...")
        
        # Navigate to the press releases page
        press_url = "https://www.justice.gov/news/press-releases"
        self.driver.get(press_url)
        time.sleep(3)  # Wait for page to load
        
        try:
            # Format dates for the form (MM/DD/YYYY format expected)
            start_str = start_date.strftime("%m/%d/%Y")
            end_str = end_date.strftime("%m/%d/%Y")
            
            logger.info(f"Setting date range: {start_str} to {end_str}")
            
            # Find and fill start date
            logger.debug("Finding start date element...")
            start_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="edit-start-date"]'))
            )
            start_input.clear()
            start_input.send_keys(start_str)
            logger.debug(f"Start date set to: {start_str}")
            time.sleep(1)
            
            # Find and fill end date
            logger.debug("Finding end date element...")
            end_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="edit-end-date"]'))
            )
            end_input.clear()
            end_input.send_keys(end_str)
            logger.debug(f"End date set to: {end_str}")
            time.sleep(1)
            
            # Click search button
            logger.debug("Clicking search button...")
            search_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="edit-submit-news"]'))
            )
            search_button.click()
            logger.debug("Search button clicked")
            
            # Wait for results to load and record the current URL
            logger.debug("Waiting for filtered results...")
            time.sleep(5)
            
            # Record the base URL after filtering is applied
            base_url = self.driver.current_url
            logger.info(f"Base filtered URL: {base_url}")
            
            # Now scrape the filtered results using URL-based pagination
            page = 0
            while True:
                # Construct the URL for the current page
                if page == 0:
                    # First page - use base URL as is
                    current_url = base_url
                else:
                    # Add page parameter to URL
                    separator = "&" if "?" in base_url else "?"
                    current_url = f"{base_url}{separator}page={page}"
                
                logger.info(f"Loading page {page + 1}: {current_url}")
                self.driver.get(current_url)
                time.sleep(3)  # Wait for page to load
                
                soup = self._parse_html(self.driver.page_source)
                items = soup.find_all("div", class_="views-row") or soup.find_all(
                    "article", class_="node"
                )
                
                if not items:
                    logger.info(
                        f"No items found on page {page + 1} - reached end of results"
                    )
                    break
                
                page_articles = self._process_page_items(items, start_date, end_date)
                articles.extend(page_articles)
                logger.info(
                    f"Processed {len(items)} items on page {page + 1}, found {len(page_articles)} new articles"
                )
                
                page += 1
                
                # Safety limit to prevent infinite loops
                if page > 20:
                    logger.warning("Reached safety limit of 20 pages")
                    break
            
            logger.info(f"Date filtering found {len(articles)} articles")
            return articles
            
        except Exception as e:
            logger.error(f"Date filtering interface error: {e}")
            raise e
    
    def _scrape_with_pagination_fallback(
        self, start_date, end_date, progress_callback=None
    ):
        """Fallback method using pagination and local date filtering."""
        articles = []
        page = 0
        
        # Parse date objects for comparison
        start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        logger.info("Using pagination fallback method...")
        
        # Load the initial press releases page
        press_url = "https://www.justice.gov/news/press-releases"
        logger.info(f"Loading initial page: {press_url}")
        self.driver.get(press_url)
        time.sleep(3)
        
        while True:
            try:
                # Construct the URL for the current page
                if page == 0:
                    current_url = press_url
                else:
                    current_url = f"{press_url}?page={page}"
                
                logger.info(f"Loading fallback page {page + 1}: {current_url}")
                self.driver.get(current_url)
                time.sleep(3)  # Wait for page to load
                
                # Get page source and parse with BeautifulSoup
                soup = self._parse_html(self.driver.page_source)
                
                # Find press release items
                items = soup.find_all("div", class_="views-row") or soup.find_all(
                    "article", class_="node"
                )
                
                # If no items found, we've reached the end
                if not items:
                    logger.info(f"No more results found on page {page}")
                    break
                
                page_articles = 0
                articles_too_old = 0
                
                for item in items:
                    try:
                        article = self._extract_article_from_item(
                            item, progress_callback
                        )
                        if article:
                            # Check if article is within our date range
                            if self._is_date_in_range(
                                article["published_date"], start_obj, end_obj
                            ):
                                articles.append(article)
                                page_articles += 1
                            elif (
                                article["published_date"]
                                and article["published_date"].date() < start_obj
                            ):
                                # Article is older than our range - count for early stopping
                                articles_too_old += 1
                                
                    except Exception as e:
                        logger.error(f"Error processing article item: {e}")
                        continue
                
                logger.info(
                    f"Processed {len(items)} items on page {page + 1}, found {page_articles} new articles ({articles_too_old} too old)"
                )
                
                # Stop if we found mostly old articles (indicates we've gone back far enough)
                if articles_too_old >= len(items) * 0.8:  # 80% of articles are too old
                    logger.info(
                        "Stopping: reached articles older than target date range"
                    )
                    break
                
                # Navigate to next page using URL parameter
                page += 1
                
                # Safety check to prevent infinite loops
                if page > 20:  # Reasonable limit
                    logger.warning("Reached maximum page limit (20)")
                    break
                    
            except Exception as e:
                logger.error(f"Error scraping page {page}: {e}")
                break
                
        logger.info(f"Total DOJ articles scraped: {len(articles)}")
        return articles
    
    def _process_page_items(self, items, start_date, end_date, progress_callback=None):
        """Process page items and return articles within date range."""
        page_articles = []
        
        for item in items:
            try:
                article = self._extract_article_from_item(item, progress_callback)
                if article:
                    # Check if article is within our date range
                    if self._is_date_in_range(
                        article["published_date"], start_date, end_date
                    ):
                        page_articles.append(article)
                        
            except Exception as e:
                logger.error(f"Error processing article item: {e}")
                continue
        
        return page_articles
    
    def _extract_article_from_item(self, item, progress_callback=None):
        """Extract article data from a press release item."""
        try:
            # Find title and link
            title_elem = (
                item.find("h3", class_="node__title")
                or item.find("h2", class_="node__title")
                or item.find("h3")
                or item.find("h2")
                or item.find("a", class_="node__title-link")
            )
            
            if not title_elem:
                return None
                
            # Get link - might be the title element itself or a child
            link_elem = title_elem if title_elem.name == "a" else title_elem.find("a")
            if not link_elem:
                return None
                
            title = self._clean_text(title_elem.get_text())
            url = self._resolve_url(link_elem.get("href"))
            
            # Check if article already exists in database by title
            if self._article_exists_by_title(title):
                logger.debug(f"Exists: {title}...")
                return None
            
            # Extract date from the listing
            published_date = self._extract_date_from_item(item)
            if not published_date:
                # Fallback: extract from individual page
                published_date = self._extract_date_from_page(url)
            
            if not published_date:
                logger.warning(f"Could not determine date for article: {title}")
                return None
            
            # Get full content from individual page
            content = self._extract_full_content(url, progress_callback)
            if not content:
                logger.warning(f"Could not extract content for: {title}")
                return None
            
            return {
                "title": title,
                "content": content,
                "url": url,
                "published_date": published_date,
                "category": "DOJ Press Release",
            }
            
        except Exception as e:
            logger.error(f"Error extracting article from item: {e}")
            return None
    
    def _extract_date_from_item(self, item) -> Optional[datetime]:
        """Extract publication date from a press release item."""
        try:
            # Look for various date element patterns
            date_selectors = [
                "time[datetime]",
                ".date-display-single",
                ".submitted",
                ".node__meta time",
                ".field--name-created time",
            ]
            
            for selector in date_selectors:
                date_elem = item.select_one(selector)
                if date_elem:
                    date_str = date_elem.get("datetime") or date_elem.get_text()
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        return parsed_date
                        
        except Exception:
            pass
            
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
        """Extract full content from a DOJ press release page."""
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
            
            # DOJ-specific content selectors (in order of preference)
            content_selectors = [
                ".field--name-body",  # Main body field
                ".field--name-field-pr-body",  # Press release body
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
    
    def _extract_date_from_page(self, url: str) -> Optional[datetime]:
        """Extract publication date from individual page."""
        try:
            self.driver.get(url)
            time.sleep(1)  # Brief wait for page load
            soup = self._parse_html(self.driver.page_source)
            
            # Look for date elements
            date_selectors = ["time[datetime]", ".date-display-single", ".submitted"]
            
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_str = date_elem.get("datetime") or date_elem.get_text()
                    return self._parse_date(date_str)
                    
        except Exception:
            pass
            
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from DOJ website and return UTC datetime."""
        from ..utils.timezone_utils import parse_date_to_utc
        
        if not date_str:
            return None
            
        # Use the timezone utility to parse and convert to UTC
        # DOJ is based in Washington DC (Eastern time)
        return parse_date_to_utc(date_str, source_timezone='America/New_York')
