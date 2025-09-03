"""URL scraper for individual web pages."""

import json
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from ..core import get_db, config
from ..database.models import Article, Source
from ..analysis.openai_client import OpenAIAnalyzer
from .base import BaseScraper


class URLScraper(BaseScraper):
    """Scraper for individual URLs using OpenAI to parse content."""

    def __init__(self, scraping_config):
        # Create a dummy source config for individual URLs
        class DummySourceConfig:
            def __init__(self):
                self.name = "Manual URL"
                self.base_url = ""
                self.enabled = True

        super().__init__(DummySourceConfig(), scraping_config)
        self.openai_analyzer = OpenAIAnalyzer(config.openai)

        # Load the article parser prompt
        from ..config.distribution import get_distribution_manager

        dist_manager = get_distribution_manager()
        prompts_dir = dist_manager.get_prompts_directory()
        prompt_path = prompts_dir / "article_parser.txt"

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.parser_prompt = f.read()
        except FileNotFoundError:
            # Fallback to basic parser prompt
            self.parser_prompt = """
You are an expert article parser. Extract structured information from web content and return ONLY valid JSON.

TASK: Extract these fields from the webpage content:
- title: Main headline
- content: Clean article body text  
- published_date: Date in YYYY-MM-DD format (or null)
- author: Article author (or null)
- category: Content type (e.g. "Press Release", "News Article")
- tags: 3-5 relevant keywords as array

CRITICAL INSTRUCTIONS:
1. Return ONLY a valid JSON object - no explanations, no markdown, no extra text
2. Focus on main article content, ignore navigation/ads/footers
3. Clean up text formatting and whitespace
4. If unclear content, use: {"error": "No clear article content found"}

WEBPAGE CONTENT TO ANALYZE:

{content}
"""

    def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL and parse it into an Article object.

        Args:
            url: The URL to scrape

        Returns:
            Dict containing success status, message, and article data
        """
        try:
            print(f"Scraping URL: {url}")

            # Step 1: Fetch the webpage
            response = self._make_request(url)
            if not response:
                return {
                    "success": False,
                    "error": "Failed to fetch URL",
                    "articles_count": 0,
                }

            # Step 2: Extract visible text
            visible_text = self._extract_visible_text(response.text)
            if not visible_text or len(visible_text.strip()) < 100:
                return {
                    "success": False,
                    "error": "Insufficient content found on page",
                    "articles_count": 0,
                }

            print(f"Extracted {len(visible_text)} characters of text")

            # Step 3: Parse with OpenAI
            article_data = self._parse_with_openai(visible_text, url)
            if not article_data or "error" in article_data:
                return {
                    "success": False,
                    "error": article_data.get(
                        "error", "Failed to parse article content"
                    ),
                    "articles_count": 0,
                }

            # Step 4: Add URL to article data
            article_data["url"] = url

            # Step 5: Save to database
            saved_article = self._save_article(article_data)
            if not saved_article:
                return {
                    "success": False,
                    "error": "Failed to save article to database",
                    "articles_count": 0,
                }

            return {
                "success": True,
                "message": f'Successfully scraped and saved article: {article_data.get("title", "Unknown Title")}',
                "articles_count": 1,
                "article": {
                    "title": article_data.get("title"),
                    "url": url,
                    "word_count": len(article_data.get("content", "").split()),
                },
            }

        except Exception as e:
            print(f"Error scraping URL {url}: {str(e)}")
            return {
                "success": False,
                "error": f"Scraping failed: {str(e)}",
                "articles_count": 0,
            }

    def _extract_visible_text(self, html: str) -> str:
        """
        Extract visible text content from HTML, filtering out navigation, ads, etc.

        Args:
            html: Raw HTML content

        Returns:
            Clean visible text content
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted elements
        unwanted_tags = [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "iframe",
            "noscript",
            "form",
            "button",
            "input",
            "select",
            "textarea",
        ]

        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove elements with common ad/navigation classes and IDs
        unwanted_selectors = [
            '[class*="nav"]',
            '[class*="menu"]',
            '[class*="sidebar"]',
            '[class*="ad"]',
            '[class*="advertisement"]',
            '[class*="banner"]',
            '[class*="popup"]',
            '[class*="modal"]',
            '[class*="cookie"]',
            '[class*="social"]',
            '[class*="share"]',
            '[class*="comment"]',
            '[id*="nav"]',
            '[id*="menu"]',
            '[id*="sidebar"]',
            '[id*="ad"]',
            '[id*="advertisement"]',
            '[id*="banner"]',
        ]

        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Extract text from main content areas first
        main_content = None
        main_selectors = [
            "main",
            "article",
            '[role="main"]',
            ".content",
            ".main-content",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".page-content",
        ]

        for selector in main_selectors:
            main_element = soup.select_one(selector)
            if main_element:
                main_content = main_element.get_text(separator=" ", strip=True)
                break

        # If no main content found, get all text
        if not main_content:
            main_content = soup.get_text(separator=" ", strip=True)

        # Clean up the text
        lines = main_content.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line and len(line) > 3:  # Filter out very short lines
                cleaned_lines.append(line)

        # Join lines and clean up whitespace
        cleaned_text = " ".join(cleaned_lines)
        cleaned_text = " ".join(cleaned_text.split())  # Normalize whitespace

        return cleaned_text

    def _parse_with_openai(
        self, content: str, url: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Use OpenAI to parse the content into structured article data.

        Args:
            content: Raw text content from the webpage

        Returns:
            Parsed article data or None if parsing failed
        """
        try:
            # Format the prompt with the content
            formatted_prompt = self.parser_prompt.format(content=content)

            # Call OpenAI
            response = self.openai_analyzer.analyze_text(
                text=formatted_prompt,
                system_prompt="You are an expert article parser. You MUST return only valid JSON format. No explanations, no markdown formatting, no extra text - just the JSON object.",
            )

            if not response:
                return {"error": "OpenAI analysis failed"}

            # Clean the response - sometimes OpenAI adds extra text
            cleaned_response = response.strip()

            # Try multiple approaches to extract JSON
            json_text = None

            # Approach 1: Look for complete JSON object
            json_start = cleaned_response.find("{")
            json_end = cleaned_response.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                json_text = cleaned_response[json_start:json_end]

            # Approach 2: If that fails, try to find JSON in markdown code blocks
            if not json_text or len(json_text) < 10:
                import re

                json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
                json_match = re.search(json_pattern, cleaned_response, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1)

            # Approach 3: Use the whole response if nothing else works
            if not json_text:
                json_text = cleaned_response

            # Try to parse JSON response
            try:
                parsed_data = json.loads(json_text)

                # Check if OpenAI returned an error
                if "error" in parsed_data:
                    print(f"OpenAI returned error: {parsed_data['error']}")
                    # Fall through to the fallback mechanism below
                    raise json.JSONDecodeError("OpenAI returned error", json_text, 0)

                # Validate required fields
                if "title" not in parsed_data or "content" not in parsed_data:
                    print(
                        f"Missing required fields. Parsed data keys: {list(parsed_data.keys())}"
                    )
                    # Fall through to the fallback mechanism below
                    raise json.JSONDecodeError("Missing required fields", json_text, 0)

                # Convert published_date string to UTC datetime if present
                if parsed_data.get("published_date"):
                    from ..utils.timezone_utils import parse_date_to_utc, get_utc_now
                    parsed_date = parse_date_to_utc(parsed_data["published_date"])
                    parsed_data["published_date"] = parsed_date if parsed_date else get_utc_now()
                else:
                    # Default to current UTC date if no date found
                    from ..utils.timezone_utils import get_utc_now
                    parsed_data["published_date"] = get_utc_now()

                return parsed_data

            except json.JSONDecodeError as e:
                # If JSON parsing completely fails, create a fallback article
                print(f"Failed to parse OpenAI response as JSON: {e}")
                print(f"Original response: {response[:500]}...")
                print(f"Extracted JSON text: {json_text[:300]}...")

                # Create fallback using original content
                print("Creating fallback article from extracted content...")

                # Try to extract title from the first lines of content
                content_lines = content.split("\n")
                potential_title = None

                # Look for the first substantial line as title
                for line in content_lines[:10]:  # Check first 10 lines
                    line = line.strip()
                    if len(line) > 10 and len(line) < 200:  # Good title length
                        potential_title = line
                        break

                # If no good title found, use URL-based title
                if not potential_title:
                    if url:
                        from urllib.parse import urlparse

                        parsed_url = urlparse(url)
                        potential_title = "Article from " + parsed_url.netloc
                    else:
                        potential_title = "Extracted Article"

                # Clean up content - remove the title line if it's there
                clean_content = content
                if potential_title and potential_title in content:
                    clean_content = content.replace(potential_title, "", 1).strip()

                # Truncate content if too long
                if len(clean_content) > 2000:
                    clean_content = clean_content[:2000] + "..."

                fallback_article = {
                    "title": potential_title[:200],  # Limit title length
                    "content": clean_content,
                    "published_date": datetime.now(),
                    "author": None,
                    "category": "Manual URL",
                    "tags": ["fallback", "extracted"],
                }

                return fallback_article

        except Exception as e:
            print(f"Error in OpenAI parsing: {str(e)}")
            return {"error": f"OpenAI parsing failed: {str(e)}"}

    def _save_article(self, article_data: Dict[str, Any]) -> Optional[Article]:
        """
        Save the parsed article to the database.

        Args:
            article_data: Parsed article data from OpenAI

        Returns:
            Saved Article object or None if saving failed
        """
        db = get_db()
        try:
            # Get or create the "Manual URL" source
            source = db.query(Source).filter(Source.name == "Manual URL").first()
            if not source:
                source = Source(
                    name="Manual URL",
                    base_url="",
                    source_type="manual",
                    scraper_type="manual",
                    enabled=True,
                )
                db.add(source)
                db.commit()
                db.refresh(source)

            # Generate content hash for duplicate detection
            content_hash = self._generate_content_hash(
                article_data["title"], article_data["content"], article_data["url"]
            )

            # Check for duplicates
            existing = (
                db.query(Article)
                .filter(
                    (Article.url == article_data["url"])
                    | (Article.content_hash == content_hash)
                )
                .first()
            )

            if existing:
                print(f"Article already exists: {article_data['title']}")
                return existing

            # Create new article
            word_count = (
                len(article_data["content"].split()) if article_data["content"] else 0
            )
            tags_str = (
                ",".join(article_data.get("tags", []))
                if article_data.get("tags")
                else ""
            )

            article = Article(
                source_id=source.id,
                title=article_data["title"],
                content=article_data["content"],
                url=article_data["url"],
                content_hash=content_hash,
                published_date=article_data["published_date"],
                author=article_data.get("author"),
                category=article_data.get("category", "Manual URL"),
                tags=tags_str,
                word_count=word_count,
                scraped_at=datetime.now(),
            )

            db.add(article)
            db.commit()
            db.refresh(article)

            print(f"Successfully saved article: {article.title}")
            return article

        except Exception as e:
            print(f"Error saving article: {str(e)}")
            db.rollback()
            return None
        finally:
            db.close()

    def _generate_content_hash(self, title: str, content: str, url: str) -> str:
        """Generate a hash for duplicate detection."""
        combined = f"{title.strip().lower()}{content.strip().lower()}{url}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()
