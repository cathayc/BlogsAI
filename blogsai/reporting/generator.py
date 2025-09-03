"""Report generation and formatting."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Template
import markdown
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.lib.colors import black, blue, white, grey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

from ..core import get_db, config
from ..database.models import Report, Article, Source
from ..config.app_dirs import app_dirs


class ReportGenerator:
    """Generates reports in various formats."""
    
    def _format_local_date(self, dt, format_str="%B %d, %Y"):
        """Format UTC datetime as local date string."""
        from ..utils.timezone_utils import format_local_date
        return format_local_date(dt, format_str)

    def __init__(self):
        self.config = config

        # Use platform-appropriate reports directory (with fallback handling)
        self.output_dir = app_dirs.get_reports_directory()

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _clean_json_content(self, json_text: str) -> str:
        """Clean JSON content by removing markdown code fences and extra formatting."""
        if not json_text:
            return json_text

        # Start with basic cleanup
        cleaned = json_text.strip()

        # Remove ```json markers first (case insensitive)
        import re

        cleaned = re.sub(r"```json\s*", "", cleaned, flags=re.IGNORECASE)

        # Remove any remaining ``` markers
        cleaned = re.sub(r"```\s*", "", cleaned)

        # Remove newlines
        cleaned = cleaned.replace("\n", "")

        # Remove standalone backslashes that are not part of valid JSON escape sequences
        # Valid JSON escape sequences: \" \\ \/ \b \f \n \r \t \uXXXX
        # Only remove backslashes that are not followed by valid escape characters
        cleaned = re.sub(r'\\(?!["\\/bfnrtu])', "", cleaned)

        # Remove "json" prefix if it exists
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

        # Validate that it's actually JSON
        import json

        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            # If cleaning failed, return original
            return json_text

    def generate_report_files(self, report_id: int) -> Dict[str, str]:
        """Generate report files in configured formats with proper error handling."""
        from ..core import db_session

        try:
            with db_session() as db:
                # Validate report exists
                report = self._get_report_by_id(db, report_id)
                if not report:
                    raise ValueError(f"Report {report_id} not found")

                # Get associated articles
                articles = self._get_report_articles(db, report_id)

                # Generate files in all configured formats
                generated_files = self._generate_all_formats(report, articles)

                # Update report with file paths
                self._update_report_file_paths(report, generated_files)

                return generated_files

        except Exception as e:
            self._log_error(
                f"Error generating report files for report {report_id}: {str(e)}"
            )
            raise

    def _get_report_by_id(self, db, report_id: int):
        """Get report by ID with error handling."""
        try:
            return db.query(Report).filter_by(id=report_id).first()
        except Exception as e:
            self._log_error(f"Error fetching report {report_id}: {str(e)}")
            return None

    def _generate_all_formats(self, report, articles: List) -> Dict[str, str]:
        """Generate report files in all configured formats."""
        generated_files = {}

        for fmt in self.config.reporting.formats:
            try:
                file_path = self._generate_format(report, articles, fmt)
                generated_files[fmt] = file_path

            except Exception as e:
                self._log_error(
                    f"Error generating {fmt} format for report {report.id}: {str(e)}"
                )
                # Continue with other formats even if one fails
                continue

        return generated_files

    def _update_report_file_paths(self, report, generated_files: Dict[str, str]):
        """Update report record with generated file paths."""
        try:
            for fmt, file_path in generated_files.items():
                if fmt == "html":
                    report.html_file = file_path
                elif fmt == "json":
                    report.json_file = file_path
                elif fmt == "markdown":
                    report.markdown_file = file_path
        except Exception as e:
            self._log_error(f"Error updating report file paths: {str(e)}")

    def _log_error(self, message: str):
        """Log error messages consistently."""
        import logging

        logging.error(f"ReportGenerator: {message}")

    def _generate_format(self, report: Report, articles: List[Dict], fmt: str) -> str:
        safe_title = "".join(
            c for c in report.title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        filepath = Path(self.output_dir) / f"{safe_title}.{fmt}"

        generators = {
            "json": self._generate_json,
            "html": self._generate_html,
            "markdown": self._generate_markdown,
            "pdf": self._generate_pdf,
        }

        if fmt in generators:
            generators[fmt](report, articles, filepath)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        return str(filepath)

    def _generate_json(self, report: Report, articles: List[Dict], filepath: Path):
        report_data = {
            "metadata": {
                "id": report.id,
                "title": report.title,
                "type": report.report_type,
                "start_date": report.start_date.isoformat(),
                "end_date": report.end_date.isoformat(),
                "created_at": report.created_at.isoformat(),
                "article_count": report.article_count,
                "tokens_used": report.tokens_used,
            },
            "summary": report.summary,
            "analysis": report.analysis,
            "articles": articles,
        }

        with open(filepath, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

    def _generate_html(self, report: Report, articles: List[Dict], filepath: Path):
        """Generate HTML report."""
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ report.title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        a { color: #007acc; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .header { border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
        .metadata { background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .summary { background: #e8f4fd; padding: 15px; border-left: 4px solid #007acc; margin-bottom: 20px; }
        .analysis { margin-bottom: 30px; }
        .articles { margin-top: 30px; }
        .article { border: 1px solid #ddd; margin-bottom: 20px; padding: 15px; border-radius: 5px; }
        .article-title { font-weight: bold; margin-bottom: 10px; }
        .article-meta { color: #666; font-size: 0.9em; margin-bottom: 10px; }
        .article-content { margin-top: 10px; }
        
        /* Structured analysis styling */
        .structured-analysis { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .markdown-analysis { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .analysis-section { margin-bottom: 20px; }
        .analysis-section h3 { color: #2c3e50; margin-bottom: 10px; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }
        .analysis-section ul { margin-left: 20px; }
        .analysis-section li { margin-bottom: 5px; }
        
        /* Markdown content styling */
        .markdown-content h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .markdown-content h2 { color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 30px; }
        .markdown-content h3 { color: #7f8c8d; margin-top: 25px; }
        .markdown-content strong { color: #2c3e50; }
        .markdown-content ul { margin-left: 20px; }
        .markdown-content li { margin-bottom: 8px; }
        .markdown-content p { margin-bottom: 15px; }
        .markdown-content blockquote { 
            border-left: 4px solid #3498db; 
            padding-left: 15px; 
            margin: 15px 0; 
            font-style: italic; 
            background: #ecf0f1; 
            padding: 10px 15px;
        }
        .markdown-content code { 
            background: #f8f9fa; 
            padding: 2px 4px; 
            border-radius: 3px; 
            font-family: 'Courier New', monospace; 
        }
        .markdown-content hr { 
            border: none; 
            height: 2px; 
            background: #bdc3c7; 
            margin: 25px 0; 
        }
        pre { white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ report.title }}</h1>
        <div class="metadata">
            <strong>Report Date:</strong> {{ report.start_date.strftime('%B %d, %Y') }}<br>
            <strong>Articles Analyzed:</strong> {{ report.article_count }}<br>
            <strong>AI Tokens Used:</strong> {{ report.tokens_used }}
        </div>
    </div>
    
    {% if report.summary %}
    <div class="summary">
        <h2>Summary</h2>
        <p>{{ report.summary }}</p>
    </div>
    {% endif %}
    
    <div class="analysis">
        <h2>Analysis</h2>
        <div class="markdown-content">{{ analysis_html|safe }}</div>
    </div>
    
    <div class="articles">
        <h2>Source Articles ({{ articles|length }})</h2>
        {% for article in articles %}
        <div class="article">
            <div class="article-title">{{ article.title }}</div>
            <div class="article-meta">
                <strong>Source:</strong> {{ article.source_name }} | 
                <strong>Published:</strong> {{ article.published_date.strftime('%Y-%m-%d %H:%M') }}
                {% if include_links %} | <a href="{{ article.url }}" target="_blank">View Original</a>{% endif %}
                {% if article.relevance_score %} | <strong>Relevance Score:</strong> {{ article.relevance_score }}/100{% endif %}
            </div>
            
            {% if article.structured_analysis_html %}
            <div class="structured-analysis">
                {{ article.structured_analysis_html|safe }}
            </div>
            {% elif article.detailed_analysis_html %}
            <div class="markdown-analysis">
                {{ article.detailed_analysis_html|safe }}
            </div>
            {% elif article.detailed_analysis %}
            <div class="raw-analysis">
                <h4>Analysis</h4>
                <pre>{{ article.detailed_analysis }}</pre>
            </div>
            {% endif %}
            
            <div class="article-content">{{ article.content[:500] }}{% if article.content|length > 500 %}...{% endif %}</div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
        """

        # Convert markdown content to HTML with fallback for missing extensions
        try:
            analysis_html = markdown.markdown(
                report.analysis, extensions=["tables", "fenced_code"]
            )
        except ImportError as e:
            print(
                f"Warning: Markdown extension not available ({e}), using basic markdown conversion"
            )
            try:
                # Try with just fenced_code extension
                analysis_html = markdown.markdown(
                    report.analysis, extensions=["fenced_code"]
                )
            except ImportError:
                # Fallback to basic markdown without extensions
                analysis_html = markdown.markdown(report.analysis)

        # Process articles to add structured analysis HTML
        processed_articles = []
        for article in articles:
            processed_article = dict(article)

            # Convert detailed analysis JSON to HTML if available
            if article.get("detailed_analysis_json"):
                try:
                    import json

                    json_content = article["detailed_analysis_json"]

                    # Clean and parse the JSON content
                    cleaned_json = self._clean_json_content(json_content)
                    analysis_data = json.loads(cleaned_json)

                    # Check if this is a combined analysis with both article and insight analysis
                    if (
                        isinstance(analysis_data, dict)
                        and "article_analysis" in analysis_data
                        and "insight_analysis" in analysis_data
                    ):
                        # Combined analysis - parse both parts
                        article_json_text = analysis_data["article_analysis"]
                        insight_json_text = analysis_data["insight_analysis"]

                        # Parse article analysis
                        try:
                            article_data = json.loads(
                                self._clean_json_content(article_json_text)
                            )
                            article_html = self._json_to_html(article_data)
                        except json.JSONDecodeError:
                            article_html = "<div class='json-parse-error'><h4>Article Analysis Parse Error</h4></div>"

                        # Parse insight analysis (market intelligence)
                        try:
                            insight_data = json.loads(
                                self._clean_json_content(insight_json_text)
                            )
                            insight_html = self._insight_json_to_html(insight_data)
                        except json.JSONDecodeError:
                            insight_html = "<div class='json-parse-error'><h4>Market Intelligence Parse Error</h4></div>"

                        # Combine both HTML sections
                        processed_article["structured_analysis_html"] = (
                            article_html + insight_html
                        )
                    else:
                        # Single article analysis
                        processed_article["structured_analysis_html"] = (
                            self._json_to_html(analysis_data)
                        )
                except (json.JSONDecodeError, Exception) as e:
                    print(
                        f"Error parsing JSON analysis for {article.get('title', 'unknown')}: {e}"
                    )
                    # Create a fallback display that shows it's JSON but couldn't be parsed
                    processed_article["structured_analysis_html"] = (
                        f"<div class='json-parse-error'><h4>Analysis (JSON Parse Error)</h4><p><strong>Error:</strong> {str(e)}</p><pre style='background: #ffeeee; padding: 10px; border-radius: 5px; max-height: 300px; overflow-y: auto;'>{str(article.get('detailed_analysis_json', ''))}</pre></div>"
                    )

            # Convert markdown analysis to HTML if available
            elif article.get("detailed_analysis"):
                try:
                    processed_article["detailed_analysis_html"] = markdown.markdown(
                        article["detailed_analysis"],
                        extensions=["tables", "fenced_code"],
                    )
                except ImportError as e:
                    print(
                        f"Warning: Markdown extension not available ({e}), using basic markdown conversion"
                    )
                    try:
                        # Try with just fenced_code extension
                        processed_article["detailed_analysis_html"] = markdown.markdown(
                            article["detailed_analysis"], extensions=["fenced_code"]
                        )
                    except ImportError:
                        # Fallback to basic markdown without extensions
                        processed_article["detailed_analysis_html"] = markdown.markdown(
                            article["detailed_analysis"]
                        )

            processed_articles.append(processed_article)

        template = Template(template_str)
        html_content = template.render(
            report=report,
            articles=processed_articles,
            analysis_html=analysis_html,
            include_links=self.config.reporting.include_source_links,
        )

        with open(filepath, "w") as f:
            f.write(html_content)

    def _insight_json_to_html(self, insight_data):
        """Convert structured insight analysis JSON to formatted HTML."""
        try:
            html_parts = []

            # Add market intelligence header
            html_parts.append('<div class="market-intelligence-section">')
            html_parts.append(
                '<h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">Market Intelligence Analysis</h2>'
            )

            # Research Summary
            if "research_summary" in insight_data:
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Research Summary</h3>")
                html_parts.append(f'<p>{insight_data["research_summary"]}</p>')
                html_parts.append("</div>")

            # Comparable Cases
            if "comparable_cases" in insight_data:
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Comparable Cases</h3>")
                cases = insight_data["comparable_cases"]
                if isinstance(cases, list):
                    for i, case in enumerate(cases, 1):
                        if isinstance(case, dict):
                            html_parts.append(
                                f'<h4>{i}. {case.get("case_name", "Unknown Case")}</h4>'
                            )
                            html_parts.append("<ul>")
                            if case.get("similarity"):
                                html_parts.append(
                                    f'<li><strong>Similarity:</strong> {case["similarity"]}</li>'
                                )
                            if case.get("key_differences"):
                                html_parts.append(
                                    f'<li><strong>Key Differences:</strong> {case["key_differences"]}</li>'
                                )
                            if case.get("penalty_outcome"):
                                html_parts.append(
                                    f'<li><strong>Penalty/Outcome:</strong> {case["penalty_outcome"]}</li>'
                                )
                            if case.get("industry_reaction"):
                                html_parts.append(
                                    f'<li><strong>Industry Reaction:</strong> {case["industry_reaction"]}</li>'
                                )
                            html_parts.append("</ul>")
                html_parts.append("</div>")

            # Regulatory Intelligence
            if "regulatory_intelligence" in insight_data:
                reg_intel = insight_data["regulatory_intelligence"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Regulatory Intelligence</h3>")

                if isinstance(reg_intel, dict):
                    # Agency Guidance
                    if "agency_guidance" in reg_intel:
                        html_parts.append("<h4>Agency Guidance & Statements</h4>")
                        guidance_list = reg_intel["agency_guidance"]
                        if isinstance(guidance_list, list):
                            html_parts.append("<ul>")
                            for guidance in guidance_list:
                                if isinstance(guidance, dict):
                                    source = guidance.get("source", "Unknown")
                                    url = guidance.get("source_url", "")
                                    detail = guidance.get(
                                        "detail", guidance.get("details", "")
                                    )
                                    if url:
                                        html_parts.append(
                                            f'<li><strong><a href="{url}" target="_blank">{source}</a>:</strong> {detail}</li>'
                                        )
                                    else:
                                        html_parts.append(
                                            f"<li><strong>{source}:</strong> {detail}</li>"
                                        )
                            html_parts.append("</ul>")

                    # Congressional Activity
                    if "congressional_activity" in reg_intel:
                        html_parts.append("<h4>Congressional Activity</h4>")
                        activity_list = reg_intel["congressional_activity"]
                        if isinstance(activity_list, list):
                            html_parts.append("<ul>")
                            for activity in activity_list:
                                if isinstance(activity, dict):
                                    source = activity.get("source", "Unknown")
                                    url = activity.get("source_url", "")
                                    detail = activity.get(
                                        "detail", activity.get("details", "")
                                    )
                                    if url:
                                        html_parts.append(
                                            f'<li><strong><a href="{url}" target="_blank">{source}</a>:</strong> {detail}</li>'
                                        )
                                    else:
                                        html_parts.append(
                                            f"<li><strong>{source}:</strong> {detail}</li>"
                                        )
                            html_parts.append("</ul>")

                    # Industry Responses
                    if "industry_responses" in reg_intel:
                        html_parts.append("<h4>Industry Advisory Responses</h4>")
                        response_list = reg_intel["industry_responses"]
                        if isinstance(response_list, list):
                            html_parts.append("<ul>")
                            for response in response_list:
                                if isinstance(response, dict):
                                    source = response.get("source", "Unknown")
                                    url = response.get("source_url", "")
                                    detail = response.get(
                                        "detail", response.get("details", "")
                                    )
                                    if url:
                                        html_parts.append(
                                            f'<li><strong><a href="{url}" target="_blank">{source}</a>:</strong> {detail}</li>'
                                        )
                                    else:
                                        html_parts.append(
                                            f"<li><strong>{source}:</strong> {detail}</li>"
                                        )
                            html_parts.append("</ul>")

                html_parts.append("</div>")

            # Market Impact
            if "market_impact" in insight_data:
                market = insight_data["market_impact"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Market Impact</h3>")

                if isinstance(market, dict):
                    # Stock Market Response
                    if "stock_responses" in market:
                        html_parts.append("<h4>Stock Market Response</h4>")
                        responses = market["stock_responses"]
                        if isinstance(responses, list):
                            html_parts.append("<ul>")
                            for response in responses:
                                if isinstance(response, dict):
                                    source = response.get("source", "Unknown")
                                    url = response.get("source_url", "")
                                    if url:
                                        html_parts.append(
                                            f'<li><a href="{url}" target="_blank">{source}</a></li>'
                                        )
                                    else:
                                        html_parts.append(f"<li>{source}</li>")
                            html_parts.append("</ul>")

                    # Insurance & Risk
                    if "insurance_risk" in market:
                        html_parts.append("<h4>Insurance & Risk Mitigation</h4>")
                        risks = market["insurance_risk"]
                        if isinstance(risks, list):
                            html_parts.append("<ul>")
                            for risk in risks:
                                if isinstance(risk, dict):
                                    source = risk.get("source", "Unknown")
                                    url = risk.get("source_url", "")
                                    if url:
                                        html_parts.append(
                                            f'<li><a href="{url}" target="_blank">{source}</a></li>'
                                        )
                                    else:
                                        html_parts.append(f"<li>{source}</li>")
                            html_parts.append("</ul>")

                    # Compliance Market
                    if "compliance_market" in market:
                        html_parts.append("<h4>Compliance Market Response</h4>")
                        compliance = market["compliance_market"]
                        if isinstance(compliance, list):
                            html_parts.append("<ul>")
                            for item in compliance:
                                if isinstance(item, dict):
                                    source = item.get("source", "Unknown")
                                    url = item.get("source_url", "")
                                    if url:
                                        html_parts.append(
                                            f'<li><a href="{url}" target="_blank">{source}</a></li>'
                                        )
                                    else:
                                        html_parts.append(f"<li>{source}</li>")
                            html_parts.append("</ul>")

                html_parts.append("</div>")

            # Strategic Insights
            if "insights" in insight_data:
                insights = insight_data["insights"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Strategic Insights</h3>")

                if isinstance(insights, dict):
                    # Enforcement Trends
                    if "enforcement_trends" in insights:
                        html_parts.append("<h4>Enforcement Trends</h4>")
                        trends = insights["enforcement_trends"]
                        if isinstance(trends, list):
                            html_parts.append("<ul>")
                            for trend in trends:
                                if isinstance(trend, dict):
                                    html_parts.append(
                                        f'<li><strong>{trend.get("trend", "Unknown")}:</strong> {trend.get("detail", "")}</li>'
                                    )
                            html_parts.append("</ul>")

                    # Predictions
                    if "predictions" in insights:
                        html_parts.append("<h4>Predictions</h4>")
                        predictions = insights["predictions"]
                        if isinstance(predictions, list):
                            html_parts.append("<ul>")
                            for prediction in predictions:
                                if isinstance(prediction, dict):
                                    html_parts.append(
                                        f'<li><strong>{prediction.get("trend", "Unknown")}:</strong> {prediction.get("detail", "")}</li>'
                                    )
                            html_parts.append("</ul>")

                    # Strategic Implications
                    if "strategic_implications" in insights:
                        html_parts.append("<h4>Strategic Implications</h4>")
                        implications = insights["strategic_implications"]
                        if isinstance(implications, list):
                            html_parts.append("<ul>")
                            for implication in implications:
                                if isinstance(implication, dict):
                                    html_parts.append(
                                        f'<li><strong>{implication.get("trend", "Unknown")}:</strong> {implication.get("detail", "")}</li>'
                                    )
                            html_parts.append("</ul>")

                html_parts.append("</div>")

            html_parts.append("</div>")  # Close market-intelligence-section

            return "\n".join(html_parts)

        except Exception as e:
            return f'<div class="analysis-section"><h3>Market Intelligence</h3><p class="error">Error formatting market intelligence: {str(e)}</p></div>'

    def _json_to_html(self, analysis_data):
        """Convert structured JSON analysis to formatted HTML."""
        try:
            html_parts = []

            # Analysis Metadata
            if "analysis_metadata" in analysis_data:
                metadata = analysis_data["analysis_metadata"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Analysis Overview</h3>")
                html_parts.append(
                    f'<p><strong>Relevance Score:</strong> {metadata.get("relevance_score", "N/A")}/10</p>'
                )

                if metadata.get("practice_areas"):
                    html_parts.append(
                        f'<p><strong>Practice Areas:</strong> {", ".join(metadata["practice_areas"])}</p>'
                    )
                html_parts.append("</div>")

            # Case Overview
            if "case_overview" in analysis_data:
                overview = analysis_data["case_overview"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Case Overview</h3>")
                if overview.get("summary"):
                    html_parts.append(
                        f'<p><strong>Summary:</strong> {overview["summary"]}</p>'
                    )
                if overview.get("significance"):
                    html_parts.append(
                        f'<p><strong>Significance:</strong> {overview["significance"]}</p>'
                    )
                html_parts.append("</div>")

            # Fact Pattern
            if "fact_pattern" in analysis_data:
                fact_pattern = analysis_data["fact_pattern"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Fact Pattern</h3>")

                if fact_pattern.get("parties"):
                    html_parts.append("<p><strong>Key Parties:</strong></p>")
                    html_parts.append("<ul>")
                    for party in fact_pattern["parties"]:
                        html_parts.append(f"<li>{party}</li>")
                    html_parts.append("</ul>")

                if fact_pattern.get("misconduct_details"):
                    html_parts.append(
                        f'<p><strong>Misconduct Details:</strong> {fact_pattern["misconduct_details"]}</p>'
                    )

                if fact_pattern.get("legal_framework"):
                    html_parts.append("<p><strong>Legal Framework:</strong></p>")
                    html_parts.append("<ul>")
                    for law in fact_pattern["legal_framework"]:
                        html_parts.append(f"<li>{law}</li>")
                    html_parts.append("</ul>")
                html_parts.append("</div>")

            # Legal Analysis
            if "legal_analysis" in analysis_data:
                legal = analysis_data["legal_analysis"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Legal Analysis</h3>")

                if legal.get("enforcement_trends"):
                    html_parts.append(
                        f'<p><strong>Enforcement Trends:</strong> {legal["enforcement_trends"]}</p>'
                    )

                if legal.get("whistleblower_analysis"):
                    html_parts.append(
                        f'<p><strong>Whistleblower Analysis:</strong> {legal["whistleblower_analysis"]}</p>'
                    )
                html_parts.append("</div>")

            # Blog Outline
            if "blog_outline" in analysis_data:
                blog = analysis_data["blog_outline"]
                html_parts.append('<div class="analysis-section">')
                html_parts.append("<h3>Blog Outline</h3>")

                if blog.get("compelling_hooks"):
                    html_parts.append("<p><strong>Compelling Hooks:</strong></p>")
                    html_parts.append("<ul>")
                    for hook in blog["compelling_hooks"]:
                        html_parts.append(f"<li>{hook}</li>")
                    html_parts.append("</ul>")

                if blog.get("practical_takeaways"):
                    html_parts.append("<p><strong>Practical Takeaways:</strong></p>")
                    html_parts.append("<ul>")
                    for takeaway in blog["practical_takeaways"]:
                        html_parts.append(f"<li>{takeaway}</li>")
                    html_parts.append("</ul>")
                html_parts.append("</div>")

            return "".join(html_parts)

        except Exception as e:
            print(f"Error converting JSON to HTML: {e}")
            return f"<p>Error displaying structured analysis: {str(e)}</p>"

    def _generate_markdown(self, report: Report, articles: List[Dict], filepath: Path):
        """Generate Markdown report."""
        markdown_content = f"""# {report.title}

## Report Metadata
- **Report Date**: {report.start_date.strftime('%B %d, %Y')}
- **Articles Analyzed**: {report.article_count}
- **AI Tokens Used**: {report.tokens_used}

"""

        if report.summary:
            markdown_content += f"""### Executive Summary

{report.summary}

---

"""

        markdown_content += f"""{report.analysis}"""

        with open(filepath, "w") as f:
            f.write(markdown_content)

    def _get_report_articles(self, db, report_id: int) -> List[Dict]:
        """Get articles associated with a report."""
        from sqlalchemy.orm import joinedload
        from ..database.models import ReportArticle

        report = (
            db.query(Report)
            .options(
                joinedload(Report.report_articles)
                .joinedload(ReportArticle.article)
                .joinedload(Article.source)
            )
            .filter_by(id=report_id)
            .first()
        )

        articles = []
        for report_article in report.report_articles:
            article = report_article.article
            articles.append(
                {
                    "id": article.id,
                    "title": article.title,
                    "content": article.content,
                    "url": article.url,
                    "published_date": article.published_date,
                    "author": article.author,
                    "category": article.category,
                    "source_name": (
                        article.source.name if article.source else "Unknown Source"
                    ),
                    "word_count": article.word_count,
                    "relevance_score": article.relevance_score,
                    "practice_areas": article.practice_areas,
                    "dollar_amount": article.dollar_amount,
                    "whistleblower_indicators": article.whistleblower_indicators,
                    "blog_potential": article.blog_potential,
                    "relevance_summary": article.relevance_summary,
                    "detailed_analysis": article.detailed_analysis,
                    "detailed_analysis_json": article.detailed_analysis_json,
                    "detailed_analysis_tokens": article.detailed_analysis_tokens,
                    "detailed_analysis_at": article.detailed_analysis_at,
                }
            )

        return sorted(articles, key=lambda x: x["published_date"], reverse=True)

    def _generate_pdf(self, report: Report, articles: List[Dict], filepath: Path):
        """Generate PDF report with professional formatting and improved structure."""
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        # Define styles using Times-Roman 12pt
        styles = getSampleStyleSheet()

        # Custom styles for better typography
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Times-Bold",
            fontSize=18,
            spaceAfter=24,
            alignment=TA_CENTER,
        )

        heading_style = ParagraphStyle(
            "Heading",
            parent=styles["Heading1"],
            fontName="Times-Bold",
            fontSize=16,  # Larger for main headings
            spaceAfter=6,  # Reduced spacing
            spaceBefore=12,  # Reduced spacing
            textColor=black,
        )

        subheading_style = ParagraphStyle(
            "SubHeading",
            parent=styles["Heading2"],
            fontName="Times-Bold",
            fontSize=14,  # Medium for subheadings
            spaceAfter=4,  # Reduced spacing
            spaceBefore=8,  # Reduced spacing
            textColor=black,
        )

        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=12,  # Base font size as requested
            spaceAfter=3,  # Reduced spacing
            alignment=TA_JUSTIFY,
            leftIndent=0,
            rightIndent=0,
        )

        bullet_style = ParagraphStyle(
            "Bullet",
            parent=body_style,
            leftIndent=36,
            bulletIndent=18,
            bulletFontName="Times-Roman",
            bulletFontSize=12,
            spaceAfter=2,  # Reduced spacing for bullets
        )

        # Legal numbering styles with proper hanging indents
        legal_level1_style = ParagraphStyle(
            "LegalLevel1",
            parent=body_style,
            leftIndent=24,  # Total left margin
            firstLineIndent=-12,  # Negative indent for hanging effect
            spaceAfter=3,
        )

        legal_level2_style = ParagraphStyle(
            "LegalLevel2",
            parent=body_style,
            leftIndent=36,  # More indented than level 1
            firstLineIndent=-12,  # Negative indent for hanging effect
            spaceAfter=2,
        )

        legal_level3_style = ParagraphStyle(
            "LegalLevel3",
            parent=body_style,
            leftIndent=48,  # More indented than level 2
            firstLineIndent=-12,  # Negative indent for hanging effect
            spaceAfter=2,
        )

        legal_level4_style = ParagraphStyle(
            "LegalLevel4",
            parent=body_style,
            leftIndent=60,  # More indented than level 3 (was 90, now 60)
            firstLineIndent=-12,  # Negative indent for hanging effect
            spaceAfter=2,
        )

        # TOC style for clickable links
        toc_style = ParagraphStyle(
            "TOC", parent=body_style, fontSize=12, spaceAfter=2, leftIndent=0
        )

        toc_sub_style = ParagraphStyle(
            "TOCSub", parent=body_style, fontSize=11, spaceAfter=1, leftIndent=20
        )

        toc_subsub_style = ParagraphStyle(
            "TOCSubSub", parent=body_style, fontSize=10, spaceAfter=1, leftIndent=40
        )

        link_style = ParagraphStyle(
            "Link", parent=body_style, textColor=blue, underline=1
        )

        metadata_style = ParagraphStyle(
            "Metadata",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=11,  # Slightly smaller than body text
            spaceAfter=2,  # Reduced spacing
            textColor=black,
        )

        article_info_style = ParagraphStyle(
            "ArticleInfo",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=12,  # Same as body text
            spaceAfter=2,  # Reduced spacing
            textColor=black,
        )

        # Build the story (content)
        story = []

        # Validate detailed analysis data availability
        validation = self._validate_detailed_analysis_data(articles)
        if validation["validation_errors"]:
            print("Validation warnings:")
            for error in validation["validation_errors"]:
                print(f"   {error}")

        print(f"PDF summary:")
        print(f"   Total articles: {validation['total_articles']}")
        print(f"   High priority articles: {validation['high_priority_count']}")
        print(f"   With cached analysis: {validation['cached_analysis_count']}")
        print(f"   Missing analysis: {validation['missing_analysis_count']}")

        # Get articles with detailed analysis based on report's high_priority_only flag
        articles_with_analysis = []
        
        # Use the report's stored flag to determine which articles to include
        if report.high_priority_only:
            # Include only high priority articles (score >= 80) with detailed analysis
            score_threshold = 80
        else:
            # Include all relevant articles (score >= 50) with detailed analysis
            score_threshold = 50
        
        for article in articles:
            if (article.get("relevance_score") and article["relevance_score"] >= score_threshold and
                (article.get("detailed_analysis") or article.get("detailed_analysis_json"))):
                # Parse practice_areas from JSON string if it exists
                practice_areas = article.get("practice_areas")
                if practice_areas:
                    try:
                        import json

                        practice_areas = json.loads(practice_areas)
                        if isinstance(practice_areas, list):
                            practice_areas = ", ".join(practice_areas)
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, use as-is
                        pass

                articles_with_analysis.append(
                    {
                        "title": article["title"],
                        "url": article["url"],
                        "published_date": self._format_local_date(article["published_date"], "%B %d, %Y"),
                        "score": article["relevance_score"],
                        "dollar_amount": article.get("dollar_amount"),
                        "practice_areas": practice_areas,
                        "whistleblower_indicators": article.get(
                            "whistleblower_indicators"
                        ),
                        "detailed_analysis": article.get("detailed_analysis", ""),
                        "detailed_analysis_json": article.get(
                            "detailed_analysis_json", ""
                        ),
                    }
                )
        
        # Sort by relevance score (highest first)
        articles_with_analysis.sort(key=lambda x: x["score"], reverse=True)

        # === FIRST PAGE ===
        story.append(Paragraph(report.title, title_style))
        story.append(Spacer(1, 0.15 * inch))  # Reduced spacing

        # Table of Contents with clickable links
        toc_entries = self._generate_table_of_contents(report, articles_with_analysis)
        if toc_entries:
            story.append(Paragraph("Table of Contents", heading_style))
            for entry in toc_entries:
                if entry.startswith("      "):  # Double-indented (article subsections)
                    story.append(Paragraph(entry, toc_subsub_style))
                elif entry.startswith(
                    "   "
                ):  # Single-indented (articles under overview)
                    story.append(Paragraph(entry, toc_sub_style))
                else:  # Main section
                    story.append(Paragraph(entry, toc_style))
            story.append(Spacer(1, 0.1 * inch))  # Reduced spacing

        # Report metadata with bookmark
        story.append(
            Paragraph('<a name="report_metadata"/>Report Metadata', heading_style)
        )
        story.append(
            Paragraph(
                f"<b>Report Date:</b> {report.start_date.strftime('%B %d, %Y')}",
                metadata_style,
            )
        )
        story.append(
            Paragraph(
                f"<b>Articles Analyzed:</b> {report.article_count}", metadata_style
            )
        )
        story.append(
            Paragraph(f"<b>AI Tokens Used:</b> {report.tokens_used:,}", metadata_style)
        )
        story.append(Spacer(1, 0.1 * inch))  # Reduced spacing

        # Summary - Keep on first page with bookmark
        if report.summary:
            story.append(
                Paragraph('<a name="executive_summary"/>Summary', heading_style)
            )
            story.append(
                Paragraph(self._clean_text_for_pdf(report.summary), body_style)
            )
            story.append(Spacer(1, 0.1 * inch))  # Reduced spacing

        # Articles with Detailed Analysis List with links and bookmark
        if articles_with_analysis:
            # Determine the section title based on report's high_priority_only flag
            if report.high_priority_only:
                section_title = "High Priority Articles"
                description = "The following articles scored ≥80 and include detailed blog post outlines:"
            else:
                section_title = "Analyzed Articles"
                description = "The following articles scored ≥50 and include detailed blog post outlines:"
            
            story.append(
                Paragraph(
                    f'<a name="analyzed_articles"/>{section_title}',
                    heading_style,
                )
            )
            story.append(
                Paragraph(
                    description,
                    body_style,
                )
            )
            story.append(Spacer(1, 0.05 * inch))  # Reduced spacing

            for i, article_info in enumerate(articles_with_analysis, 1):
                title = article_info["title"]
                url = article_info["url"]
                score = article_info["score"]
                link_text = f"<b>{i}.</b> <link href='{url}' color='blue'>{self._clean_text_for_pdf(title)}</link> (Score: {score})"
                story.append(Paragraph(link_text, legal_level1_style))

            story.append(Spacer(1, 0.1 * inch))
            story.append(
                Paragraph(
                    "Detailed analysis of each article begins on the next page.",
                    body_style,
                )
            )

        # Page break before detailed articles
        story.append(PageBreak())

        # === DETAILED ARTICLE PAGES ===
        for i, article_info in enumerate(articles_with_analysis):
            if i > 0:  # Page break before each article except the first
                story.append(PageBreak())

            # Article title with embedded link and bookmark
            title = article_info["title"]
            url = article_info["url"]
            article_id = f"article_{i+1}"
            title_with_link = f'<a name="{article_id}"/><link href="{url}" color="blue">{self._clean_text_for_pdf(title)}</link>'
            story.append(Paragraph(title_with_link, subheading_style))
            story.append(Spacer(1, 0.05 * inch))  # Reduced spacing

            # Article information section
            story.append(Paragraph("Article Information", heading_style))
            story.append(
                Paragraph(
                    f"<b>Source Link:</b> <link href='{url}' color='blue'>{url}</link>",
                    article_info_style,
                )
            )
            story.append(
                Paragraph(
                    f"<b>Relevance Score:</b> {article_info['score']}/100",
                    article_info_style,
                )
            )

            if article_info.get("published_date"):
                story.append(
                    Paragraph(
                        f"<b>Publication Date:</b> {article_info['published_date']}",
                        article_info_style,
                    )
                )

            if article_info.get("dollar_amount"):
                story.append(
                    Paragraph(
                        f"<b>Dollar Amount:</b> {article_info['dollar_amount']}",
                        article_info_style,
                    )
                )

            if article_info.get("practice_areas"):
                practice_areas = article_info["practice_areas"]
                # If it's already a string (from JSON parsing), use as-is. If it's a list, join it.
                if isinstance(practice_areas, list):
                    practice_areas_text = ", ".join(practice_areas)
                else:
                    practice_areas_text = str(practice_areas)
                story.append(
                    Paragraph(
                        f"<b>Practice Areas:</b> {self._clean_text_for_pdf(practice_areas_text)}",
                        article_info_style,
                    )
                )

            if article_info.get("whistleblower_indicators"):
                story.append(
                    Paragraph(
                        f"<b>Whistleblower Elements:</b> {article_info['whistleblower_indicators']}",
                        article_info_style,
                    )
                )

            story.append(Spacer(1, 0.1 * inch))  # Reduced spacing

            # Detailed blog outline
            detailed_analysis_json = article_info.get("detailed_analysis_json")
            detailed_analysis = article_info.get("detailed_analysis")

            # Prefer JSON if available, otherwise use markdown
            if detailed_analysis_json:
                print(f"Using JSON: {article_info['title']}...")
                self._render_json_analysis_to_pdf(
                    detailed_analysis_json,
                    story,
                    heading_style,
                    subheading_style,
                    body_style,
                    bullet_style,
                    legal_level1_style,
                    legal_level2_style,
                    legal_level3_style,
                    legal_level4_style,
                    article_id,
                )
            elif detailed_analysis:
                print(f"Using markdown: {article_info['title']}...")
                # Parse and add the detailed analysis using existing markdown parser
                self._render_markdown_analysis_to_pdf(
                    detailed_analysis,
                    story,
                    heading_style,
                    subheading_style,
                    body_style,
                    bullet_style,
                    article_id,
                    i,
                )
            else:
                # Fallback: if no cached detailed analysis, try extracting from report text
                print(f"No cache: {article_info['title']}...")
                detailed_analysis = self._extract_detailed_analysis_for_article(
                    report.analysis, article_info["title"]
                )
                if detailed_analysis:
                    self._render_markdown_analysis_to_pdf(
                        detailed_analysis,
                        story,
                        heading_style,
                        subheading_style,
                        body_style,
                        bullet_style,
                        article_id,
                        i,
                    )

        # === APPENDIX ===
        if (
            articles_with_analysis
        ):  # Only add page break if we had articles with analysis
            story.append(PageBreak())

        # Add medium and lower priority articles appendix from original analysis
        appendix_content = self._extract_appendix_content(report.analysis)
        if appendix_content:
            story.append(Paragraph("Article Review Appendix", heading_style))
            self._parse_appendix_to_pdf(
                appendix_content,
                story,
                heading_style,
                subheading_style,
                body_style,
                bullet_style,
                legal_level1_style,
            )

        # Build the PDF with error handling
        try:
            print(f"Building PDF with {len(story)} elements...")
            doc.build(story)
            print("PDF built successfully!")
        except Exception as e:
            print(f"Error building PDF: {e}")
            # Try to build with just the basic content (first few elements)
            try:
                # Build with just title, TOC, and metadata (safe content)
                safe_story = story[:10]  # First 10 elements should be safe
                print(f"Attempting safe build with {len(safe_story)} elements...")
                doc.build(safe_story)
                print("Safe PDF build completed!")
            except Exception as e2:
                print(f"Even safe build failed: {e2}")
                raise e  # Re-raise original error

    def _parse_markdown_to_pdf(
        self,
        markdown_text: str,
        story: list,
        heading_style,
        subheading_style,
        body_style,
        bullet_style,
    ):
        """Parse markdown content and add appropriate PDF elements with page breaks."""
        lines = markdown_text.split("\n")
        in_high_priority = False
        article_count = 0

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Track when we enter high priority articles section
            if "High Priority Articles" in line:
                in_high_priority = True
                story.append(Paragraph(self._clean_text_for_pdf(line), heading_style))
                continue

            # Track when we leave high priority articles
            if "All Articles Reviewed" in line:
                in_high_priority = False
                if (
                    article_count > 0
                ):  # Add page break before appendix if we had high priority articles
                    story.append(PageBreak())
                story.append(Paragraph(self._clean_text_for_pdf(line), heading_style))
                continue

            # Handle different markdown elements
            if line.startswith("### ") and any(char.isdigit() for char in line[:10]):
                # This is likely an article title (### 1. Article Title)
                if in_high_priority and article_count > 0:
                    # Add page break before each new high priority article (except the first)
                    story.append(PageBreak())
                article_count += 1

                title_text = line[4:].strip()  # Remove ### and space
                story.append(
                    Paragraph(self._clean_text_for_pdf(title_text), subheading_style)
                )

            elif line.startswith("## "):
                # Major section headers
                header_text = line[3:].strip()
                story.append(
                    Paragraph(self._clean_text_for_pdf(header_text), heading_style)
                )

            elif line.startswith("### "):
                # Sub-section headers
                header_text = line[4:].strip()
                story.append(
                    Paragraph(self._clean_text_for_pdf(header_text), subheading_style)
                )

            elif line.startswith("#### "):
                # Sub-sub-section headers
                header_text = line[5:].strip()
                story.append(
                    Paragraph(
                        f"<b>{self._clean_text_for_pdf(header_text)}</b>", body_style
                    )
                )

            elif line.startswith("- ") or line.startswith("* "):
                # Bullet points
                bullet_text = line[2:].strip()
                story.append(
                    Paragraph(
                        f"• {self._clean_text_for_pdf(bullet_text)}", bullet_style
                    )
                )

            elif line.startswith("**") and line.endswith("**"):
                # Bold standalone lines
                bold_text = line[2:-2]
                story.append(
                    Paragraph(
                        f"<b>{self._clean_text_for_pdf(bold_text)}</b>", body_style
                    )
                )

            elif line.startswith("---"):
                # Horizontal rules - add some space
                story.append(Spacer(1, 0.1 * inch))

            elif line and not line.startswith("#"):
                # Regular text paragraphs
                story.append(Paragraph(self._clean_text_for_pdf(line), body_style))

    def _clean_text_for_pdf(self, text: str) -> str:
        """Clean and format text for PDF generation."""
        import re

        if not text:
            return ""

        # Normalize Unicode characters to ASCII equivalents for better PDF compatibility
        text = self._normalize_unicode_for_pdf(text)

        # Convert markdown bold to HTML bold
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)

        # Convert markdown italic to HTML italic
        text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)

        # Convert markdown links to HTML links with blue color
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="blue">\1</link>', text
        )

        # Handle multiple source citations - convert to proper links
        def format_multiple_sources(match):
            sources_text = match.group(1)
            # Split by comma and format each source
            sources = sources_text.split(", ")
            formatted_sources = []
            for source in sources:
                if ":" in source and "http" in source:
                    parts = source.split(": ", 1)
                    if len(parts) == 2:
                        name, url = parts
                        formatted_sources.append(
                            f'<link href="{url.strip()}" color="blue">{name.strip()}</link>'
                        )
                    else:
                        formatted_sources.append(source)
                else:
                    formatted_sources.append(source)
            return "[" + ", ".join(formatted_sources) + "]"

        # Apply multiple source formatting
        text = re.sub(r"\[([^]]*https?://[^]]*)\]", format_multiple_sources, text)

        # First, preserve our HTML tags temporarily
        import uuid

        tag_placeholders = {}

        # Preserve link tags completely
        def preserve_tag(match):
            placeholder = f"TAGPRESERVE{uuid.uuid4().hex[:8]}"
            tag_placeholders[placeholder] = match.group(0)
            return placeholder

        text = re.sub(r"<link[^>]*>.*?</link>", preserve_tag, text)
        text = re.sub(r"<b>.*?</b>", preserve_tag, text)
        text = re.sub(r"<i>.*?</i>", preserve_tag, text)

        # Now escape problematic characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;").replace(">", "&gt;")

        # Restore preserved tags
        for placeholder, original_tag in tag_placeholders.items():
            text = text.replace(placeholder, original_tag)

        return text

    def _normalize_unicode_for_pdf(self, text: str) -> str:
        """Normalize Unicode characters to ASCII equivalents for better PDF compatibility."""
        if not text:
            return text

        # Dictionary of Unicode characters to ASCII replacements
        unicode_replacements = {
            "\u2011": "-",  # Non-breaking hyphen → regular hyphen
            "\u2012": "-",  # Figure dash → regular hyphen
            "\u2013": "-",  # En dash → regular hyphen
            "\u2014": "--",  # Em dash → double hyphen
            "\u2015": "--",  # Horizontal bar → double hyphen
            "\u2018": "'",  # Left single quotation mark → apostrophe
            "\u2019": "'",  # Right single quotation mark → apostrophe
            "\u201A": "'",  # Single low-9 quotation mark → apostrophe
            "\u201B": "'",  # Single high-reversed-9 quotation mark → apostrophe
            "\u201C": '"',  # Left double quotation mark → quote
            "\u201D": '"',  # Right double quotation mark → quote
            "\u201E": '"',  # Double low-9 quotation mark → quote
            "\u201F": '"',  # Double high-reversed-9 quotation mark → quote
            "\u2026": "...",  # Horizontal ellipsis → three dots
            "\u2032": "'",  # Prime → apostrophe
            "\u2033": '"',  # Double prime → quote
            "\u2039": "<",  # Single left-pointing angle quotation mark
            "\u203A": ">",  # Single right-pointing angle quotation mark
            "\u00A0": " ",  # Non-breaking space → regular space
            "\u00AD": "",  # Soft hyphen → remove
        }

        # Apply replacements
        for unicode_char, replacement in unicode_replacements.items():
            text = text.replace(unicode_char, replacement)

        return text

    def _clean_unreachable_code_placeholder(self):
        """Placeholder method - the code below was unreachable after return statement."""
        # Fix spacing issues where relevance levels are concatenated with text
        text = re.sub(r"\b(HIGH|MEDIUM|LOW)([a-z])", r"\1 \2", text)

        # Fix doubled quotes before processing attribution - handle multiple patterns
        # More aggressive fix for doubled quotes in any context including numbered lists
        text = re.sub(r'""([^"]*?)""', r'"\1"', text)

        # First handle quote attribution formatting for clean quotes
        def format_quote_attribution(match):
            quote = match.group(1)
            attribution = match.group(2).strip()

            # Remove existing quotes from quote text since we'll italicize it
            quote_text = quote.strip("\"'")

            # Remove existing dashes if present
            if attribution.startswith("--"):
                attribution = attribution[2:].strip()
            elif attribution.startswith("-"):
                attribution = attribution[1:].strip()

            return f'<i>"{quote_text}"</i> --{attribution}'

        # Apply quote formatting - simple pattern for numbered lists
        text = re.sub(
            r'(\d+\.\s*")([^"]+)"(\s*--[^"]*?)(?=\d+\.\s*"|$)', r"\1<i>\2</i>\3", text
        )
        # Standard pattern for quote + attribution
        text = re.sub(
            r'("([^"]+)")(\s*--[A-Z][^"]*?)(?=\d+\.\s*"|$)',
            format_quote_attribution,
            text,
        )

        # Preserve existing ReportLab link tags by temporarily replacing them

        def preserve_existing_links(match):
            import re

            placeholder = f"PRESERVELINK_{uuid.uuid4().hex[:8]}"
            original_link = match.group(0)
            # Fix spacing issues within the link tag itself
            fixed_link = re.sub(r"'color='blue'>", r"' color='blue'>", original_link)
            fixed_link = re.sub(r'"color="blue">', r'" color="blue">', fixed_link)
            link_preservation[placeholder] = fixed_link
            return placeholder

        # Preserve existing <link> tags before any processing
        text = re.sub(r"<link[^>]*>.*?</link>", preserve_existing_links, text)

        # Fix spacing issues around punctuation and parentheses
        # Fix missing space before opening parenthesis
        text = re.sub(r"\.(\()", r". \1", text)
        text = re.sub(r"(\w)(\()", r"\1 \2", text)

        # Fix common word concatenation issues
        text = re.sub(r"\bandCFTC\b", "and CFTC", text)
        text = re.sub(r"\bjointsettlements\b", "joint settlements", text)
        text = re.sub(r"\bhaveexpanded\b", "have expanded", text)
        text = re.sub(r"\bdeadlyopioid\b", "deadly opioid", text)
        text = re.sub(r"\bthedevastating\b", "the devastating", text)
        text = re.sub(r"\bhavea\b", "have a", text)
        text = re.sub(r"\baresponsibility\b", "a responsibility", text)
        text = re.sub(
            r"\bofColumbia\d+\b", "of Columbia ", text
        )  # Fix spacing before numbers
        text = re.sub(r"\ballegedin\b", "alleged in", text)
        text = re.sub(
            r"\bDivision\d+\b", "Division ", text
        )  # Fix spacing after Division

        # Fix spacing around numbered list items that got concatenated
        text = re.sub(r'(\.\s*"[^"]*"\s*--[^"]*?)(\d+\.\s*")', r"\1\n\n\2", text)

        # Quote formatting is now handled above before link preservation

        # Replace markdown bold/italic with HTML tags for ReportLab
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)

        # Handle markdown links [text](url) -> placeholders FIRST to avoid escaping issues
        import uuid

        link_placeholders = {}

        def convert_markdown_link(match):
            link_text = match.group(1)
            url = match.group(2)
            placeholder = f"LINKPLACEHOLDER_{uuid.uuid4().hex[:8]}"
            link_tag = f'<link href="{url}" color="blue">{link_text}</link>'
            link_placeholders[placeholder] = link_tag
            return placeholder

        # Convert markdown links to placeholders before any character removal or escaping
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", convert_markdown_link, text)

        # Convert plain URLs to hyperlinks
        def convert_plain_url(match):
            url = match.group(1)
            placeholder = f"LINKPLACEHOLDER_{uuid.uuid4().hex[:8]}"
            link_tag = f'<link href="{url}" color="blue">{url}</link>'
            link_placeholders[placeholder] = link_tag
            return placeholder

        # Match URLs that aren't already in markdown format - be more precise about ending
        text = re.sub(
            r'(?<!\()(https?://[^\s<>"{}|\\^`\[\]\n\r]+)', convert_plain_url, text
        )

        # Now remove problematic characters (but preserve our placeholders)
        # Don't remove characters that are part of our link placeholders
        text = re.sub(r'[^\w\s\-.,;:!?()[\]{}\'"/\\&$%@#+*=<>|_]', "", text)

        # Now escape HTML characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;").replace(">", "&gt;")

        # Restore bold and italic tags
        text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")

        # Restore link tags from placeholders
        for placeholder, link_tag in link_placeholders.items():
            text = text.replace(placeholder, link_tag)

        # Restore preserved existing link tags
        for placeholder, link_tag in link_preservation.items():
            text = text.replace(placeholder, link_tag)

        return text

    def _clean_url_for_link(self, url: str) -> str:
        """Clean URL for use in PDF links, removing trailing quotes and whitespace."""
        import re

        if not url:
            return ""
        # Remove any trailing quotes, brackets, or other non-URL characters
        cleaned = str(url).strip()
        # Remove trailing punctuation that's not part of the URL
        cleaned = re.sub(r'[\'"\]\)]+$', "", cleaned)
        return cleaned.strip()

    def _extract_detailed_analysis_for_article(
        self, analysis_content: str, article_title: str
    ) -> str:
        """Extract the detailed analysis content for a specific article from the full analysis."""
        lines = analysis_content.split("\n")

        in_high_priority = False
        in_target_article = False
        in_detailed_analysis = False
        detailed_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Check if we're entering high priority section
            if "High Priority Articles" in line_stripped:
                in_high_priority = True
                continue

            # Check if we're leaving high priority section
            if (
                "All Articles Reviewed" in line_stripped
                or "## All Articles" in line_stripped
            ):
                break

            if not in_high_priority:
                continue

            # Look for the specific article title
            import re

            if line_stripped.startswith("### ") and re.match(
                r"### \d+\. ", line_stripped
            ):
                # Extract title without number prefix
                line_title = line_stripped[4:].strip()
                if ". " in line_title:
                    line_title = line_title.split(". ", 1)[1]

                if line_title == article_title:
                    in_target_article = True
                    continue
                elif in_target_article:
                    # We've moved to a different article, stop collecting
                    break

            # Start collecting detailed analysis content
            if in_target_article:
                if "#### Detailed Analysis & Blog Outline" in line_stripped:
                    in_detailed_analysis = True
                    # Skip the header line itself, start collecting from next line
                    continue
                elif in_detailed_analysis:
                    detailed_lines.append(line)

        return "\n".join(detailed_lines)

    def _validate_detailed_analysis_data(self, articles: List[Dict]) -> Dict[str, Any]:
        """Validate that detailed analysis data is properly available for high-priority articles."""
        validation_results = {
            "total_articles": len(articles),
            "high_priority_count": 0,
            "cached_analysis_count": 0,
            "missing_analysis_count": 0,
            "validation_errors": [],
        }

        for article in articles:
            if article.get("relevance_score", 0) >= 80:
                validation_results["high_priority_count"] += 1

                if article.get("detailed_analysis"):
                    validation_results["cached_analysis_count"] += 1
                else:
                    validation_results["missing_analysis_count"] += 1
                    validation_results["validation_errors"].append(
                        f"Missing detailed analysis for high-priority article: {article.get('title', 'Unknown')}..."
                    )

        return validation_results

    def _is_formatting_note(self, line: str) -> bool:
        """Check if a line is a formatting note that should be filtered out."""
        line_lower = line.lower().strip()

        # List of patterns that indicate formatting notes
        formatting_patterns = [
            "pdf-ready formatting note",
            "this analysis is structured for pdf",
            "for pdf layout",
            "law firm client distribution",
            "prepared for law firm distribution",
            "for further information, contact your regulatory compliance counsel",
            "contact your regulatory compliance counsel",
            "for further details or to access",
            "visit the doj press release",
            "for additional information",
            "this document is formatted",
            "structured for professional distribution",
            "contact the firm for",
            "disclaimer:",
            "note: this analysis",
            "pdf formatting",
            "layout note",
            "distribution note",
            "formatting note",
            "authors of this analysis",
            "fact-checking protocol",
            "fact checking protocol",
        ]

        # Check if line contains any formatting patterns
        for pattern in formatting_patterns:
            if pattern in line_lower:
                return True

        # Check for lines that look like footer notes or disclaimers
        if (
            line_lower.startswith("note:")
            or line_lower.startswith("disclaimer:")
            or line_lower.startswith("for further")
            or line_lower.startswith("this document")
            or line_lower.startswith("formatting note:")
            or line_lower.startswith("this analysis")
            and ("structured" in line_lower or "formatted" in line_lower)
        ):
            return True

        return False

    def _extract_high_priority_articles(self, analysis_content: str) -> List[Dict]:
        """Extract high priority article information from the analysis content."""
        # NOTE: This method is deprecated in favor of querying database directly
        # Kept for backwards compatibility if needed
        articles = []
        lines = analysis_content.split("\n")

        current_article = None
        in_high_priority = False
        in_detailed_analysis = False
        detailed_analysis_lines = []

        for line in lines:
            line = line.strip()

            # Check if we're entering high priority section
            if "High Priority Articles" in line:
                in_high_priority = True
                continue

            # Check if we're leaving high priority section
            if "All Articles Reviewed" in line or "## All Articles" in line:
                # Save the last article if we have one
                if current_article and detailed_analysis_lines:
                    current_article["detailed_analysis"] = "\n".join(
                        detailed_analysis_lines
                    )
                    articles.append(current_article)
                break

            if not in_high_priority:
                continue

            # Look for article titles (### 1. Article Title, ### 2. Article Title, etc.)
            import re

            if line.startswith("### ") and re.match(r"### \d+\. ", line):
                # Save previous article if exists
                if current_article and detailed_analysis_lines:
                    current_article["detailed_analysis"] = "\n".join(
                        detailed_analysis_lines
                    )
                    articles.append(current_article)

                # Start new article
                title = line[4:].strip()  # Remove ### and number
                # Remove number prefix if exists (e.g. "1. Title" -> "Title")
                if ". " in title:
                    title = title.split(". ", 1)[1]

                current_article = {"title": title}
                detailed_analysis_lines = []
                in_detailed_analysis = False
                continue

            # Extract article metadata
            if current_article and not in_detailed_analysis:
                if line.startswith("**Relevance Score:**"):
                    score_match = re.search(r"(\d+)/100", line)
                    if score_match:
                        current_article["score"] = score_match.group(1)
                elif line.startswith("**Dollar Amount:**"):
                    amount = line.split(":", 1)[1].strip().replace("**", "")
                    current_article["dollar_amount"] = amount
                elif line.startswith("**Practice Areas:**"):
                    areas = line.split(":", 1)[1].strip().replace("**", "")
                    current_article["practice_areas"] = [
                        area.strip() for area in areas.split(",")
                    ]
                elif line.startswith("**Whistleblower Elements:**"):
                    indicators = line.split(":", 1)[1].strip().replace("**", "")
                    current_article["whistleblower_indicators"] = indicators
                elif line.startswith("**Source:**"):
                    # Extract URL from [text](url) format
                    url_match = re.search(r"\[.*?\]\((.*?)\)", line)
                    if url_match:
                        current_article["url"] = url_match.group(1)
                elif line.startswith("#### Detailed Analysis"):
                    in_detailed_analysis = True
                    continue

            # Collect detailed analysis content
            if in_detailed_analysis and line:
                detailed_analysis_lines.append(line)

        # Don't forget the last article
        if current_article and detailed_analysis_lines:
            current_article["detailed_analysis"] = "\n".join(detailed_analysis_lines)
            articles.append(current_article)

        return articles

    def _extract_appendix_content(self, analysis_content: str) -> str:
        """Extract the appendix content (medium and lower priority articles)."""
        lines = analysis_content.split("\n")
        appendix_lines = []
        in_appendix = False

        for line in lines:
            if "All Articles Reviewed" in line or "## All Articles" in line:
                in_appendix = True

            if in_appendix:
                appendix_lines.append(line)

        return "\n".join(appendix_lines)

    def _parse_appendix_to_pdf(
        self,
        markdown_text: str,
        story: list,
        heading_style,
        subheading_style,
        body_style,
        bullet_style,
        legal_level1_style=None,
    ):
        """Parse appendix markdown content for PDF (without high-priority article logic)."""
        lines = markdown_text.split("\n")

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Handle different markdown elements
            if line.startswith("## "):
                # Major section headers
                header_text = line[3:].strip()
                story.append(
                    Paragraph(self._clean_text_for_pdf(header_text), heading_style)
                )

            elif line.startswith("### "):
                # Sub-section headers
                header_text = line[4:].strip()
                story.append(
                    Paragraph(self._clean_text_for_pdf(header_text), subheading_style)
                )

            elif line.startswith("**") and line.endswith("**"):
                # Bold standalone lines
                bold_text = line[2:-2]
                story.append(
                    Paragraph(
                        f"<b>{self._clean_text_for_pdf(bold_text)}</b>", body_style
                    )
                )

            elif line.startswith("- ") or line.startswith("* "):
                # Bullet points
                bullet_text = line[2:].strip()
                story.append(
                    Paragraph(
                        f"• {self._clean_text_for_pdf(bullet_text)}", bullet_style
                    )
                )

            elif line.startswith("---"):
                # Horizontal rules - add some space
                story.append(Spacer(1, 0.1 * inch))

            elif line and (
                ("**" in line and line.count("**") >= 2)
                and any(line.find(f"**{i}.") != -1 for i in range(1, 20))
            ):
                # Numbered list items with bold formatting (e.g., "**1. California Defense Contractor...**")
                if legal_level1_style:
                    story.append(
                        Paragraph(self._clean_text_for_pdf(line), legal_level1_style)
                    )
                else:
                    story.append(
                        Paragraph(self._clean_text_for_pdf(line), bullet_style)
                    )

            elif (
                line and not line.startswith("#") and not self._is_formatting_note(line)
            ):
                # Regular text paragraphs (skip formatting notes)
                story.append(Paragraph(self._clean_text_for_pdf(line), body_style))

    def _generate_table_of_contents(
        self, report: Report, articles_with_analysis: List[Dict]
    ) -> List[str]:
        """Generate comprehensive table of contents with clickable links."""
        toc_entries = []

        # Level 1: Main Report Sections
        section_num = 1

        # Add standard sections with internal links
        toc_entries.append(
            f'<link href="#report_metadata" color="blue">{section_num}. Report Metadata</link>'
        )
        section_num += 1

        if report.summary:
            toc_entries.append(
                f'<link href="#executive_summary" color="blue">{section_num}. Executive Summary</link>'
            )
            section_num += 1

        if articles_with_analysis:
            # Determine section title based on report's high_priority_only flag
            section_title = "High Priority Articles Overview" if report.high_priority_only else "Analyzed Articles Overview"
            
            toc_entries.append(
                f'<link href="#analyzed_articles" color="blue">{section_num}. {section_title}</link>'
            )

            # Level 2: Individual Articles (nested under analyzed articles section)
            for i, article in enumerate(articles_with_analysis, 1):
                article_title = article["title"]
                # Use full title in table of contents
                display_title = article_title

                # Create bookmark ID for the article
                article_id = f"article_{i}"
                # Articles are subsections of High Priority Articles Overview
                toc_entries.append(
                    f'   <link href="#{article_id}" color="blue">{section_num}.{i} {display_title}</link>'
                )

                # Level 3: Major sections within each article (double-indented)
                # Use fixed section structure for JSON-based articles
                if article.get("detailed_analysis_json"):
                    # JSON-based articles have predictable structure
                    fixed_subsections = [
                        "Executive Summary",
                        "Case Analysis",
                        "Market Intelligence & External Research",
                    ]
                    for j, subsection in enumerate(fixed_subsections, 1):
                        subsection_id = f"{article_id}_section_{j}"
                        toc_entries.append(f"      {section_num}.{i}.{j} {subsection}")
                else:
                    # Fallback for markdown-based articles
                    detailed_analysis = article.get("detailed_analysis", "")
                    if detailed_analysis:
                        subsections = self._extract_major_sections_for_toc(
                            detailed_analysis
                        )
                        for j, subsection in enumerate(subsections, 1):
                            subsection_id = f"{article_id}_section_{j}"
                            toc_entries.append(
                                f"      {section_num}.{i}.{j} {subsection}"
                            )

            section_num += 1

        # Always include appendix
        toc_entries.append(f"{section_num}. Article Summary Appendix")

        return toc_entries

    def _extract_major_sections_for_toc(self, analysis_content: str) -> List[str]:
        """Extract major sections from detailed analysis for table of contents."""
        if not analysis_content:
            return []

        found_sections = []
        lines = analysis_content.split("\n")

        for line in lines:
            line = line.strip()

            # Look for main sections - both # and ## headers, but exclude lettered subsections
            if (
                line.startswith("## ") or line.startswith("# ")
            ) and not line.startswith("### "):
                section_title = line.lstrip("#").strip()

                # Skip lettered subsections (A., B., C., etc.)
                if section_title.startswith(("A.", "B.", "C.", "D.", "E.", "F.")):
                    continue

                # Skip PART prefixes and get the actual section name
                if section_title.startswith("PART "):
                    # Extract section name after "PART X:" pattern
                    if ":" in section_title:
                        section_title = section_title.split(":", 1)[1].strip()

                # Match and standardize main sections
                if "EXECUTIVE SUMMARY" in section_title.upper():
                    if "Executive Summary" not in found_sections:
                        found_sections.append("Executive Summary")
                elif "CASE ANALYSIS" in section_title.upper():
                    if "Case Analysis" not in found_sections:
                        found_sections.append("Case Analysis")
                elif (
                    "MARKET INTELLIGENCE" in section_title.upper()
                    or "EXTERNAL RESEARCH" in section_title.upper()
                    or "LEGAL ANALYSIS" in section_title.upper()
                ):
                    if "Market Intelligence & External Research" not in found_sections:
                        found_sections.append("Market Intelligence & External Research")
                elif (
                    "BLOG POST OUTLINE" in section_title.upper()
                    or "BLOG POST STRUCTURE" in section_title.upper()
                    or "COMMENTARY ANGLES" in section_title.upper()
                ):
                    if "Blog Post Outline" not in found_sections:
                        found_sections.append("Blog Post Outline")

        # Ensure we have the main sections in logical order
        ordered_sections = []
        for priority in [
            "Executive Summary",
            "Case Analysis",
            "Market Intelligence & External Research",
            "Blog Post Outline",
        ]:
            if priority in found_sections:
                ordered_sections.append(priority)

        return ordered_sections[:4]  # Limit to 4 main sections for readability

    def _add_case_analysis_paragraphs(
        self, table_data: List[List[str]], story: List, body_style
    ) -> None:
        """Convert a CASE ANALYSIS table to individual paragraphs to avoid PDF rendering issues."""
        if not table_data or len(table_data) < 2:
            return

        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch

        # Skip header row, process data rows
        for row in table_data[1:]:
            if len(row) >= 2:
                element = row[0].strip()
                details = row[1].strip()

                # Clean up HTML entities and tags (handle both encoded and unencoded)
                details = details.replace("&lt;br&gt;", "\n")
                details = details.replace("<br>", "\n")
                details = details.replace("&lt;", "<")
                details = details.replace("&gt;", ">")
                details = details.replace("&amp;", "&")

                # Add element header (remove existing bold tags to avoid double formatting)
                element_clean = self._clean_text_for_pdf(element)
                element_clean = element_clean.replace("<b>", "").replace("</b>", "")
                element_clean = element_clean.replace("**", "")  # Remove markdown bold
                story.append(Paragraph(f"<b>{element_clean}</b>", body_style))

                # Split details by line breaks and add as bullet points
                detail_lines = [
                    line.strip() for line in details.split("\n") if line.strip()
                ]
                for detail_line in detail_lines:
                    detail_clean = self._clean_text_for_pdf(detail_line)
                    if detail_clean.startswith("-"):
                        story.append(Paragraph(f"  {detail_clean}", body_style))
                    else:
                        story.append(Paragraph(f"  • {detail_clean}", body_style))

                # Add small spacing between elements
                story.append(Spacer(1, 0.05 * inch))

    def _render_json_analysis_to_pdf(
        self,
        detailed_analysis_json: str,
        story: List,
        heading_style,
        subheading_style,
        body_style,
        bullet_style,
        legal_level1_style,
        legal_level2_style,
        legal_level3_style,
        legal_level4_style,
        article_id: str,
    ):
        """Render JSON-structured analysis directly to PDF without markdown conversion."""
        import json
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch

        try:
            # Parse the combined JSON
            combined_json = json.loads(detailed_analysis_json)

            # Check if this has both article and insight analysis
            if (
                "article_analysis" in combined_json
                and "insight_analysis" in combined_json
            ):
                # Two-stage analysis
                article_text = combined_json["article_analysis"]
                insight_text = combined_json["insight_analysis"]

                # Parse article analysis
                try:
                    article_json = json.loads(article_text)
                    self._render_article_analysis_json_to_pdf(
                        article_json,
                        story,
                        heading_style,
                        subheading_style,
                        body_style,
                        bullet_style,
                        legal_level1_style,
                        legal_level2_style,
                        legal_level3_style,
                        legal_level4_style,
                        article_id,
                    )
                except json.JSONDecodeError:
                    story.append(
                        Paragraph("Article analysis format error.", body_style)
                    )

                # Parse insight analysis
                try:
                    insight_json = json.loads(insight_text)
                    self._render_insight_analysis_json_to_pdf(
                        insight_json,
                        story,
                        heading_style,
                        subheading_style,
                        body_style,
                        bullet_style,
                        legal_level1_style,
                        legal_level2_style,
                        legal_level3_style,
                        legal_level4_style,
                        article_id,
                    )
                except json.JSONDecodeError:
                    story.append(
                        Paragraph("Insight analysis format error.", body_style)
                    )

            else:
                # Single article analysis
                self._render_article_analysis_json_to_pdf(
                    combined_json,
                    story,
                    heading_style,
                    subheading_style,
                    body_style,
                    bullet_style,
                    legal_level1_style,
                    legal_level2_style,
                    legal_level3_style,
                    legal_level4_style,
                    article_id,
                )

        except json.JSONDecodeError as e:
            print(f"JSON parsing failed in PDF generation: {e}")
            story.append(
                Paragraph(
                    "Analysis format error - please regenerate report.", body_style
                )
            )

    def _render_article_analysis_json_to_pdf(
        self,
        article_json: dict,
        story: List,
        heading_style,
        subheading_style,
        body_style,
        bullet_style,
        legal_level1_style,
        legal_level2_style,
        legal_level3_style,
        legal_level4_style,
        article_id: str,
    ):
        """Render article analysis JSON to PDF."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch

        # Legal document section numbering
        section_counter = 0

        def int_to_roman(num):
            """Convert integer to Roman numeral."""
            values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
            literals = [
                "M",
                "CM",
                "D",
                "CD",
                "C",
                "XC",
                "L",
                "XL",
                "X",
                "IX",
                "V",
                "IV",
                "I",
            ]
            result = ""
            for i in range(len(values)):
                count = num // values[i]
                result += literals[i] * count
                num -= values[i] * count
            return result

        def get_legal_section_number(level, counter):
            """Generate legal document section numbers: 1., A., 1., a., i."""
            if level == 1:  # Main sections: 1., 2., 3.
                return f"{counter}."
            elif level == 2:  # Sub-sections: A., B., C.
                return f"{chr(64 + counter)}."  # A=65, so 64+1=65=A
            elif level == 3:  # Sub-sub-sections: 1., 2., 3.
                return f"{counter}."
            elif level == 4:  # Sub-sub-sub-sections: a., b., c.
                return f"{chr(96 + counter)}."  # a=97, so 96+1=97=a
            elif level == 5:  # Lowest level: i., ii., iii.
                return int_to_roman(counter).lower() + "."
            else:
                return f"{counter}."

        # Executive Summary
        if "analysis_metadata" in article_json:
            metadata = article_json["analysis_metadata"]
            if "relevance_score" in metadata:
                story.append(
                    Paragraph(
                        f"Relevance score: {metadata['relevance_score']}", body_style
                    )
                )
                story.append(Spacer(1, 0.05 * inch))

        if "case_overview" in article_json:
            overview = article_json["case_overview"]
            section_counter += 1
            section_id = f"{article_id}_section_{section_counter}"
            section_num = get_legal_section_number(1, section_counter)
            story.append(
                Paragraph(
                    f'<a name="{section_id}"/>{section_num} EXECUTIVE SUMMARY',
                    heading_style,
                )
            )

            if "summary" in overview:
                story.append(
                    Paragraph(self._clean_text_for_pdf(overview["summary"]), body_style)
                )
            if "significance" in overview:
                story.append(
                    Paragraph(
                        self._clean_text_for_pdf(overview["significance"]), body_style
                    )
                )
            story.append(Spacer(1, 0.05 * inch))

        # Case Analysis
        section_counter += 1
        section_id = f"{article_id}_section_{section_counter}"
        section_num = get_legal_section_number(1, section_counter)
        story.append(
            Paragraph(
                f'<a name="{section_id}"/>{section_num} CASE ANALYSIS', heading_style
            )
        )

        if "fact_pattern" in article_json:
            fact_pattern = article_json["fact_pattern"]
            subsection_counter = 0

            # Parties
            if "parties" in fact_pattern:
                subsection_counter += 1
                subsection_num = get_legal_section_number(2, subsection_counter)
                story.append(
                    Paragraph(
                        f"<b>{subsection_num} Parties Involved</b>", subheading_style
                    )
                )
                parties = fact_pattern["parties"]
                if isinstance(parties, dict):
                    # Parse dictionary into numbered legal format
                    for i, (key, value) in enumerate(parties.items(), 1):
                        item_num = get_legal_section_number(3, i)
                        # Capitalize the key for display
                        display_key = key.replace("_", " ").title()
                        story.append(
                            Paragraph(
                                f"{item_num} {display_key}: {self._clean_text_for_pdf(str(value))}",
                                legal_level3_style,
                            )
                        )
                elif isinstance(parties, list):
                    for i, party in enumerate(parties, 1):
                        party_num = get_legal_section_number(3, i)
                        story.append(
                            Paragraph(
                                f"{party_num} {self._clean_text_for_pdf(str(party))}",
                                legal_level3_style,
                            )
                        )
                else:
                    story.append(
                        Paragraph(self._clean_text_for_pdf(str(parties)), body_style)
                    )
                story.append(Spacer(1, 0.03 * inch))

            # Misconduct
            if "misconduct_details" in fact_pattern:
                subsection_counter += 1
                subsection_num = get_legal_section_number(2, subsection_counter)
                story.append(
                    Paragraph(
                        f"<b>{subsection_num} Alleged Misconduct</b>", subheading_style
                    )
                )
                story.append(
                    Paragraph(
                        self._clean_text_for_pdf(fact_pattern["misconduct_details"]),
                        body_style,
                    )
                )
                story.append(Spacer(1, 0.03 * inch))
            elif "misconduct" in fact_pattern:
                subsection_counter += 1
                subsection_num = get_legal_section_number(2, subsection_counter)
                story.append(
                    Paragraph(
                        f"<b>{subsection_num} Alleged Misconduct</b>", subheading_style
                    )
                )
                misconduct = fact_pattern["misconduct"]
                if isinstance(misconduct, dict):
                    for i, (key, value) in enumerate(misconduct.items(), 1):
                        item_num = get_legal_section_number(3, i)
                        # Capitalize the key for display
                        display_key = key.replace("_", " ").title()
                        story.append(
                            Paragraph(
                                f"{item_num} {display_key}: {self._clean_text_for_pdf(str(value))}",
                                legal_level3_style,
                            )
                        )
                elif isinstance(misconduct, list):
                    for i, item in enumerate(misconduct, 1):
                        item_num = get_legal_section_number(3, i)
                        story.append(
                            Paragraph(
                                f"{item_num} {self._clean_text_for_pdf(str(item))}",
                                legal_level3_style,
                            )
                        )
                else:
                    story.append(
                        Paragraph(self._clean_text_for_pdf(str(misconduct)), body_style)
                    )
                story.append(Spacer(1, 0.03 * inch))

            # Legal Framework
            if "legal_framework" in fact_pattern:
                subsection_counter += 1
                subsection_num = get_legal_section_number(2, subsection_counter)
                story.append(
                    Paragraph(
                        f"<b>{subsection_num} Legal Framework</b>", subheading_style
                    )
                )
                legal = fact_pattern["legal_framework"]
                if isinstance(legal, list):
                    for i, statute in enumerate(legal, 1):
                        statute_num = get_legal_section_number(3, i)
                        story.append(
                            Paragraph(
                                f"{statute_num} {self._clean_text_for_pdf(statute)}",
                                legal_level3_style,
                            )
                        )
                elif isinstance(legal, dict):
                    for i, (key, value) in enumerate(legal.items(), 1):
                        item_num = get_legal_section_number(3, i)
                        # Capitalize the key for display
                        display_key = key.replace("_", " ").title()
                        story.append(
                            Paragraph(
                                f"{item_num} {display_key}: {self._clean_text_for_pdf(str(value))}",
                                legal_level3_style,
                            )
                        )
                else:
                    story.append(
                        Paragraph(self._clean_text_for_pdf(str(legal)), body_style)
                    )
                story.append(Spacer(1, 0.05 * inch))

        # Supporting Quotes
        if "supporting_quotes" in article_json:
            subsection_counter += 1
            subsection_num = get_legal_section_number(2, subsection_counter)
            story.append(
                Paragraph(
                    f"<b>{subsection_num} Supporting Quotes</b>", subheading_style
                )
            )

            quotes = article_json["supporting_quotes"]
            for i, quote in enumerate(quotes, 1):
                quote_num = get_legal_section_number(3, i)
                if isinstance(quote, dict):
                    quote_text = quote.get("quote", "")
                    speaker = quote.get("speaker", "Unknown")
                    title = quote.get("title", "")
                    attribution = f"--{speaker}"
                    if title:
                        attribution += f", {title}"
                else:
                    quote_text = str(quote)
                    attribution = ""

                story.append(
                    Paragraph(
                        f'{quote_num} <i>"{self._clean_text_for_pdf(quote_text)}"</i> {attribution}',
                        legal_level3_style,
                    )
                )
                story.append(Spacer(1, 0.03 * inch))

        # Legal Analysis
        if "legal_analysis" in article_json:
            analysis = article_json["legal_analysis"]
            analysis_section_counter = 0

            if "enforcement_trends" in analysis:
                analysis_section_counter += 1
                analysis_num = get_legal_section_number(
                    2, subsection_counter + analysis_section_counter
                )
                story.append(
                    Paragraph(
                        f"<b>{analysis_num} Enforcement Trends & Precedent</b>",
                        subheading_style,
                    )
                )
                trends = analysis["enforcement_trends"]
                story.append(
                    Paragraph(self._clean_text_for_pdf(str(trends)), body_style)
                )
                story.append(Spacer(1, 0.03 * inch))

            if "investigative_techniques" in analysis:
                analysis_section_counter += 1
                analysis_num = get_legal_section_number(
                    2, subsection_counter + analysis_section_counter
                )
                story.append(
                    Paragraph(
                        f"<b>{analysis_num} Investigative Techniques</b>",
                        subheading_style,
                    )
                )
                techniques = analysis["investigative_techniques"]
                story.append(
                    Paragraph(self._clean_text_for_pdf(str(techniques)), body_style)
                )
                story.append(Spacer(1, 0.03 * inch))

            if "whistleblower_analysis" in analysis:
                analysis_section_counter += 1
                analysis_num = get_legal_section_number(
                    2, subsection_counter + analysis_section_counter
                )
                story.append(
                    Paragraph(
                        f"<b>{analysis_num} Whistleblower Analysis</b>",
                        subheading_style,
                    )
                )
                whistleblower = analysis["whistleblower_analysis"]
                story.append(
                    Paragraph(self._clean_text_for_pdf(str(whistleblower)), body_style)
                )
                story.append(Spacer(1, 0.05 * inch))

    def _render_insight_analysis_json_to_pdf(
        self,
        insight_json: dict,
        story: List,
        heading_style,
        subheading_style,
        body_style,
        bullet_style,
        legal_level1_style,
        legal_level2_style,
        legal_level3_style,
        legal_level4_style,
        article_id: str,
    ):
        """Render insight analysis JSON to PDF."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch

        # Helper functions for legal numbering (redefine here for scope)
        def int_to_roman(num):
            values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
            literals = [
                "M",
                "CM",
                "D",
                "CD",
                "C",
                "XC",
                "L",
                "XL",
                "X",
                "IX",
                "V",
                "IV",
                "I",
            ]
            result = ""
            for i in range(len(values)):
                count = num // values[i]
                result += literals[i] * count
                num -= values[i] * count
            return result

        def get_legal_section_number(level, counter):
            if level == 1:  # Main sections: 1., 2., 3.
                return f"{counter}."
            elif level == 2:  # Sub-sections: A., B., C.
                return f"{chr(64 + counter)}."
            elif level == 3:  # Sub-sub-sections: 1., 2., 3.
                return f"{counter}."
            elif level == 4:  # Sub-sub-sub-sections: a., b., c.
                return f"{chr(96 + counter)}."
            elif level == 5:  # Lowest level: i., ii., iii.
                return int_to_roman(counter).lower() + "."
            else:
                return f"{counter}."

        # Market Intelligence section (continuing from Case Analysis)
        # Create proper anchor using the passed article_id
        section_id = f"{article_id}_section_3"
        story.append(
            Paragraph(
                f'<a name="{section_id}"/>3. MARKET INTELLIGENCE & EXTERNAL RESEARCH',
                heading_style,
            )
        )

        # Research Summary
        if "research_summary" in insight_json:
            story.append(Paragraph("<b>A. Research Summary</b>", subheading_style))
            summary = insight_json["research_summary"]
            story.append(Paragraph(self._clean_text_for_pdf(str(summary)), body_style))
            story.append(Spacer(1, 0.05 * inch))

        # Insights
        if "insights" in insight_json:
            story.append(Paragraph("<b>B. Key Insights</b>", subheading_style))
            insights = insight_json["insights"]
            if isinstance(insights, dict):
                subsection_counter = 0
                for key, value in insights.items():
                    subsection_counter += 1
                    sub_num = get_legal_section_number(3, subsection_counter)
                    key_title = key.replace("_", " ").title()
                    story.append(Paragraph(f"<b>{sub_num} {key_title}</b>", body_style))

                    if isinstance(value, list):
                        for i, item in enumerate(value, 1):
                            item_letter = get_legal_section_number(4, i)

                            # Handle both dictionary and string items
                            if isinstance(item, dict):
                                # Extract meaningful content from dictionary with citations
                                if "trend" in item and "detail" in item:
                                    formatted_text = (
                                        f"<b>{item['trend']}:</b> {item['detail']}"
                                    )
                                    # Add citation if available
                                    if "source" in item and "source_url" in item:
                                        clean_url = self._clean_url_for_link(
                                            item["source_url"]
                                        )
                                        formatted_text += f" (<link href='{clean_url}' color='blue'>{item['source']}</link>)"
                                elif "prediction" in item and "detail" in item:
                                    formatted_text = (
                                        f"<b>{item['prediction']}:</b> {item['detail']}"
                                    )
                                    # Add citation if available
                                    if "source" in item and "source_url" in item:
                                        clean_url = self._clean_url_for_link(
                                            item["source_url"]
                                        )
                                        formatted_text += f" (<link href='{clean_url}' color='blue'>{item['source']}</link>)"
                                elif "stakeholder" in item and "recommendation" in item:
                                    formatted_text = f"<b>{item['stakeholder']}:</b> {item['recommendation']}"
                                    # Add citation if available
                                    if "source" in item and "source_url" in item:
                                        clean_url = self._clean_url_for_link(
                                            item["source_url"]
                                        )
                                        formatted_text += f" (<link href='{clean_url}' color='blue'>{item['source']}</link>)"
                                else:
                                    # Generic dictionary handling - look for source and source_url
                                    base_content = " - ".join(
                                        [
                                            f"{k}: {v}"
                                            for k, v in item.items()
                                            if k not in ["source", "source_url"]
                                        ]
                                    )
                                    if "source" in item and "source_url" in item:
                                        clean_url = self._clean_url_for_link(
                                            item["source_url"]
                                        )
                                        formatted_text = f"{base_content} (<link href='{clean_url}' color='blue'>{item['source']}</link>)"
                                    else:
                                        formatted_text = base_content
                            else:
                                formatted_text = str(item)

                            cleaned_text = self._clean_text_for_pdf(
                                formatted_text
                            ).strip()
                            story.append(
                                Paragraph(
                                    f"{item_letter} {cleaned_text}", legal_level4_style
                                )
                            )
                    else:
                        story.append(
                            Paragraph(self._clean_text_for_pdf(str(value)), body_style)
                        )
                    story.append(Spacer(1, 0.03 * inch))
            else:
                story.append(
                    Paragraph(self._clean_text_for_pdf(str(insights)), body_style)
                )
            story.append(Spacer(1, 0.05 * inch))

        if "comparable_cases" in insight_json:
            story.append(Paragraph("<b>C. Comparable Cases</b>", subheading_style))
            cases = insight_json["comparable_cases"]
            for i, case in enumerate(cases, 1):
                if isinstance(case, dict):
                    case_name = case.get("case_name", "Unknown Case")
                    source_url = case.get("source_url", "")
                    case_num = get_legal_section_number(3, i)

                    # Format case name with hyperlink if URL available
                    if source_url:
                        clean_url = self._clean_url_for_link(source_url)
                        case_title = f"<b>{case_num} <link href='{clean_url}' color='blue'>{self._clean_text_for_pdf(case_name)}</link></b>"
                    else:
                        case_title = (
                            f"<b>{case_num} {self._clean_text_for_pdf(case_name)}</b>"
                        )
                    story.append(Paragraph(case_title, legal_level3_style))

                    sub_item_counter = 0
                    for field in [
                        "similarity",
                        "key_differences",
                        "penalty_outcome",
                        "industry_reaction",
                    ]:
                        if field in case:
                            sub_item_counter += 1
                            value = case[field]
                            field_title = field.replace("_", " ").title()
                            sub_item_letter = get_legal_section_number(
                                4, sub_item_counter
                            )
                            story.append(
                                Paragraph(
                                    f"{sub_item_letter} <b>{field_title}:</b> {self._clean_text_for_pdf(str(value))}",
                                    legal_level4_style,
                                )
                            )

                    story.append(Spacer(1, 0.05 * inch))

        # Other sections with legal numbering
        if "regulatory_intelligence" in insight_json:
            story.append(
                Paragraph("<b>D. Regulatory Intelligence</b>", subheading_style)
            )
            reg_intel = insight_json["regulatory_intelligence"]

            if isinstance(reg_intel, dict):
                # Parse structured regulatory intelligence
                subsection_counter = 0

                if "agency_guidance" in reg_intel:
                    subsection_counter += 1
                    sub_num = get_legal_section_number(3, subsection_counter)
                    story.append(
                        Paragraph(f"<b>{sub_num} Agency Guidance</b>", body_style)
                    )

                    guidance_list = reg_intel["agency_guidance"]
                    if isinstance(guidance_list, list):
                        for i, guidance in enumerate(guidance_list, 1):
                            if isinstance(guidance, dict):
                                source = guidance.get("source", "Unknown")
                                details = guidance.get(
                                    "detail", guidance.get("details", "")
                                )  # Try both 'detail' and 'details'
                                source_url = guidance.get("source_url", "")
                                item_letter = get_legal_section_number(4, i)

                                # Format with hyperlink if URL available
                                if source_url:
                                    formatted_text = f"{item_letter} <b><link href='{self._clean_url_for_link(source_url)}' color='blue'>{self._clean_text_for_pdf(source)}</link>:</b> {self._clean_text_for_pdf(details)}"
                                else:
                                    formatted_text = f"{item_letter} <b>{self._clean_text_for_pdf(source)}:</b> {self._clean_text_for_pdf(details)}"
                                story.append(
                                    Paragraph(formatted_text, legal_level4_style)
                                )
                    story.append(Spacer(1, 0.03 * inch))

                if "congressional_activity" in reg_intel:
                    subsection_counter += 1
                    sub_num = get_legal_section_number(3, subsection_counter)
                    story.append(
                        Paragraph(
                            f"<b>{sub_num} Congressional Activity</b>", body_style
                        )
                    )

                    activity_list = reg_intel["congressional_activity"]
                    if isinstance(activity_list, list):
                        for i, activity in enumerate(activity_list, 1):
                            if isinstance(activity, dict):
                                source = activity.get("source", "Unknown")
                                details = activity.get(
                                    "detail", activity.get("details", "")
                                )  # Try both 'detail' and 'details'
                                source_url = activity.get("source_url", "")
                                item_letter = get_legal_section_number(4, i)

                                # Format with hyperlink if URL available
                                if source_url:
                                    formatted_text = f"{item_letter} <b><link href='{self._clean_url_for_link(source_url)}' color='blue'>{self._clean_text_for_pdf(source)}</link>:</b> {self._clean_text_for_pdf(details)}"
                                else:
                                    formatted_text = f"{item_letter} <b>{self._clean_text_for_pdf(source)}:</b> {self._clean_text_for_pdf(details)}"
                                story.append(
                                    Paragraph(formatted_text, legal_level4_style)
                                )
                    story.append(Spacer(1, 0.03 * inch))

                if "industry_responses" in reg_intel:
                    subsection_counter += 1
                    sub_num = get_legal_section_number(3, subsection_counter)
                    story.append(
                        Paragraph(f"<b>{sub_num} Industry Responses</b>", body_style)
                    )

                    response_list = reg_intel["industry_responses"]
                    if isinstance(response_list, list):
                        for i, response in enumerate(response_list, 1):
                            if isinstance(response, dict):
                                source = response.get("source", "Unknown")
                                details = response.get(
                                    "detail", response.get("details", "")
                                )  # Try both 'detail' and 'details'
                                source_url = response.get("source_url", "")
                                item_letter = get_legal_section_number(4, i)

                                # Format with hyperlink if URL available
                                if source_url:
                                    formatted_text = f"{item_letter} <b><link href='{self._clean_url_for_link(source_url)}' color='blue'>{self._clean_text_for_pdf(source)}</link>:</b> {self._clean_text_for_pdf(details)}"
                                else:
                                    formatted_text = f"{item_letter} <b>{self._clean_text_for_pdf(source)}:</b> {self._clean_text_for_pdf(details)}"
                                story.append(
                                    Paragraph(formatted_text, legal_level4_style)
                                )
                    story.append(Spacer(1, 0.03 * inch))
            else:
                # Fallback for string/other formats
                story.append(
                    Paragraph(self._clean_text_for_pdf(str(reg_intel)), body_style)
                )
                story.append(Spacer(1, 0.03 * inch))

        if "market_impact" in insight_json:
            story.append(Paragraph("<b>E. Market Impact</b>", subheading_style))
            market = insight_json["market_impact"]

            if isinstance(market, dict):
                # Parse structured market impact
                subsection_counter = 0

                for category in [
                    "stock_responses",
                    "insurance_risk",
                    "compliance_market",
                ]:
                    if category in market:
                        subsection_counter += 1
                        sub_num = get_legal_section_number(3, subsection_counter)

                        category_title = category.replace("_", " ").title()
                        story.append(
                            Paragraph(f"<b>{sub_num} {category_title}</b>", body_style)
                        )

                        category_list = market[category]
                        if isinstance(category_list, list):
                            for i, item in enumerate(category_list, 1):
                                if isinstance(item, dict):
                                    source = item.get("source", "Unknown")
                                    details = item.get(
                                        "detail", item.get("details", "")
                                    )  # Try both 'detail' and 'details'
                                    source_url = item.get("source_url", "")
                                    item_letter = get_legal_section_number(4, i)

                                    # Format with hyperlink if URL available
                                    if source_url:
                                        formatted_text = f"{item_letter} <b><link href='{self._clean_url_for_link(source_url)}' color='blue'>{self._clean_text_for_pdf(source)}</link>:</b> {self._clean_text_for_pdf(details)}"
                                    else:
                                        formatted_text = f"{item_letter} <b>{self._clean_text_for_pdf(source)}:</b> {self._clean_text_for_pdf(details)}"
                                    story.append(
                                        Paragraph(formatted_text, legal_level4_style)
                                    )
                                else:
                                    item_letter = get_legal_section_number(4, i)
                                    story.append(
                                        Paragraph(
                                            f"{item_letter} {self._clean_text_for_pdf(str(item))}",
                                            legal_level4_style,
                                        )
                                    )
                        story.append(Spacer(1, 0.03 * inch))
            else:
                # Fallback for string/other formats
                story.append(
                    Paragraph(self._clean_text_for_pdf(str(market)), body_style)
                )
                story.append(Spacer(1, 0.05 * inch))

    def _render_markdown_analysis_to_pdf(
        self,
        detailed_analysis: str,
        story: List,
        heading_style,
        subheading_style,
        body_style,
        bullet_style,
        article_id: str,
        article_index: int,
    ):
        """Render markdown analysis to PDF (fallback method)."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.units import inch

        # Parse and add the detailed analysis
        analysis_lines = detailed_analysis.split("\n")

        # Check for tables and process them specially
        table_lines = []  # Simplified: skip table extraction for now

        # Section counter for bookmarks
        section_counter = 0

        line_idx = 0
        while line_idx < len(analysis_lines):
            line = analysis_lines[line_idx].strip()

            # Check if this line starts a table
            if line_idx in table_lines:
                # Check if this is a fact-checking protocol table by looking at surrounding context
                context_start = max(0, line_idx - 5)
                context_lines = analysis_lines[context_start : line_idx + 1]
                context_text = "\n".join(context_lines).lower()

                if (
                    "fact-checking protocol" in context_text
                    or "fact checking protocol" in context_text
                ):
                    # Skip fact-checking protocol tables
                    table_data, lines_consumed = self._parse_markdown_table(
                        analysis_lines[line_idx:]
                    )
                    line_idx += lines_consumed  # Skip the table
                    continue

                if "case analysis" in context_text and "element" in context_text:
                    # Convert CASE ANALYSIS tables to structured text instead of table format
                    table_data, lines_consumed = self._parse_markdown_table(
                        analysis_lines[line_idx:]
                    )
                    if table_data:
                        # Convert table to structured paragraphs
                        self._add_case_analysis_paragraphs(
                            table_data, story, body_style
                        )
                        story.append(Spacer(1, 0.05 * inch))  # Reduced spacing
                    line_idx += lines_consumed
                    continue

                table_data, lines_consumed = self._parse_markdown_table(
                    analysis_lines[line_idx:]
                )
                if table_data:
                    story.append(self._create_pdf_table(table_data))
                    story.append(Spacer(1, 0.05 * inch))  # Reduced spacing
                    line_idx += lines_consumed
                    continue

            # Process regular lines
            if not line:
                line_idx += 1
                continue

            # Skip redundant source article line (already shown in Article Information)
            if "SOURCE ARTICLE:" in line:
                line_idx += 1
                continue

            if line.startswith("####"):
                # Sub-sub-heading
                header_text = line[4:].strip()
                story.append(
                    Paragraph(
                        f"<b>{self._clean_text_for_pdf(header_text)}</b>", body_style
                    )
                )
            elif line.startswith("###"):
                # Sub-heading
                header_text = line[3:].strip()
                story.append(
                    Paragraph(self._clean_text_for_pdf(header_text), subheading_style)
                )
            elif line.startswith("##"):
                # Major heading with bookmark
                header_text = line[2:].strip()
                # Check if this is a main section that should get a bookmark and add legal numbering
                if any(
                    section in header_text.upper()
                    for section in [
                        "EXECUTIVE SUMMARY",
                        "CASE ANALYSIS",
                        "MARKET INTELLIGENCE",
                        "BLOG POST OUTLINE",
                    ]
                ):
                    section_counter += 1
                    section_id = f"{article_id}_section_{section_counter}"
                    # Add legal document numbering for main sections
                    section_num = f"{section_counter}."
                    story.append(
                        Paragraph(
                            f'<a name="{section_id}"/>{section_num} {self._clean_text_for_pdf(header_text)}',
                            heading_style,
                        )
                    )
                else:
                    story.append(
                        Paragraph(self._clean_text_for_pdf(header_text), heading_style)
                    )
            elif line.startswith("  - ") or line.startswith("  * "):
                # Indented sub-bullet (2 spaces)
                bullet_text = line[4:].strip()
                story.append(
                    Paragraph(
                        f"    ◦ {self._clean_text_for_pdf(bullet_text)}", bullet_style
                    )
                )
            elif line.startswith("   - ") or line.startswith("   * "):
                # Indented sub-bullet (3+ spaces)
                bullet_text = line[5:].strip()
                story.append(
                    Paragraph(
                        f"    ◦ {self._clean_text_for_pdf(bullet_text)}", bullet_style
                    )
                )
            elif line.startswith("- ") or line.startswith("* "):
                # Regular bullet point
                bullet_text = line[2:].strip()

                # Check if this looks like a case start (Similarity pattern)
                if bullet_text.startswith("**Similarity:**"):
                    # This might be the start of a new case - add some spacing
                    story.append(Spacer(1, 0.05 * inch))
                    story.append(
                        Paragraph(
                            f"• {self._clean_text_for_pdf(bullet_text)}", bullet_style
                        )
                    )
                else:
                    story.append(
                        Paragraph(
                            f"• {self._clean_text_for_pdf(bullet_text)}", bullet_style
                        )
                    )
            elif re.match(r"^\d+\.\s+\*\*.*\*\*", line):
                # Numbered list item with bold text (e.g., "1. **Case Name:**")
                story.append(Paragraph(self._clean_text_for_pdf(line), bullet_style))
            elif line.startswith("**") and line.endswith("**"):
                # Bold standalone line
                bold_text = line[2:-2]
                story.append(
                    Paragraph(
                        f"<b>{self._clean_text_for_pdf(bold_text)}</b>", body_style
                    )
                )
            elif line.startswith("---"):
                # Horizontal rule
                story.append(Spacer(1, 0.1 * inch))
            elif (
                line and not line.startswith("#") and not self._is_formatting_note(line)
            ):
                # Check if this is concatenated bullet points
                if "•" in line and line.count("•") > 1:
                    # Split concatenated bullet points and process individually
                    self._process_concatenated_bullets(line, story, bullet_style)
                else:
                    # Regular paragraph (skip formatting notes)
                    story.append(Paragraph(self._clean_text_for_pdf(line), body_style))

            line_idx += 1

    def _process_concatenated_bullets(self, line: str, story: List, bullet_style):
        """Process concatenated bullet points and preserve indentation."""
        # Split by bullet points but preserve the bullet symbols
        parts = line.split("•")

        for i, part in enumerate(parts):
            if i == 0 and not part.strip():
                # Skip empty first part
                continue

            bullet_text = part.strip()
            if not bullet_text:
                continue

            # Check if this should be indented (contains specific patterns)
            # Look for patterns that indicate this is a sub-item
            if (
                bullet_text.startswith("Majority-owned")
                or bullet_text.startswith("DOJ Civil")
                or bullet_text.startswith("U.S. Attorney")
                or bullet_text.startswith("Small Business Administration")
                or bullet_text.startswith("GNGH2 Inc.")
            ):
                # This is a sub-bullet
                story.append(
                    Paragraph(
                        f"    ◦ {self._clean_text_for_pdf(bullet_text)}", bullet_style
                    )
                )
            else:
                # Regular bullet
                story.append(
                    Paragraph(
                        f"• {self._clean_text_for_pdf(bullet_text)}", bullet_style
                    )
                )
