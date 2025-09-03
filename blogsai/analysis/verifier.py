"""Citation and fact verification system for BlogsAI reports."""

import re
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from .openai_client import OpenAIAnalyzer, APIKeyInvalidError, OpenAIAPIError
from ..core import config


class CitationVerifier:
    """Verifies citations and facts in AI-generated reports."""

    def __init__(self):
        self.config = config
        self.openai_analyzer = OpenAIAnalyzer(self.config.openai)

        # Set up headless Chrome for verification
        self._setup_driver()

    def _setup_driver(self):
        """Set up headless Chrome WebDriver for citation verification."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)

    def __del__(self):
        """Clean up WebDriver when verifier is destroyed."""
        if hasattr(self, "driver") and self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def verify_report_citations(
        self, report_content: str, max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Verify all citations in a report and correct inaccuracies.

        Args:
            report_content: The full AI-generated report content
            max_iterations: Maximum number of correction iterations

        Returns:
            Dict with verification results and corrected content
        """
        print("Verifying citations...")

        current_content = report_content
        iteration = 0
        all_verification_results = []

        while iteration < max_iterations:
            iteration += 1
            print(f"Verification {iteration}/{max_iterations}")

            # Step 1: Extract citations from current content
            citations = self._extract_citations(current_content)

            if not citations:
                print("No citations found")
                break

            print(f"Found {len(citations)} citations to verify")

            # Step 2: Verify each citation
            verification_results = []
            for citation in citations:
                result = self._verify_single_citation(citation)
                verification_results.append(result)
                time.sleep(1)  # Rate limiting

            all_verification_results.extend(verification_results)

            # Step 3: Check if any citations failed verification
            failed_verifications = [
                r for r in verification_results if not r["verified"]
            ]

            if not failed_verifications:
                print("Citations verified")
                break

            print(f"{len(failed_verifications)} citation issues")

            # Step 4: Generate corrections
            corrected_content = self._generate_corrections(
                current_content, failed_verifications
            )

            if corrected_content["success"]:
                current_content = corrected_content["corrected_content"]
                print(f"Corrections applied")
            else:
                print(f"Correction failed: {corrected_content.get('error')}")
                break

        return {
            "success": True,
            "final_content": current_content,
            "verification_results": all_verification_results,
            "iterations_performed": iteration,
            "fully_verified": len(
                [r for r in all_verification_results if not r["verified"]]
            )
            == 0,
        }

    def _extract_citations(self, content: str) -> List[Dict[str, Any]]:
        """Extract URLs and quoted text from report content."""
        citations = []

        # Extract URLs
        url_pattern = r"https?://[^\s\)]+[^\s\.\)\,]"
        urls = re.findall(url_pattern, content)

        # Extract quoted text (text within quotes near URLs)
        quote_patterns = [
            r'"([^"]+)"',  # Double quotes
            r'> "([^"]+)"',  # Blockquote format
            r"> ([^<\n]+)",  # Blockquote without quotes
        ]

        for url in urls:
            # Find quotes near this URL (within 500 characters)
            url_position = content.find(url)
            if url_position == -1:
                continue

            # Look for quotes around the URL position
            start_pos = max(0, url_position - 500)
            end_pos = min(len(content), url_position + 500)
            surrounding_text = content[start_pos:end_pos]

            # Extract quotes from surrounding text
            quotes = []
            for pattern in quote_patterns:
                found_quotes = re.findall(pattern, surrounding_text)
                quotes.extend(found_quotes)

            citations.append(
                {"url": url, "quotes": quotes, "context": surrounding_text}
            )

        return citations

    def _verify_single_citation(self, citation: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a single citation against its source page."""
        url = citation["url"]
        quotes = citation["quotes"]

        print(f"Verifying: {url}")

        try:
            # Fetch the actual page content
            page_content = self._fetch_page_content(url)

            if not page_content:
                return {
                    "url": url,
                    "verified": False,
                    "error": "Could not fetch page content",
                    "quotes": quotes,
                }

            # Use AI to verify quotes against page content
            verification_result = self._ai_verify_quotes(quotes, page_content, url)

            return {
                "url": url,
                "verified": verification_result["verified"],
                "quotes": quotes,
                "page_content_preview": page_content[:500] + "...",
                "verification_details": verification_result,
            }

        except Exception as e:
            print(f"Verify error {url}: {e}")
            return {"url": url, "verified": False, "error": str(e), "quotes": quotes}

    def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and clean content from a web page."""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                print(f"Fetch {attempt + 1}/{max_retries}: {url}")
                self.driver.get(url)
                time.sleep(retry_delay)  # Wait for page load

                # Get page source and extract text content
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                # Remove unwanted elements
                for unwanted in soup(
                    ["script", "style", "nav", "aside", "footer", "header"]
                ):
                    unwanted.decompose()

                # Extract main content
                content_selectors = [
                    ".field--name-body",  # DOJ main body
                    ".field--name-field-pr-body",  # DOJ press release body
                    ".node-content",  # General node content
                    ".region-content",  # Content region
                    "#main-content",  # Main content area
                    "main",  # HTML5 main element
                    "article",  # Article content
                    "body",  # Fallback to body
                ]

                content = None
                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        content = content_elem.get_text()
                        break

                if not content:
                    content = soup.get_text()

                # Clean up whitespace
                content = " ".join(content.split())

                if content and len(content) > 100:
                    return content
                else:
                    print(f"Insufficient content from {url}")

            except Exception as e:
                print(f"Fetch error {url}: {e}")
                if attempt < max_retries - 1:
                    print(f"Retry in {retry_delay}s")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff

        print(f"Fetch failed: {url}")
        return None

    def _ai_verify_quotes(
        self, quotes: List[str], page_content: str, url: str
    ) -> Dict[str, Any]:
        """Use AI to verify if quotes are accurate against page content."""
        if not quotes:
            return {"verified": True, "details": "No quotes to verify"}

        try:
            # Load verification prompt
            prompt_template = self._load_prompt_template("citation_verifier.txt")

            context_data = {
                "quotes_to_verify": "\n".join([f'"{quote}"' for quote in quotes]),
                "page_content": page_content[:4000],  # Limit for API
                "source_url": url,
            }

            # Create a temporary article-like object for the API call
            class TempArticle:
                def __init__(self):
                    self.title = f"Verification for {url}"
                    self.content = page_content[:1000]
                    self.url = url
                    self.published_date = datetime.now()  # Add missing attribute
                    self.scraped_at = datetime.now()  # Add missing attribute

            temp_article = TempArticle()

            result = self.openai_analyzer.analyze_articles(
                [temp_article], prompt_template, context_data
            )

            if result["success"]:
                # Parse the verification response
                verification_text = result["analysis"].strip().upper()
                verified = (
                    "VERIFIED: TRUE" in verification_text
                    or "ACCURATE" in verification_text
                )

                return {
                    "verified": verified,
                    "details": result["analysis"],
                    "tokens_used": result.get("tokens_used", 0),
                }
            else:
                return {
                    "verified": False,
                    "details": f"AI verification failed: {result.get('error')}",
                    "tokens_used": 0,
                }

        except Exception as e:
            print(f"Error in AI verification: {e}")
            return {
                "verified": False,
                "details": f"Verification error: {str(e)}",
                "tokens_used": 0,
            }

    def _generate_corrections(
        self, content: str, failed_verifications: List[Dict]
    ) -> Dict[str, Any]:
        """Generate corrected content based on failed verifications."""
        try:
            # Load correction prompt
            prompt_template = self._load_prompt_template("citation_corrector.txt")

            # Prepare error details
            error_details = []
            for failure in failed_verifications:
                error_details.append(
                    f"""
URL: {failure['url']}
Problematic Quotes: {', '.join(failure['quotes'])}
Issue: {failure.get('verification_details', {}).get('details', 'Verification failed')}
Actual Page Content Preview: {failure.get('page_content_preview', 'Not available')}
"""
                )

            context_data = {
                "original_content": content,
                "citation_errors": "\n---\n".join(error_details),
            }

            # Create temporary article for correction
            class TempArticle:
                def __init__(self):
                    self.title = "Content Correction"
                    self.content = content[:1000]
                    self.url = "internal://correction"
                    self.published_date = datetime.now()  # Add missing attribute
                    self.scraped_at = datetime.now()  # Add missing attribute

            temp_article = TempArticle()

            result = self.openai_analyzer.analyze_articles(
                [temp_article], prompt_template, context_data
            )

            if result["success"]:
                return {
                    "success": True,
                    "corrected_content": result["analysis"],
                    "tokens_used": result.get("tokens_used", 0),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error"),
                    "tokens_used": 0,
                }

        except Exception as e:
            print(f"Error generating corrections: {e}")
            return {"success": False, "error": str(e), "tokens_used": 0}

    def _load_prompt_template(self, filename: str) -> str:
        """Load prompt template from file."""
        from pathlib import Path
        from ..config.distribution import get_distribution_manager

        # Use distribution manager for prompts directory
        dist_manager = get_distribution_manager()
        prompts_dir = dist_manager.get_prompts_directory()
        prompt_path = prompts_dir / filename

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")

        with open(prompt_path, "r") as f:
            return f.read()
