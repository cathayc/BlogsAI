"""Web scrapers for different sources."""

from .doj_scraper import DOJScraper
from .sec_scraper import SECScraper
from .cftc_scraper import CFTCScraper
from .manager import ScraperManager

__all__ = ['DOJScraper', 'SECScraper', 'CFTCScraper', 'ScraperManager']
