"""OpenAI client for analysis."""

import os
from typing import Optional
from openai import OpenAI
import openai

from ..config.config import OpenAIConfig


class APIKeyInvalidError(Exception):
    """Raised when OpenAI API key is invalid or missing."""

    pass


class OpenAIAPIError(Exception):
    """Raised when OpenAI API encounters an error."""

    pass


class OpenAIAnalyzer:
    """Handles AI analysis using OpenAI."""

    def __init__(self, config: OpenAIConfig):
        self.config = config

        # Get API key from credential manager (not from config)
        from blogsai.config.credential_manager import CredentialManager

        credential_manager = CredentialManager()
        api_key = credential_manager.get_api_key()

        if not api_key:
            raise APIKeyInvalidError(
                "OpenAI API key is missing. Please set your API key in the settings."
            )

        try:
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            raise APIKeyInvalidError(f"Failed to initialize OpenAI client: {str(e)}")

    def analyze_articles(
        self, articles, prompt_template: str, context_data: Optional[dict] = None
    ) -> dict:
        """Analyze articles using OpenAI."""

        # Prepare articles text
        articles_text = self._format_articles_for_analysis(articles)

        # Format prompt with articles and context
        prompt = self._format_prompt(prompt_template, articles_text, context_data)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert legal and financial analyst specializing in regulatory analysis.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            analysis = response.choices[0].message.content
            tokens_used = response.usage.total_tokens

            return {
                "analysis": analysis,
                "tokens_used": tokens_used,
                "model": self.config.model,
                "success": True,
            }

        except openai.AuthenticationError as e:
            # Invalid API key
            error_msg = "Invalid OpenAI API key. Please check your API key in settings."
            raise APIKeyInvalidError(error_msg) from e

        except openai.PermissionDeniedError as e:
            # API key doesn't have permission for the model
            error_msg = f"API key doesn't have permission to use model '{self.config.model}'. Please check your OpenAI plan."
            raise OpenAIAPIError(error_msg) from e

        except openai.RateLimitError as e:
            # Rate limit exceeded
            error_msg = (
                "OpenAI rate limit exceeded. Please wait a moment and try again."
            )
            raise OpenAIAPIError(error_msg) from e

        except openai.BadRequestError as e:
            # Bad request (invalid parameters, etc.)
            error_msg = f"Invalid request to OpenAI API: {str(e)}"
            raise OpenAIAPIError(error_msg) from e

        except openai.APIConnectionError as e:
            # Network connection error
            error_msg = "Unable to connect to OpenAI API. Please check your internet connection."
            raise OpenAIAPIError(error_msg) from e

        except openai.APITimeoutError as e:
            # Request timeout
            error_msg = "OpenAI API request timed out. Please try again."
            raise OpenAIAPIError(error_msg) from e

        except openai.InternalServerError as e:
            # OpenAI server error
            error_msg = "OpenAI API is experiencing issues. Please try again later."
            raise OpenAIAPIError(error_msg) from e

        except Exception as e:
            # Handle specific gzip decompression errors
            if "decompressing data" in str(e) or "incorrect header check" in str(e):
                error_msg = "Network compression error occurred. This is usually temporary - please try again."
                raise OpenAIAPIError(error_msg) from e

            # Catch any other unexpected errors
            error_msg = f"Unexpected error during OpenAI analysis: {str(e)}"
            raise OpenAIAPIError(error_msg) from e

    def _format_articles_for_analysis(self, articles):
        """Format articles for AI analysis."""
        if not articles:
            return "No articles found for the specified time period."

        formatted_articles = []

        for i, article in enumerate(articles, 1):
            article_text = f"""
Article {i}:
Title: {article.title}
Source: {getattr(article, 'source_name', 'Unknown')}
Published: {article.published_date.strftime('%Y-%m-%d %H:%M')}
URL: {article.url}
Category: {article.category or 'N/A'}
Author: {article.author or 'N/A'}

Content:
{article.content[:2000]}{"..." if len(article.content) > 2000 else ""}

---
"""
            formatted_articles.append(article_text)

        return "\n".join(formatted_articles)

    def _format_prompt(
        self, template: str, articles_text: str, context_data: Optional[dict] = None
    ) -> str:
        """Format prompt template with articles and context."""

        # Base substitutions
        substitutions = {
            "articles": articles_text,
        }

        # Add context data if provided
        if context_data:
            substitutions.update(context_data)

        # Format the template
        try:
            return template.format(**substitutions)
        except KeyError as e:
            # Handle missing template variables gracefully
            print(f"Warning: Missing template variable {e}")
            return template.replace("{articles}", articles_text)

    def generate_summary(self, analysis: str, max_length: int = 200) -> str:
        """Generate a brief summary of the analysis."""

        if len(analysis) <= max_length:
            return analysis

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating concise summaries.",
                    },
                    {
                        "role": "user",
                        "content": f"Create a brief {max_length}-character summary of this analysis:\n\n{analysis}",
                    },
                ],
                max_tokens=100,
                temperature=0.3,
            )

            return response.choices[0].message.content

        except Exception as e:
            # Fallback to simple truncation
            return (
                analysis[:max_length] + "..."
                if len(analysis) > max_length
                else analysis
            )

    def analyze_with_research(
        self,
        articles,
        prompt_template: str,
        context_data: Optional[dict] = None,
        enable_web_search: bool = True,
    ) -> dict:
        """Analyze articles using OpenAI o3 model with web search for market intelligence."""

        # Prepare articles text
        articles_text = self._format_articles_for_analysis(articles)

        # Format prompt with articles and context
        prompt = self._format_prompt(prompt_template, articles_text, context_data)

        try:
            # Use responses API with web search tools for research
            if enable_web_search and hasattr(self.config, "research_model"):
                # Use responses API for web search (works with gpt-4o and other models)
                response = self.client.responses.create(
                    model=self.config.research_model,
                    input=prompt,
                    tools=[{"type": "web_search"}],
                    tool_choice="auto",
                )

                analysis = response.output_text
                tokens_used = len(prompt.split()) + len(
                    analysis.split()
                )  # Rough estimate

                return {
                    "analysis": analysis,
                    "tokens_used": tokens_used,
                    "model": self.config.research_model,
                    "success": True,
                    "web_search_enabled": True,
                }
            else:
                # Fallback to regular chat completion
                return self.analyze_articles(articles, prompt_template, context_data)

        except openai.AuthenticationError as e:
            error_msg = "Invalid OpenAI API key. Please check your API key in settings."
            raise APIKeyInvalidError(error_msg) from e

        except openai.PermissionDeniedError as e:
            error_msg = f"API key doesn't have permission to use model '{self.config.research_model}'. Please check your OpenAI plan."
            raise OpenAIAPIError(error_msg) from e

        except openai.RateLimitError as e:
            # Rate limit exceeded
            error_msg = f"OpenAI rate limit exceeded for model '{self.config.research_model}'. Please wait a moment and try again."
            raise OpenAIAPIError(error_msg) from e

        except openai.BadRequestError as e:
            error_msg = f"Invalid request to OpenAI API (possibly research model '{self.config.research_model}' not available): {str(e)}"
            raise OpenAIAPIError(error_msg) from e

        except Exception as e:
            # Handle specific gzip decompression errors
            if "decompressing data" in str(e) or "incorrect header check" in str(e):
                print(
                    f"Network/compression error with responses API, falling back to regular analysis: {e}"
                )
                return self.analyze_articles(articles, prompt_template, context_data)

            # If research model fails for any other reason, fallback to regular analysis
            print(
                f"Research model '{self.config.research_model}' failed, falling back to regular analysis: {e}"
            )
            return self.analyze_articles(articles, prompt_template, context_data)

    def analyze_text(self, text: str, system_prompt: str = None) -> Optional[str]:
        """
        Analyze arbitrary text using OpenAI.

        Args:
            text: The text to analyze
            system_prompt: Optional system prompt to set context

        Returns:
            Analysis result as string or None if failed
        """
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": text})

            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            return response.choices[0].message.content

        except openai.AuthenticationError as e:
            # Invalid API key
            error_msg = "Invalid OpenAI API key. Please check your API key in settings."
            raise APIKeyInvalidError(error_msg) from e

        except openai.PermissionDeniedError as e:
            # API key doesn't have permission for the model
            error_msg = f"API key doesn't have permission to use model '{self.config.model}'. Please check your OpenAI plan."
            raise OpenAIAPIError(error_msg) from e

        except openai.RateLimitError as e:
            # Rate limit exceeded
            error_msg = (
                "OpenAI rate limit exceeded. Please wait a moment and try again."
            )
            raise OpenAIAPIError(error_msg) from e

        except openai.BadRequestError as e:
            # Bad request (invalid parameters, etc.)
            error_msg = f"Invalid request to OpenAI API: {str(e)}"
            raise OpenAIAPIError(error_msg) from e

        except openai.APIConnectionError as e:
            # Network connection error
            error_msg = "Unable to connect to OpenAI API. Please check your internet connection."
            raise OpenAIAPIError(error_msg) from e

        except openai.APITimeoutError as e:
            # Request timeout
            error_msg = "OpenAI API request timed out. Please try again."
            raise OpenAIAPIError(error_msg) from e

        except openai.InternalServerError as e:
            # OpenAI server error
            error_msg = "OpenAI API is experiencing issues. Please try again later."
            raise OpenAIAPIError(error_msg) from e

        except Exception as e:
            # Handle specific gzip decompression errors
            if "decompressing data" in str(e) or "incorrect header check" in str(e):
                error_msg = "Network compression error occurred. This is usually temporary - please try again."
                raise OpenAIAPIError(error_msg) from e

            # Catch any other unexpected errors
            error_msg = f"Unexpected error during OpenAI analysis: {str(e)}"
            raise OpenAIAPIError(error_msg) from e
