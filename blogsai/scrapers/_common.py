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
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
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
    """Initialize ChromeDriver with multiple fallback strategies."""
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    chrome_options = setup_chrome_options()
    driver = None
    
    # Strategy 1: Try specific stable version first (known to work on macOS)
    try:
        logger.info(f"Attempting ChromeDriver v138.0.7204.183 for {scraper_name}")
        service = Service(
            ChromeDriverManager(driver_version="138.0.7204.183").install()
        )
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info(f"ChromeDriver v138.0.7204.183 initialized successfully for {scraper_name}")
        return driver
    except Exception as e1:
        logger.warning(f"ChromeDriver v138.0.7204.183 failed for {scraper_name}: {e1}")
        
    # Strategy 2: Try another stable version
    try:
        logger.info(f"Attempting ChromeDriver v130.0.6723.116 for {scraper_name}")
        service = Service(
            ChromeDriverManager(driver_version="130.0.6723.116").install()
        )
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info(f"ChromeDriver v130.0.6723.116 initialized successfully for {scraper_name}")
        return driver
    except Exception as e2:
        logger.warning(f"ChromeDriver v130.0.6723.116 failed for {scraper_name}: {e2}")
        
    # Strategy 3: Try latest version as last resort
    try:
        logger.info(f"Attempting latest ChromeDriver version for {scraper_name}")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info(f"Latest ChromeDriver initialized successfully for {scraper_name}")
        return driver
    except Exception as e3:
        logger.error(f"All ChromeDriver initialization strategies failed for {scraper_name}: {e3}")
        
    return None
