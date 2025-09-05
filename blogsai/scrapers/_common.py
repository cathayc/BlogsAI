"""Common utilities and helper functions for government scrapers."""

import re
import logging
import weakref
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin, urlencode
from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


def log_safe_content(
    logger_func, message: str, content: str = None, max_length: int = 200
):
    """Safely log content without bloating logs with large HTML/text."""
    if content is None:
        logger_func(message)
    else:
        content_preview = (
            content[:max_length] + "..." if len(content) > max_length else content
        )
        logger_func(f"{message} (Preview: {content_preview})")


def setup_chrome_options():
    """Set up Chrome options with proper binary path for macOS."""
    import platform
    import os
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--disable-notifications")
    # Note: remote-debugging-port is set dynamically in initialize_chrome_driver()
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Add macOS-specific Chrome binary path if needed
    if platform.system() == "Darwin":  # macOS
        possible_chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chrome.app/Contents/MacOS/Chrome",
            "/usr/bin/google-chrome",
            "/usr/local/bin/chrome"
        ]
        
        for chrome_path in possible_chrome_paths:
            if os.path.exists(chrome_path):
                chrome_options.binary_location = chrome_path
                logger.info(f"Set Chrome binary location: {chrome_path}")
                break
        else:
            logger.warning("Chrome binary not found at expected locations")
    
    return chrome_options


def initialize_chrome_driver(scraper_name: str):
    """Initialize ChromeDriver with platform-specific strategies."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import subprocess
    import platform
    import os
    import random
    
    logger.info(f"Initializing ChromeDriver for {scraper_name}...")
    
    # Windows: Use the existing working approach with unique ports
    if platform.system() == "Windows":
        try:
            logger.info(f"Windows: Standard ChromeDriver setup for {scraper_name}")
            chrome_options = setup_chrome_options()
            
            # Use different debugging ports for each scraper to avoid conflicts
            port_map = {
                "Department of Justice": 9222,
                "Securities and Exchange Commission": 9223, 
                "Commodity Futures Trading Commission": 9224
            }
            debug_port = port_map.get(scraper_name, 9222 + random.randint(10, 99))
            
            # Update the remote debugging port to avoid conflicts
            chrome_options.add_argument(f"--remote-debugging-port={debug_port}")
            logger.info(f"Using debug port {debug_port} for {scraper_name}")
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info(f"Windows ChromeDriver initialized successfully for {scraper_name}")
            return driver
        except Exception as e:
            logger.error(f"Windows ChromeDriver failed for {scraper_name}: {e}")
            return None
    
    # macOS: Use multiple fallback strategies for compatibility
    elif platform.system() == "Darwin":
        # Strategy 1: Skip ChromeDriver entirely - use HTTP-based scraping
        logger.info(f"macOS Strategy 1: Attempting HTTP-based scraping for {scraper_name} (no ChromeDriver needed)")
        try:
            # Test if we can access the website via HTTP
            import requests
            from bs4 import BeautifulSoup
            
            # Test URLs for different scrapers
            test_urls = {
                "Department of Justice": "https://www.justice.gov/news",
                "Securities and Exchange Commission": "https://www.sec.gov/news/press-releases", 
                "Commodity Futures Trading Commission": "https://www.cftc.gov/PressRoom/PressReleases"
            }
            
            test_url = test_urls.get(scraper_name, "https://www.justice.gov/news")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(test_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # If we can parse content, HTTP scraping might work
                if soup.find('body'):
                    logger.info(f"macOS Strategy 1: HTTP-based scraping available for {scraper_name}")
                    return "HTTP_FALLBACK"  # Special marker for HTTP-based scraping
            
            logger.warning(f"macOS Strategy 1: HTTP test failed for {scraper_name}")
            
        except Exception as e1:
            logger.warning(f"macOS Strategy 1 (HTTP test) failed for {scraper_name}: {e1}")
        
        # Strategy 2: Try basic ChromeDriver with minimal options
        try:
            logger.info(f"macOS Strategy 2: Basic ChromeDriver for {scraper_name}")
            
            basic_options = Options()
            basic_options.add_argument("--headless")
            basic_options.add_argument("--no-sandbox")
            basic_options.add_argument("--disable-dev-shm-usage")
            basic_options.add_argument("--disable-gpu")
            
            os.environ['WDM_LOG_LEVEL'] = '0'
            service = Service(ChromeDriverManager().install())
            
            driver = webdriver.Chrome(service=service, options=basic_options)
            logger.info(f"macOS Strategy 2: Basic ChromeDriver initialized successfully for {scraper_name}")
            return driver
            
        except Exception as e2:
            logger.warning(f"macOS Strategy 2 (basic ChromeDriver) failed for {scraper_name}: {e2}")
        
        # Strategy 3: Try with system ChromeDriver (Homebrew installation) 
        try:
            logger.info(f"macOS Strategy 3: System ChromeDriver for {scraper_name}")
            
            chromedriver_paths = [
                "/opt/homebrew/bin/chromedriver",  # Apple Silicon Homebrew
                "/usr/local/bin/chromedriver",     # Intel Homebrew
                "/usr/bin/chromedriver"            # System installation
            ]
            
            system_chromedriver = None
            for path in chromedriver_paths:
                if os.path.exists(path):
                    system_chromedriver = path
                    break
            
            if system_chromedriver:
                logger.info(f"Found system ChromeDriver at {system_chromedriver}")
                basic_options = Options()
                basic_options.add_argument("--headless")
                basic_options.add_argument("--no-sandbox")
                basic_options.add_argument("--disable-dev-shm-usage")
                
                service = Service(system_chromedriver)
                driver = webdriver.Chrome(service=service, options=basic_options)
                logger.info(f"macOS Strategy 3: System ChromeDriver initialized successfully for {scraper_name}")
                return driver
            else:
                logger.info("No system ChromeDriver found")
                
        except Exception as e3:
            logger.warning(f"macOS Strategy 3 failed for {scraper_name}: {e3}")
        
        logger.error(f"All macOS ChromeDriver strategies failed for {scraper_name}")
        logger.info(f"Returning None - scrapers should handle HTTP fallback for {scraper_name}")
        return None
    
    # Linux: Use standard approach
    else:
        try:
            logger.info(f"Linux: Standard ChromeDriver setup for {scraper_name}")
            chrome_options = setup_chrome_options()
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info(f"Linux ChromeDriver initialized successfully for {scraper_name}")
            return driver
        except Exception as e:
            logger.error(f"Linux ChromeDriver failed for {scraper_name}: {e}")
            return None
