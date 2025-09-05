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
                break
    
    return chrome_options
