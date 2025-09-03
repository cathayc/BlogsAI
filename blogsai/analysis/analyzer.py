"""
Main analysis engine with three-tier analysis system.

This module provides the core analysis functionality for the BlogsAI application,
including article relevance scoring, detailed analysis generation, and intelligence
report creation. The engine uses OpenAI's API for natural language processing
and supports various report formats.

Key Components:
- AnalysisEngine: Main class for orchestrating analysis workflows
- Article scoring: Relevance assessment based on practice areas and content
- Report generation: Creation of structured intelligence reports
- Citation verification: Optional verification of AI-generated content

The analysis system operates in multiple tiers:
1. Relevance scoring: Quick assessment of article importance (0-100 scale)
2. Detailed analysis: In-depth examination of high-priority articles
3. Report compilation: Aggregation of analyses into comprehensive reports

Usage:
    engine = AnalysisEngine(enable_verification=True, progress_callback=callback_func)
    report = engine.generate_intelligence_report(start_date, end_date)
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_

from .openai_client import OpenAIAnalyzer, APIKeyInvalidError, OpenAIAPIError
from .verifier import CitationVerifier
from ..core import get_db, config
from ..database.models import Article, Report, ReportArticle, Source


class AnalysisEngine:
    """
    Main analysis engine for processing articles and generating intelligence reports.
    
    This class orchestrates the entire analysis workflow, from article relevance scoring
    to detailed analysis generation and report compilation. It integrates with OpenAI's
    API for natural language processing and optionally supports citation verification.
    
    Attributes:
        config: Application configuration object
        openai_analyzer: OpenAI API client for analysis tasks
        enable_verification: Whether to enable citation verification
        progress_callback: Optional callback function for progress updates
        citation_verifier: Citation verification component (if enabled)
    
    The analysis process follows these steps:
    1. Article collection from specified date range or IDs
    2. Relevance scoring (0-100 scale) based on practice areas
    3. Filtering articles by relevance thresholds (≥50 relevant, ≥80 high priority)
    4. Detailed analysis generation for high-priority articles
    5. Report compilation and formatting
    6. Optional citation verification for AI-generated content
    """
    
    def __init__(self, enable_verification: bool = False, progress_callback=None):
        """
        Initialize the AnalysisEngine.
        
        Args:
            enable_verification: Whether to enable citation verification for AI content
            progress_callback: Optional callback function for progress updates.
                             Should accept a string message parameter.
        
        Raises:
            APIKeyInvalidError: If OpenAI API key is invalid or missing
        """
        self.config = config
        self.openai_analyzer = OpenAIAnalyzer(self.config.openai)
        self.enable_verification = enable_verification
        self.progress_callback = progress_callback
        self.citation_verifier = CitationVerifier() if enable_verification else None
    
    def _emit_progress(self, message: str):
        """Emit progress message to callback if available, otherwise print."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)
    
    def _check_existing_report(
        self, start_date: datetime, end_date: datetime, enable_insights: bool
    ) -> Dict[str, Any]:
        """Check for existing report that matches the date range and insights requirement."""
        from ..core import db_session
        
        try:
            with db_session() as db:
                # Look for reports with matching date range
                existing_reports = (
                    db.query(Report)
                    .filter(
                    and_(
                        Report.start_date >= start_date.date(),
                        Report.end_date <= end_date.date(),
                            Report.analysis.isnot(None),  # Must have analysis content
                    )
                    )
                    .order_by(Report.created_at.desc())
                    .all()
                )
                
                for report in existing_reports:
                    # Check if the report matches our insights requirement
                    if enable_insights:
                        # For insights, check if report has market intelligence content
                        if (
                            "market intelligence" in report.analysis.lower()
                            or "insight analysis" in report.analysis.lower()
                            or "research:" in report.analysis.lower()
                        ):
                            return self._format_cached_report_response(report)
                    else:
                        # For regular reports, any existing report is acceptable
                        return self._format_cached_report_response(report)
                
                return None  # No matching report found
                
        except Exception as e:
            self._log_error(f"Error checking for existing report: {str(e)}")
            return None  # Fall back to generating new report
    
    def _format_cached_report_response(self, report: Report) -> Dict[str, Any]:
        """Format a cached report into the expected response format."""
        return {
            "success": True,
            "report_id": report.id,
            "title": report.title,
            "analysis": report.analysis,
            "summary": report.summary
            or f"Cached report with {report.article_count} articles",
            "article_count": report.article_count,
            "tokens_used": report.tokens_used or 0,
            "start_date": (
                datetime.combine(report.start_date, datetime.min.time())
                if report.start_date
                else None
            ),
            "end_date": (
                datetime.combine(report.end_date, datetime.min.time())
                if report.end_date
                else None
            ),
            "cached": True,
        }
        
    def generate_daily_report(self, target_date: datetime = None) -> Dict[str, Any]:
        if target_date is None:
            target_date = datetime.now()
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        return self._generate_tiered_report("daily", start_date, end_date, False, False)

    def generate_intelligence_report(
        self,
        start_date: datetime,
        end_date: datetime,
        force_refresh_scores: bool = False,
        force_refresh_analysis: bool = False,
        enable_insights: bool = False,
        high_priority_only: bool = True,
    ) -> Dict[str, Any]:
        end_date_inclusive = end_date.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        start_date_midnight = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # Check for existing report unless force refresh is requested
        if not force_refresh_analysis:
            existing_report = self._check_existing_report(
                start_date_midnight, end_date_inclusive, enable_insights
            )
            if existing_report:
                self._emit_progress(f"Using cached report: {existing_report['title']}")
                return existing_report
        
        return self._generate_intelligence_report(
            start_date_midnight,
            end_date_inclusive,
            force_refresh_scores,
            force_refresh_analysis,
            enable_insights,
            high_priority_only,
        )

    def generate_intelligence_report_from_articles(
        self,
        article_ids: List[int],
        force_refresh_scores: bool = False,
        force_refresh_analysis: bool = False,
        enable_insights: bool = False,
        high_priority_only: bool = True,
    ) -> Dict[str, Any]:
        """Generate intelligence report from specific article IDs instead of date range."""
        
        return self._generate_intelligence_report_from_ids(
            article_ids,
            force_refresh_scores=force_refresh_scores,
            force_refresh_analysis=force_refresh_analysis,
            enable_insights=enable_insights,
            high_priority_only=high_priority_only,
        )

    def _generate_tiered_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        force_refresh_analysis: bool = False,
        enable_insights: bool = False,
    ) -> Dict[str, Any]:
        """Generate a tiered report with proper error handling and logging."""
        from ..core import db_session
        
        try:
            with db_session() as db:
                # Step 1: Get articles for the date range
                articles = self._get_articles_for_period(db, start_date, end_date)
                
                if not articles:
                    return self._create_error_response(
                        f"No articles found for {report_type} report from {start_date.date()} to {end_date.date()}"
                    )
                
                self._emit_progress(f"Found {len(articles)} articles for analysis")
                
                # Step 2: Score articles for relevance
                scored_articles, total_tokens = self._score_articles_batch(db, articles)
                
                # Step 3: Filter articles by relevance
                relevant_articles, high_priority_articles = (
                    self._filter_articles_by_relevance(scored_articles)
                )
                
                if not relevant_articles:
                    return self._create_error_response(
                        f"No relevant articles found for {report_type} report"
                    )
                
                # Step 4: Generate detailed analyses
                detailed_analyses = self._generate_detailed_analyses(
                    high_priority_articles, force_refresh_analysis, enable_insights
                )
                total_tokens += sum(
                    analysis.get("tokens_used", 0) for analysis in detailed_analyses
                )
                
                # Step 5: Create combined analysis
                combined_analysis = self._create_article_report(
                    detailed_analyses, relevant_articles
                )
                
                # Step 6: Handle verification if enabled
                if self.enable_verification and self.citation_verifier:
                    combined_analysis, verification_tokens = (
                        self._verify_analysis_citations(
                            combined_analysis, detailed_analyses
                        )
                    )
                    total_tokens += verification_tokens
                
                # Step 7: Create and save report
                return self._create_and_save_report(
                    db,
                    report_type,
                    start_date,
                    end_date,
                    combined_analysis,
                    relevant_articles,
                    detailed_analyses,
                    total_tokens,
                )
                
        except Exception as e:
            self._log_error(f"Error in _generate_tiered_report: {str(e)}")
            return self._create_error_response(f"Report generation failed: {str(e)}")
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create a standardized error response."""
        return {"success": False, "error": error_message}
    
    def _score_articles_batch(
        self, db: Session, articles: List[Article]
    ) -> Tuple[List[Dict], int]:
        """Score a batch of articles for relevance."""
        scored_articles = []
        total_tokens = 0
        
        for article in articles:
            try:
                analysis_article = self._convert_db_article(db, article)
                score_result = self._score_article_relevance(analysis_article)
                
                if score_result["success"]:
                    scored_articles.append(
                        {
                            "article": article,
                            "analysis_article": analysis_article,
                            "score": score_result["score"],
                            "practice_areas": score_result["practice_areas"],
                            "dollar_amount": score_result["dollar_amount"],
                            "whistleblower_indicators": score_result[
                                "whistleblower_indicators"
                            ],
                            "blog_potential": score_result.get("blog_potential", "Low"),
                            "summary": score_result["summary"],
                        }
                    )
                    total_tokens += score_result.get("tokens_used", 0)
            except Exception as e:
                self._log_error(f"Error scoring article {article.id}: {str(e)}")
                continue
        
        return scored_articles, total_tokens
    
    def _filter_articles_by_relevance(
        self, scored_articles: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Filter articles by relevance score."""
        relevant_articles = [item for item in scored_articles if item["score"] >= 50]
        high_priority_articles = [
            item for item in scored_articles if item["score"] >= 80
        ]
        
        self._emit_progress(f"Relevant (≥50): {len(relevant_articles)}")
        self._emit_progress(f"High priority (≥80): {len(high_priority_articles)}")
        
        return relevant_articles, high_priority_articles
    
    def _generate_detailed_analyses(
        self,
        high_priority_articles: List[Dict],
        force_refresh_analysis: bool,
        enable_insights: bool,
    ) -> List[Dict]:
        """Generate detailed analyses for high priority articles."""
        detailed_analyses = []
        
        for item in high_priority_articles:
            try:
                self._emit_progress(
                    f"Analyzing: {item['analysis_article'].title}... ({item['score']})"
                )
                result = self._generate_individual_analysis(
                    item["analysis_article"], force_refresh_analysis, enable_insights
                )

                if result["success"]:
                    detailed_analyses.append(
                        {
                            "article": item["article"],
                            "score": item["score"],
                            "practice_areas": item["practice_areas"],
                            "dollar_amount": item["dollar_amount"],
                            "whistleblower_indicators": item[
                                "whistleblower_indicators"
                            ],
                            "blog_potential": item["blog_potential"],
                            "analysis": result["analysis"],
                            "tokens_used": result["tokens_used"],
                        }
                    )
            except Exception as e:
                self._log_error(
                    f"Error analyzing article {item['article'].id}: {str(e)}"
                )
                continue
        
        return detailed_analyses
    
    def _verify_analysis_citations(
        self, combined_analysis: str, detailed_analyses: List[Dict]
    ) -> Tuple[str, int]:
        """Verify citations in the analysis if verification is enabled."""
        verification_tokens = 0
        
        try:
            self._emit_progress("Verifying AI-generated insights...")
            
            # Extract AI-generated insights for verification
            insights_content = self._extract_insights_for_verification(
                detailed_analyses
            )
            
            if insights_content:
                self._emit_progress(
                    f"Found {len(insights_content)} insight sections to verify"
                )
                
                verified_insights = []
                for i, insight_text in enumerate(insights_content):
                    self._emit_progress(
                        f"Verifying insight section {i+1}/{len(insights_content)}..."
                    )

                    verify_result = self.citation_verifier.verify_report_citations(
                        insight_text
                    )
                    if verify_result["success"]:
                        verified_insights.append(verify_result["final_content"])
                        verification_tokens += sum(
                            r.get("verification_details", {}).get("tokens_used", 0)
                            for r in verify_result.get("verification_results", [])
                        )
                        self._emit_progress(
                            f"Insight {i+1} verified: {verify_result['fully_verified']}"
                        )
                    else:
                        self._emit_progress(
                            f"Insight {i+1} verification failed, keeping original"
                        )
                        verified_insights.append(insight_text)
                
                # Update the combined analysis with verified insights
                combined_analysis = self._update_analysis_with_verified_insights(
                    combined_analysis, insights_content, verified_insights
                )
                
                self._emit_progress(
                    f"Citation verification completed for {len(insights_content)} insight sections"
                )
            else:
                self._emit_progress("No AI-generated insights found to verify")
        except Exception as e:
            self._log_error(f"Error in citation verification: {str(e)}")
        
        return combined_analysis, verification_tokens
    
    def _create_and_save_report(
        self,
        db: Session,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        combined_analysis: str,
        relevant_articles: List[Dict],
        detailed_analyses: List[Dict],
        total_tokens: int,
    ) -> Dict[str, Any]:
        """Create and save the report to the database."""
        try:
            report_title = (
                f"{report_type.title()} Report - {start_date.strftime('%Y-%m-%d')}"
            )
            
            report = Report(
                title=report_title,
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                analysis=combined_analysis,
                summary=f"Article-by-article analysis of {len(detailed_analyses)} relevant articles",
                article_count=len(relevant_articles),
                tokens_used=total_tokens,
            )
            
            db.add(report)
            db.flush()
            
            # Link relevant articles to report
            for item in relevant_articles:
                report_article = ReportArticle(
                    report_id=report.id, article_id=item["article"].id
                )
                db.add(report_article)
            
            return {
                "success": True,
                "report_id": report.id,
                "title": report_title,
                "analysis": combined_analysis,
                "summary": f"Article-by-article analysis of {len(detailed_analyses)} relevant articles",
                "article_count": len(relevant_articles),
                "high_priority_count": len(
                    [item for item in relevant_articles if item["score"] >= 80]
                ),
                "detailed_analyses_count": len(detailed_analyses),
                "tokens_used": total_tokens,
                "start_date": start_date,
                "end_date": end_date,
            }
        except Exception as e:
            self._log_error(f"Error creating report: {str(e)}")
            raise
    
    def _log_error(self, message: str):
        """Log error messages consistently."""
        import logging

        logging.error(f"AnalysisEngine: {message}")
    
    def _generate_intelligence_report(
        self,
        start_date: datetime,
        end_date: datetime,
        force_refresh_scores: bool = False,
        force_refresh_analysis: bool = False,
        enable_insights: bool = False,
        high_priority_only: bool = True,
    ) -> Dict[str, Any]:
        """Generate intelligence report with appendix of all articles and analysis of high-priority ones."""
        from ..core import db_session
        
        try:
            with db_session() as db:
                # Step 1: Get all government articles for the date range
                articles = self._get_articles_for_period(db, start_date, end_date)
                
                if not articles:
                    return self._create_error_response(
                        f"No articles found for intelligence report from {start_date.date()} to {end_date.date()}"
                    )
                
                self._emit_progress(f"Found {len(articles)} articles for Analysis")
                
                # Step 2: Score all articles for relevance
                scored_articles, total_tokens = self._score_articles_with_refresh(
                    db, articles, force_refresh_scores
                )
                
                # Step 3: Filter by relevance and priority
                relevant_articles, high_priority_articles = (
                    self._filter_articles_by_relevance(scored_articles)
                )
                
                # Step 4: Generate detailed analysis based on priority setting
                articles_for_analysis = self._select_articles_for_analysis(
                    high_priority_articles, relevant_articles, high_priority_only
                )
                detailed_analyses = self._generate_detailed_analyses(
                    articles_for_analysis, force_refresh_analysis, enable_insights
                )
                total_tokens += sum(
                    analysis.get("tokens_used", 0) for analysis in detailed_analyses
                )
                
                # Step 5: Create intelligence report with appendix
                combined_analysis = self._create_intelligence_report(
                    detailed_analyses, scored_articles, start_date, end_date
                )
                
                # Step 6: Verify citations if verification is enabled
                if self.enable_verification and self.citation_verifier:
                    combined_analysis, verification_tokens = (
                        self._verify_report_citations(combined_analysis)
                    )
                    total_tokens += verification_tokens
                
                # Step 7: Create and save report record
                return self._create_intelligence_report_record(
                    db,
                    start_date,
                    end_date,
                    combined_analysis,
                    scored_articles,
                    relevant_articles,
                    high_priority_articles,
                    detailed_analyses,
                    total_tokens,
                    high_priority_only,
                )
                
        except Exception as e:
            self._log_error(f"Error in _generate_intelligence_report: {str(e)}")
            return self._create_error_response(
                f"Intelligence report generation failed: {str(e)}"
            )
    
    def _score_articles_with_refresh(
        self, db: Session, articles: List[Article], force_refresh_scores: bool
    ) -> Tuple[List[Dict], int]:
        """Score articles for relevance with optional force refresh."""
        scored_articles = []
        total_tokens = 0
        
        for article in articles:
            try:
                analysis_article = self._convert_db_article(db, article)
                score_result = self._score_article_relevance(
                    analysis_article, force_refresh_scores
                )

                if score_result["success"]:
                    scored_articles.append(
                        {
                            "article": article,
                            "analysis_article": analysis_article,
                            "score": score_result["score"],
                            "practice_areas": score_result["practice_areas"],
                            "dollar_amount": score_result["dollar_amount"],
                            "whistleblower_indicators": score_result[
                                "whistleblower_indicators"
                            ],
                            "blog_potential": score_result.get("blog_potential", "Low"),
                            "summary": score_result["summary"],
                        }
                    )
                    total_tokens += score_result.get("tokens_used", 0)
            except Exception as e:
                self._log_error(f"Error scoring article {article.id}: {str(e)}")
                continue
        
        return scored_articles, total_tokens
    
    def _select_articles_for_analysis(
        self,
        high_priority_articles: List[Dict],
        relevant_articles: List[Dict],
        high_priority_only: bool,
    ) -> List[Dict]:
        """Select which articles to analyze based on priority setting."""
        if high_priority_only:
            # Default behavior: only high priority articles get detailed analysis
            articles_for_analysis = high_priority_articles
            self._emit_progress(
                f"Generating detailed analysis for {len(high_priority_articles)} high priority articles..."
            )
        else:
            # New behavior: all relevant articles get detailed analysis
            articles_for_analysis = relevant_articles
            self._emit_progress(
                f"Generating detailed analysis for ALL {len(relevant_articles)} relevant articles..."
            )
        
        return articles_for_analysis
    
    def _verify_report_citations(self, combined_analysis: str) -> Tuple[str, int]:
        """Verify citations in the report if verification is enabled."""
        verification_tokens = 0
        
        try:
            self._emit_progress("Verifying...")
            verify_result = self.citation_verifier.verify_report_citations(
                combined_analysis
            )
            
            if verify_result["success"]:
                combined_analysis = verify_result["final_content"]
                verification_tokens = sum(
                    result.get("verification_details", {}).get("tokens_used", 0)
                    for result in verify_result.get("verification_results", [])
                )
                
                self._emit_progress(f"Verified: {verify_result['fully_verified']}")
                self._emit_progress(
                    f"Iterations: {verify_result['iterations_performed']}"
                )
            else:
                self._emit_progress("Verification failed")
        except Exception as e:
            self._log_error(f"Error in citation verification: {str(e)}")
        
        return combined_analysis, verification_tokens
    
    def _create_intelligence_report_record(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        combined_analysis: str,
        scored_articles: List[Dict],
        relevant_articles: List[Dict],
        high_priority_articles: List[Dict],
        detailed_analyses: List[Dict],
        total_tokens: int,
        high_priority_only: bool,
    ) -> Dict[str, Any]:
        """Create and save the intelligence report record to the database."""
        try:
            date_range = (
                f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                if start_date.date() != end_date.date()
                else start_date.strftime("%Y-%m-%d")
            )
            report_title = f"Intelligence Report - {date_range}"
            
            report = Report(
                title=report_title,
                report_type="intelligence",
                start_date=start_date,
                end_date=end_date,
                analysis=combined_analysis,
                summary=f"Analysis of {len(scored_articles)} articles, {len(detailed_analyses)} with detailed outlines",
                article_count=len(scored_articles),
                tokens_used=total_tokens,
                high_priority_only=high_priority_only,
            )
            
            db.add(report)
            db.flush()
            
            # Link all relevant articles to report (not just high-priority ones)
            for item in relevant_articles:
                report_article = ReportArticle(
                    report_id=report.id, article_id=item["article"].id
                )
                db.add(report_article)
            
            return {
                "success": True,
                "report_id": report.id,
                "title": report_title,
                "analysis": combined_analysis,
                "summary": f"Analysis of {len(scored_articles)} articles, {len(detailed_analyses)} with detailed outlines",
                "article_count": len(scored_articles),
                "high_priority_count": len(high_priority_articles),
                "detailed_analyses_count": len(detailed_analyses),
                "tokens_used": total_tokens,
                "start_date": start_date,
                "end_date": end_date,
            }
        except Exception as e:
            self._log_error(f"Error creating intelligence report record: {str(e)}")
            raise
    
    def _generate_intelligence_report_from_ids(
        self,
        article_ids: List[int],
        force_refresh_scores: bool = False,
        force_refresh_analysis: bool = False,
        enable_insights: bool = False,
        high_priority_only: bool = True,
    ) -> Dict[str, Any]:
        """Generate intelligence report from specific article IDs."""
        
        db = get_db()
        # Initialize variables to avoid UnboundLocalError
        relevant_articles = []
        high_priority_articles = []
        detailed_analyses = []
        total_tokens = 0
        
        try:
            # Step 1: Get specific articles by IDs
            articles = self._get_articles_by_ids(db, article_ids)
            
            if not articles:
                return {
                    "success": False,
                    "error": f"No articles found for the selected IDs: {article_ids}",
                }
            
            self._emit_progress(f"Found {len(articles)} selected articles for analysis")
            
            # Step 2: Score all articles for relevance (same as original method)
            scored_articles = []
            
            for article in articles:
                analysis_article = self._convert_db_article(db, article)
                score_result = self._score_article_relevance(
                    analysis_article, force_refresh_scores
                )

                if score_result["success"]:
                    scored_articles.append(
                        {
                            "article": article,
                            "analysis_article": analysis_article,
                            "score": score_result["score"],
                            "practice_areas": score_result["practice_areas"],
                            "dollar_amount": score_result["dollar_amount"],
                            "whistleblower_indicators": score_result[
                                "whistleblower_indicators"
                            ],
                            "blog_potential": score_result.get("blog_potential", "Low"),
                            "summary": score_result["summary"],
                        }
                    )
                    total_tokens += score_result.get("tokens_used", 0)
            
            # Step 3: Filter by relevance and priority (same logic as original)
            relevant_articles = [
                item for item in scored_articles if item["score"] >= 50
            ]
            high_priority_articles = [
                item for item in scored_articles if item["score"] >= 80
            ]

            self._emit_progress(
                f"Relevant articles (score ≥50): {len(relevant_articles)}"
            )
            self._emit_progress(
                f"High priority articles (score ≥80): {len(high_priority_articles)}"
            )
            
            # Create report and link articles (same as original)
            date_range_start = (
                min(article.published_date for article in articles)
                if articles
                else datetime.now()
            )
            date_range_end = (
                max(article.published_date for article in articles)
                if articles
                else datetime.now()
            )
            
            report = Report(
                title=f"Intelligence Report - Selected Articles ({date_range_start.strftime('%Y-%m-%d')} to {date_range_end.strftime('%Y-%m-%d')})",
                report_type="intelligence",
                start_date=date_range_start,
                end_date=date_range_end,
                analysis="",  # Will be populated below
                summary=f"Analysis of {len(scored_articles)} selected articles, focusing on {len(high_priority_articles)} high priority items",
                article_count=len(scored_articles),
                tokens_used=total_tokens,
            )
            
            db.add(report)
            db.flush()  # Get report ID
            
            # Link relevant articles to report  
            for item in relevant_articles:
                report_article = ReportArticle(
                    report_id=report.id, article_id=item["article"].id
                )
                db.add(report_article)
            
            # Rest follows same logic as original method...
            # (This is getting long, so I'll continue with the key parts)
            
            # Step 4: Generate detailed analysis 
            # Choose which articles to analyze based on high_priority_only setting
            if high_priority_only:
                # Default behavior: only high priority articles get detailed analysis
                articles_for_analysis = high_priority_articles
                self._emit_progress(
                    f"Generating detailed analysis for {len(high_priority_articles)} high priority articles..."
                )
            else:
                # New behavior: all selected articles get detailed analysis
                articles_for_analysis = scored_articles
                self._emit_progress(
                    f"Generating detailed analysis for ALL {len(scored_articles)} selected articles..."
                )
            
            if articles_for_analysis:
                for item in articles_for_analysis:
                    article = item["article"]
                    analysis_article = item["analysis_article"]

                    detail_result = self._generate_individual_analysis(
                        analysis_article, force_refresh_analysis, enable_insights
                    )
                    if detail_result["success"]:
                        detailed_analyses.append(
                            {
                                "article": article,
                                "analysis": detail_result["analysis"],
                                "title": analysis_article.title,
                                "url": analysis_article.url,
                                "published_date": analysis_article.published_date.strftime(
                                    "%Y-%m-%d"
                                ),
                                "score": item["score"],
                                "practice_areas": item["practice_areas"],
                                "dollar_amount": item["dollar_amount"],
                                "whistleblower_indicators": item[
                                    "whistleblower_indicators"
                                ],
                                "blog_potential": item.get("blog_potential", "Low"),
                            }
                        )
                        total_tokens += detail_result.get("tokens_used", 0)
            
            # Generate final analysis content
            analysis_content = self._create_intelligence_report(
                detailed_analyses, scored_articles, date_range_start, date_range_end
            )
            
            # Update report with final analysis
            report.analysis = analysis_content
            report.tokens_used = total_tokens
            db.commit()
            
            return {
                "success": True,
                "report_id": report.id,
                "analysis": analysis_content,
                "summary": f"Analysis of {len(scored_articles)} selected articles, {len(detailed_analyses)} with detailed outlines",
                "article_count": len(scored_articles),
                "high_priority_count": len(high_priority_articles),
                "detailed_analyses_count": len(detailed_analyses),
                "tokens_used": total_tokens,
                "start_date": date_range_start,
                "end_date": date_range_end,
            }
            
        finally:
            db.close()
    
    def _get_articles_by_ids(
        self, db: Session, article_ids: List[int]
    ) -> List[Article]:
        """Get articles by specific IDs."""
        return db.query(Article).filter(Article.id.in_(article_ids)).all()
    
    def _get_articles_for_period(
        self, db: Session, start_date: datetime, end_date: datetime
    ) -> List[Article]:
        """Get articles for the specified time period."""
        return (
            db.query(Article)
            .filter(
            and_(
                Article.published_date >= start_date,
                    Article.published_date < end_date,
            )
            )
            .all()
        )
    
    def _load_prompt_template(self, filename: str) -> str:
        """Load prompt template from file."""
        from ..config.distribution import get_distribution_manager
        
        # Use distribution manager for prompts directory
        dist_manager = get_distribution_manager()
        prompts_dir = dist_manager.get_prompts_directory()
        prompt_path = prompts_dir / filename
        
        try:
            with open(prompt_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to basic template
            return """
Analyze the following articles and provide insights:

{articles}

Please provide a comprehensive analysis covering key developments, trends, and implications.
"""
    
    def _convert_db_article(self, db: Session, db_article: Article):
        """Convert database article to analysis format."""
        # Get source name
        source = db.query(Source).filter_by(id=db_article.source_id).first()
        source_name = source.name if source else "Unknown"
        
        # Create a simple object with necessary attributes
        class AnalysisArticle:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        # Convert tags
        tags = db_article.tags.split(",") if db_article.tags else []
        
        article = AnalysisArticle(
            title=db_article.title,
            content=db_article.content,
            url=db_article.url,
            published_date=db_article.published_date,
            author=db_article.author,
            category=db_article.category,
            tags=tags,
            source_name=source_name,
            db_article_id=db_article.id,
        )
        
        # Add relevance data if it exists
        article.relevance_score = db_article.relevance_score
        article.practice_areas = db_article.practice_areas
        article.dollar_amount = db_article.dollar_amount
        article.whistleblower_indicators = db_article.whistleblower_indicators
        article.blog_potential = db_article.blog_potential
        article.relevance_summary = db_article.relevance_summary
        
        # Add detailed analysis cache data if it exists
        article.detailed_analysis = db_article.detailed_analysis
        article.detailed_analysis_tokens = db_article.detailed_analysis_tokens
        article.detailed_analysis_at = db_article.detailed_analysis_at
        
        return article
    
    def _score_article_relevance(
        self, article, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Score an article for relevance to fraud/qui-tam practice."""
        try:
            # Check for cached scores first (unless force_refresh is True)
            if (
                not force_refresh
                and hasattr(article, "relevance_score")
                and article.relevance_score is not None
            ):
                self._emit_progress(f"Cached: {article.title}...")
                
                # Parse practice areas from JSON if stored as JSON string
                practice_areas = []
                if article.practice_areas:
                    try:
                        import json

                        practice_areas = json.loads(article.practice_areas)
                    except (json.JSONDecodeError, TypeError):
                        # Fallback: treat as comma-separated string
                        practice_areas = [
                            area.strip()
                            for area in article.practice_areas.split(",")
                            if area.strip()
                        ]
                
                return {
                    "success": True,
                    "score": article.relevance_score,
                    "practice_areas": practice_areas,
                    "dollar_amount": article.dollar_amount or "Not specified",
                    "whistleblower_indicators": article.whistleblower_indicators
                    or "No",
                    "blog_potential": article.blog_potential or "Low",
                    "summary": article.relevance_summary or "No summary available",
                    "tokens_used": 0,  # No tokens used for cached result
                }
            
            self._emit_progress(f"Scoring: {article.title}...")
            
            # Load relevance scoring prompt
            prompt_template = self._load_prompt_template("relevance_scorer.txt")
            
            # Prepare article content
            article_content = f"Title: {article.title}\n\nContent: {article.content}"
            
            # Generate relevance score
            analysis_result = self.openai_analyzer.analyze_articles(
                [article], prompt_template, {"article_content": article_content}
            )
            
            if not analysis_result["success"]:
                return {"success": False, "error": analysis_result.get("error")}
            
            # Parse the scoring response
            score_data = self._parse_relevance_score(analysis_result["analysis"])
            
            # Save the scoring results to the database (pass the original DB article)
            if hasattr(article, "db_article_id"):
                self._save_relevance_score_to_db_by_id(
                    article.db_article_id, score_data
                )
            
            return {
                "success": True,
                "score": score_data["score"],
                "practice_areas": score_data["practice_areas"],
                "dollar_amount": score_data["dollar_amount"],
                "whistleblower_indicators": score_data["whistleblower_indicators"],
                "blog_potential": score_data["blog_potential"],
                "summary": score_data["summary"],
                "tokens_used": analysis_result["tokens_used"],
            }
            
        except APIKeyInvalidError as e:
            self._emit_progress(f"Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "api_key_invalid"}
            
        except OpenAIAPIError as e:
            self._emit_progress(f"OpenAI API Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "openai_api_error"}
            
        except Exception as e:
            print(f"Error scoring article relevance: {e}")
            return {"success": False, "error": str(e), "error_type": "general_error"}
    
    def _parse_relevance_score(self, score_text: str) -> Dict[str, Any]:
        """Parse the relevance scoring response."""
        try:
            # Default values
            result = {
                "score": 0,
                "practice_areas": [],
                "dollar_amount": "Not specified",
                "whistleblower_indicators": "No",
                "blog_potential": "Low",
                "summary": "No summary available",
            }
            
            # Parse structured response
            lines = score_text.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("RELEVANCE_SCORE:"):
                    try:
                        result["score"] = int(re.findall(r"\d+", line)[0])
                    except (IndexError, ValueError):
                        result["score"] = 0
                elif line.startswith("PRACTICE_AREAS:"):
                    areas_text = line.split(":", 1)[1].strip()
                    result["practice_areas"] = [
                        area.strip() for area in areas_text.split(",") if area.strip()
                    ]
                elif line.startswith("DOLLAR_AMOUNT:"):
                    result["dollar_amount"] = line.split(":", 1)[1].strip()
                elif line.startswith("WHISTLEBLOWER_INDICATORS:"):
                    result["whistleblower_indicators"] = line.split(":", 1)[1].strip()
                elif line.startswith("BLOG_POTENTIAL:"):
                    result["blog_potential"] = line.split(":", 1)[1].strip()
                elif line.startswith("SUMMARY:"):
                    result["summary"] = line.split(":", 1)[1].strip()
            
            return result
            
        except Exception as e:
            print(f"Error parsing relevance score: {e}")
            return {
                "score": 0,
                "practice_areas": [],
                "dollar_amount": "Not specified",
                "whistleblower_indicators": "No",
                "blog_potential": "Low",
                "summary": "Parsing error",
            }

    def _save_relevance_score_to_db_by_id(
        self, article_id: int, score_data: Dict[str, Any]
    ):
        """Save relevance scoring results to the database by article ID."""
        import json
        import time
        import sqlite3
        from datetime import datetime
        
        max_retries = 5
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            db = None
            try:
                # Get a fresh database session
                db = get_db()
                
                # Use a transaction block for autocommit mode
                with db.begin():
                    # Find the article in the database
                    from ..database.models import Article as DBArticle

                    db_article = db.query(DBArticle).filter_by(id=article_id).first()
                    
                    if db_article:
                        # Update relevance scoring fields
                        db_article.relevance_score = score_data["score"]
                        db_article.practice_areas = json.dumps(
                            score_data["practice_areas"]
                        )
                        db_article.dollar_amount = score_data["dollar_amount"]
                        db_article.whistleblower_indicators = score_data[
                            "whistleblower_indicators"
                        ]
                        db_article.blog_potential = score_data["blog_potential"]
                        db_article.relevance_summary = score_data["summary"]
                        db_article.relevance_scored_at = datetime.now()
                        
                        # Explicit flush to ensure the data is written
                        db.flush()
                        
                self._emit_progress(f"Saved score: {score_data['score']}")
                return  # Success - exit retry loop
                    
            except (sqlite3.OperationalError, Exception) as e:
                if attempt < max_retries - 1 and (
                    "database is locked" in str(e).lower() or "locked" in str(e).lower()
                ):
                    print(
                        f"Database locked, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Gentler backoff
                    continue
                else:
                    print(f"Error saving relevance score to database: {e}")
                    break
            finally:
                if db:
                    db.close()
    
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
        
        # Handle cases where OpenAI responds with "json" before the actual JSON
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()  # Remove "json" prefix
            
        # Validate that it's actually JSON
        import json

        try:
            json.loads(cleaned)
            return cleaned
        except:
            # If it's not valid JSON, return the original
            return json_text

    def _save_detailed_analysis_to_db(self, article, analysis_result: Dict[str, Any]):
        """Save detailed analysis results to database for caching."""
        import time
        import sqlite3
        
        max_retries = 5
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            db = None
            try:
                db = get_db()
                
                # Get the article record using the stored db_article_id
                article_id = getattr(article, "db_article_id", None)
                if not article_id:
                    print(f"No ID: {article.title}...")
                    return
                
                # Use a transaction block for autocommit mode
                with db.begin():
                    db_article = db.query(Article).filter_by(id=article_id).first()
                    if db_article:
                        # Update detailed analysis fields
                        db_article.detailed_analysis = analysis_result.get("analysis")
                        # Clean and store JSON for structured access
                        raw_json = analysis_result.get("analysis_json", "")
                        cleaned_json = self._clean_json_content(raw_json)
                        db_article.detailed_analysis_json = cleaned_json
                        db_article.detailed_analysis_tokens = analysis_result.get(
                            "tokens_used", 0
                        )
                        db_article.detailed_analysis_at = datetime.now()
                        
                        # Explicit flush to ensure the data is written
                        db.flush()
                        
                self._emit_progress(f"Cached analysis: {article.title}...")
                return  # Success - exit retry loop
                
            except (sqlite3.OperationalError, Exception) as e:
                if attempt < max_retries - 1 and (
                    "database is locked" in str(e).lower() or "locked" in str(e).lower()
                ):
                    print(
                        f"Database locked, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Gentler backoff
                    continue
                else:
                    print(f"Error saving detailed analysis to database: {e}")
                    break
            finally:
                if db:
                    db.close()
    
    def _generate_individual_analysis(
        self, article, force_refresh: bool = False, enable_insights: bool = False
    ) -> Dict[str, Any]:
        """Generate two-stage detailed analysis for a high-priority article with caching support."""
        import json

        try:
            # Check for cached analysis first (unless force refresh)
            if (
                not force_refresh
                and hasattr(article, "detailed_analysis")
                and article.detailed_analysis
            ):
                # If insights are requested, check if we have combined analysis with insights
                if (
                    enable_insights
                    and hasattr(article, "detailed_analysis_json")
                    and article.detailed_analysis_json
                ):
                    try:
                        import json

                        cleaned_json = self._clean_json_content(
                            article.detailed_analysis_json
                        )
                        analysis_data = json.loads(cleaned_json)
                        
                        # Check if we have both article and insight analysis (market intelligence)
                        if (
                            "article_analysis" in analysis_data
                            and "insight_analysis" in analysis_data
                        ):
                            self._emit_progress(
                                f"Using cache with insights: {article.title}..."
                            )
                            return {
                                "analysis": article.detailed_analysis,
                                "tokens_used": 0,  # No tokens used for cached result
                                "success": True,
                                "cached": True,
                            }
                        else:
                            # We have cached article analysis but need to generate insights
                            self._emit_progress(
                                f"Cache missing insights, regenerating: {article.title}..."
                            )
                            # Don't return here - continue to regeneration logic
                    except (json.JSONDecodeError, KeyError):
                        # JSON parsing failed, regenerate
                        self._emit_progress(
                            f"Cache corrupted, regenerating: {article.title}..."
                        )
                elif not enable_insights:
                    # No insights requested, use cached article analysis
                    self._emit_progress(f"Using cache: {article.title}...")
                    return {
                        "analysis": article.detailed_analysis,
                        "tokens_used": 0,  # No tokens used for cached result
                        "success": True,
                        "cached": True,
                    }
            
            # Stage 1: Generate article analysis with enhanced commentary hooks
            self._emit_progress(f"Analyzing: {article.title}...")
            
            article_analysis = self._generate_article_analysis(article)
            if not article_analysis.get("success"):
                return article_analysis
            
            # Stage 2: Generate insight analysis with external research (if enabled)
            if enable_insights:
                self._emit_progress(f"Research: {article.title}...")
                
                insight_analysis = self._generate_insight_analysis(
                    article, article_analysis
                )
                if not insight_analysis.get("success"):
                    # Return article analysis even if insight analysis fails
                    print(
                        f"Warning: Insight analysis failed, using article analysis only"
                    )
                    final_result = article_analysis
                else:
                    # Combine both analyses
                    combined_analysis = self._combine_analyses(
                        article_analysis, insight_analysis
                    )
                    final_result = {
                        "analysis": combined_analysis["formatted_text"],
                        "analysis_json": combined_analysis["raw_json"],
                        "parsed_sections": combined_analysis["parsed_sections"],
                        "tokens_used": article_analysis.get("tokens_used", 0)
                        + insight_analysis.get("tokens_used", 0),
                        "success": True,
                        "cached": False,
                        "stages": ["article_analysis", "insight_analysis"],
                    }
            else:
                # Only article analysis stage - store the structured JSON directly
                article_text = article_analysis.get("analysis", "")
                final_result = {
                    "analysis": article_text,
                    "analysis_json": article_text,  # Store the raw JSON structure directly
                    "tokens_used": article_analysis.get("tokens_used", 0),
                    "success": True,
                    "cached": False,
                    "stages": ["article_analysis"],
                }
            
            # Cache the result if successful
            if final_result.get("success"):
                self._save_detailed_analysis_to_db(article, final_result)
            
            return final_result
            
        except Exception as e:
            print(f"Error generating individual analysis: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_article_analysis(self, article) -> Dict[str, Any]:
        """Stage 1: Generate article analysis with enhanced commentary hooks."""
        try:
            # Load individual article analysis prompt
            prompt_template = self._load_prompt_template("article_analysis.txt")
            
            # Prepare context data
            context_data = {
                "article_content": article.content,
                "article_url": article.url,
                "article_date": (
                    article.published_date.strftime("%Y-%m-%d")
                    if article.published_date
                    else "Unknown"
                ),
            }
            
            # Generate detailed analysis
            return self.openai_analyzer.analyze_articles(
                [article], prompt_template, context_data
            )
            
        except APIKeyInvalidError as e:
            self._emit_progress(f"Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "api_key_invalid"}
            
        except OpenAIAPIError as e:
            self._emit_progress(f"OpenAI API Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "openai_api_error"}
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Article analysis failed: {str(e)}",
                "error_type": "general_error",
            }

    def _generate_insight_analysis(
        self, article, article_analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stage 2: Generate insight analysis with external research based on commentary hook."""
        try:
            # Extract hook and validation from article analysis
            article_text = article_analysis_result.get("analysis", "")
            primary_hook = self._extract_primary_hook(article_text)
            hook_validation = self._extract_hook_validation(article_text)
            secondary_angles = self._extract_secondary_angles(article_text)
            
            # Load insight analysis prompt
            prompt_template = self._load_prompt_template("insight_analysis.txt")
            
            # Prepare context data for insight analysis
            context_data = {
                "article_title": article.title,
                "article_url": article.url,
                "article_date": (
                    article.published_date.strftime("%Y-%m-%d")
                    if article.published_date
                    else "Unknown"
                ),
                "article_industry": self._extract_industry_from_article(article),
                "primary_hook": primary_hook,
                "hook_validation": hook_validation,
                "secondary_angles": secondary_angles,
            }
            
            # Generate insight analysis with web search (o3 model)
            return self.openai_analyzer.analyze_with_research(
                [article], prompt_template, context_data, enable_web_search=True
            )
            
        except Exception as e:
            print(f"Insight analysis exception details: {e}")
            print(f"Exception type: {type(e)}")
            import traceback

            traceback.print_exc()
            return {"success": False, "error": f"Insight analysis failed: {str(e)}"}
    
    def _extract_primary_hook(self, analysis_text: str) -> str:
        """Extract primary hook from article analysis."""
        import re

        hook_match = re.search(
            r"\*\*PRIMARY HOOK:\*\*\s*(.+?)(?=\n\*\*|$)", analysis_text, re.DOTALL
        )
        return (
            hook_match.group(1).strip()
            if hook_match
            else "Novel enforcement approach requiring further investigation"
        )
    
    def _extract_hook_validation(self, analysis_text: str) -> str:
        """Extract hook validation from article analysis."""
        import re

        validation_match = re.search(
            r"\*\*HOOK VALIDATION:\*\*\s*(.+?)(?=\n\*\*|$)", analysis_text, re.DOTALL
        )
        return (
            validation_match.group(1).strip()
            if validation_match
            else "Significant enforcement development"
        )
    
    def _extract_secondary_angles(self, analysis_text: str) -> str:
        """Extract secondary angles from article analysis."""
        import re

        angles_match = re.search(
            r"\*\*SECONDARY ANGLES:\*\*\s*(.+?)(?=\n\*\*|$)", analysis_text, re.DOTALL
        )
        return (
            angles_match.group(1).strip()
            if angles_match
            else "Additional enforcement trends and implications"
        )
    
    def _extract_industry_from_article(self, article) -> str:
        """Extract industry/sector from article content or category."""
        if hasattr(article, "category") and article.category:
            return article.category
        
        # Simple keyword-based industry detection
        content_lower = article.content.lower()
        if any(
            word in content_lower
            for word in ["healthcare", "hospital", "medical", "physician"]
        ):
            return "Healthcare"
        elif any(
            word in content_lower
            for word in ["financial", "bank", "securities", "investment"]
        ):
            return "Financial Services"
        elif any(
            word in content_lower
            for word in ["technology", "software", "data", "cyber"]
        ):
            return "Technology"
        elif any(
            word in content_lower for word in ["government", "federal", "contractor"]
        ):
            return "Government Contracting"
        else:
            return "General"
    
    def _combine_analyses(
        self, article_analysis: Dict[str, Any], insight_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine JSON-structured article analysis and insight analysis into cohesive report."""
        import json
        
        article_text = article_analysis.get("analysis", "")
        insight_text = insight_analysis.get("analysis", "")
        
        # Store raw JSON for later use
        combined_json = {
            "article_analysis": article_text,
            "insight_analysis": insight_text,
        }
        
        # Try to parse article analysis as JSON first
        try:
            cleaned_article_text = self._clean_json_content(article_text)
            article_json = json.loads(cleaned_article_text)
            article_sections = self._format_json_article_analysis(article_json)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Article JSON parsing failed, falling back to text extraction: {e}")
            # Fall back to old text-based extraction
            article_sections = self._extract_article_sections(article_text)
        
        # Try to parse insight analysis as JSON
        try:
            cleaned_insight_text = self._clean_json_content(insight_text)
            insight_json = json.loads(cleaned_insight_text)
            market_intelligence = self._format_json_market_intelligence(insight_json)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Insight JSON parsing failed, falling back to text extraction: {e}")
            # Fall back to old text-based extraction
            market_intelligence = self._extract_market_intelligence(insight_text)
        
        # Create streamlined combined report
        combined = f"""# COMPREHENSIVE LEGAL ANALYSIS & MARKET INTELLIGENCE

## EXECUTIVE SUMMARY
{article_sections.get('overview', 'Analysis overview not available.')}

## CASE ANALYSIS
{article_sections.get('case_facts', 'Case details not available.')}

{article_sections.get('legal_analysis', 'Legal analysis not available.')}

## INSIGHTS & EXTERNAL RESEARCH
{market_intelligence.get('comparable_cases', 'Comparable case analysis not available.')}

{market_intelligence.get('regulatory_trends', 'Regulatory trend analysis not available.')}

{market_intelligence.get('market_impact', 'Market impact analysis not available.')}

## BLOG POST OUTLINE
{article_sections.get('blog_outline', 'Blog outline not available.')}
"""
        
        return {
            "formatted_text": combined,
            "raw_json": json.dumps(combined_json),
            "parsed_sections": {
                "article_sections": article_sections,
                "market_intelligence": market_intelligence,
            },
        }
    
    def _format_json_market_intelligence(self, insight_json: dict) -> Dict[str, str]:
        """Format JSON-structured insight analysis into markdown sections."""
        sections = {}
        
        # Format comparable cases section
        if "comparable_cases" in insight_json:
            cases_md = []
            for i, case in enumerate(insight_json["comparable_cases"], 1):
                case_md = f"""### {i}. {case.get('case_name', f'Case {i}')}
- **Similarity:** {case.get('similarity', 'Not specified')}
- **Key Differences:** {case.get('key_differences', 'Not specified')}
- **Penalty/Outcome:** {case.get('penalty_outcome', 'Not specified')}
- **Industry Reaction:** {case.get('industry_reaction', 'Not specified')}
"""
                cases_md.append(case_md)
            sections["comparable_cases"] = "\n".join(cases_md)
        
        # Format regulatory intelligence section
        if "regulatory_intelligence" in insight_json:
            reg_intel = insight_json["regulatory_intelligence"]
            reg_md = []
            
            if "agency_guidance" in reg_intel:
                reg_md.append("#### Agency Guidance & Statements")
                for guidance in reg_intel["agency_guidance"]:
                    if isinstance(guidance, dict):
                        source = guidance.get("source", "Unknown source")
                        url = guidance.get("source_url", "")
                        detail = guidance.get("detail", guidance.get("details", ""))
                        if url:
                            reg_md.append(f"- **[{source}]({url}):** {detail}")
                        else:
                            reg_md.append(f"- **{source}:** {detail}")
                    else:
                        reg_md.append(f"- {guidance}")
                reg_md.append("")
            
            if "congressional_activity" in reg_intel:
                reg_md.append("#### Congressional Activity")
                for activity in reg_intel["congressional_activity"]:
                    if isinstance(activity, dict):
                        source = activity.get("source", "Unknown source")
                        url = activity.get("source_url", "")
                        detail = activity.get("detail", activity.get("details", ""))
                        if url:
                            reg_md.append(f"- **[{source}]({url}):** {detail}")
                        else:
                            reg_md.append(f"- **{source}:** {detail}")
                    else:
                        reg_md.append(f"- {activity}")
                reg_md.append("")
            
            if "industry_responses" in reg_intel:
                reg_md.append("#### Industry Advisory Responses")
                for response in reg_intel["industry_responses"]:
                    if isinstance(response, dict):
                        source = response.get("source", "Unknown source")
                        url = response.get("source_url", "")
                        detail = response.get("detail", response.get("details", ""))
                        if url:
                            reg_md.append(f"- **[{source}]({url}):** {detail}")
                        else:
                            reg_md.append(f"- **{source}:** {detail}")
                    else:
                        reg_md.append(f"- {response}")
                reg_md.append("")
            
            sections["regulatory_trends"] = "\n".join(reg_md)
        
        # Format market impact section
        if "market_impact" in insight_json:
            market = insight_json["market_impact"]
            market_md = []
            
            if "stock_responses" in market:
                market_md.append("#### Stock Market Response")
                for response in market["stock_responses"]:
                    if isinstance(response, dict):
                        source = response.get("source", "Unknown source")
                        url = response.get("source_url", "")
                        if url:
                            market_md.append(f"- **[{source}]({url})**")
                        else:
                            market_md.append(f"- {source}")
                    else:
                        market_md.append(f"- {response}")
                market_md.append("")
            
            if "insurance_risk" in market:
                market_md.append("#### Insurance & Risk Mitigation")
                for risk in market["insurance_risk"]:
                    if isinstance(risk, dict):
                        source = risk.get("source", "Unknown source")
                        url = risk.get("source_url", "")
                        if url:
                            market_md.append(f"- **[{source}]({url})**")
                        else:
                            market_md.append(f"- {source}")
                    else:
                        market_md.append(f"- {risk}")
                market_md.append("")
            
            if "compliance_market" in market:
                market_md.append("#### Compliance Market Response")
                for compliance in market["compliance_market"]:
                    if isinstance(compliance, dict):
                        source = compliance.get("source", "Unknown source")
                        url = compliance.get("source_url", "")
                        if url:
                            market_md.append(f"- **[{source}]({url})**")
                        else:
                            market_md.append(f"- {source}")
                    else:
                        market_md.append(f"- {compliance}")
                market_md.append("")
            
            sections["market_impact"] = "\n".join(market_md)
        
        return sections
    
    def _format_json_article_analysis(self, article_json: dict) -> Dict[str, str]:
        """Format JSON-structured article analysis into markdown sections."""
        sections = {}
        
        # Format overview from case_overview
        if "case_overview" in article_json:
            overview = article_json["case_overview"]
            relevance = article_json.get("analysis_metadata", {}).get(
                "relevance_score", "MEDIUM"
            )
            overview_text = f"""Relevance score: {relevance}

{overview.get('summary', 'Case summary not available.')}

{overview.get('significance', 'Significance not specified.')}"""
            sections["overview"] = overview_text
        
        # Format case facts from fact_pattern
        if "fact_pattern" in article_json:
            fact_pattern = article_json["fact_pattern"]
            
            # Parties section - handle both flat list and nested dict structures
            parties_md = []
            if "parties" in fact_pattern:
                parties = fact_pattern["parties"]
                
                if isinstance(parties, list):
                    # AI generated flat list
                    parties_md.append("**Parties Involved:**")
                    for party in parties:
                        parties_md.append(f"- {party}")
                elif isinstance(parties, dict):
                    # Expected nested structure
                    if "defendants" in parties:
                        parties_md.append("**Primary Defendants:**")
                        for defendant in parties["defendants"]:
                            parties_md.append(f"- {defendant}")
                    
                    if "government_agencies" in parties:
                        parties_md.append("\n**Government Agencies:**")
                        for agency in parties["government_agencies"]:
                            parties_md.append(f"- {agency}")
                    
                    if "whistleblowers" in parties:
                        parties_md.append("\n**Whistleblowers:**")
                        for whistleblower in parties["whistleblowers"]:
                            parties_md.append(f"- {whistleblower}")
            
            # Misconduct section - handle both string and nested dict structures
            misconduct_md = []
            if "misconduct_details" in fact_pattern:
                # AI generated string format
                misconduct_md.append("**Alleged Misconduct:**")
                misconduct_md.append(fact_pattern["misconduct_details"])
            elif "misconduct" in fact_pattern:
                # Expected nested structure
                misconduct = fact_pattern["misconduct"]
                misconduct_md.append("**Alleged Misconduct:**")
                if "mechanisms" in misconduct:
                    for mechanism in misconduct["mechanisms"]:
                        misconduct_md.append(f"- {mechanism}")
                
                if "duration" in misconduct:
                    misconduct_md.append(f"\n**Duration:** {misconduct['duration']}")
                
                if "financial_impact" in misconduct:
                    financial = misconduct["financial_impact"]
                    misconduct_md.append("\n**Financial Impact:**")
                    for key, value in financial.items():
                        if value:
                            misconduct_md.append(
                                f"- {key.replace('_', ' ').title()}: {value}"
                            )
            
            # Legal framework section - handle both list and nested dict structures
            legal_md = []
            if "legal_framework" in fact_pattern:
                legal = fact_pattern["legal_framework"]
                legal_md.append("**Legal Framework:**")
                
                if isinstance(legal, list):
                    # AI generated flat list
                    for statute in legal:
                        legal_md.append(f"- {statute}")
                elif isinstance(legal, dict):
                    # Expected nested structure
                    if "primary_statutes" in legal:
                        legal_md.append("- **Statutes:**")
                        for statute in legal["primary_statutes"]:
                            legal_md.append(f"  - {statute}")
                    
                    if "proceeding_type" in legal:
                        legal_md.append(
                            f"- **Proceedings:** {legal['proceeding_type']}"
                        )

                    if "case_number" in legal:
                        legal_md.append(f"- **Case Number:** {legal['case_number']}")
            
            case_facts = "\n".join(
                parties_md + ["\n"] + misconduct_md + ["\n"] + legal_md
            )
            sections["case_facts"] = case_facts
        
        # Format supporting quotes
        quotes_md = []
        if "supporting_quotes" in article_json:
            for i, quote in enumerate(article_json["supporting_quotes"], 1):
                quote_text = f"**SUPPORTING QUOTE #{i}:** \"{quote.get('quote', '')}\" --{quote.get('speaker', 'Unknown')}, {quote.get('title', '')}"
                quotes_md.append(quote_text)
        
        # Format legal analysis
        legal_analysis_md = []
        if "legal_analysis" in article_json:
            analysis = article_json["legal_analysis"]
            
            if "enforcement_trends" in analysis:
                trends = analysis["enforcement_trends"]
                legal_analysis_md.append("### Enforcement Trends & Precedent")
                
                if isinstance(trends, str):
                    # AI generated string format
                    legal_analysis_md.append(trends)
                elif isinstance(trends, dict):
                    # Expected nested structure
                    if "historical_context" in trends:
                        legal_analysis_md.append("**Historical Context:**")
                        for context in trends["historical_context"]:
                            legal_analysis_md.append(f"- {context}")
                    
                    if "unique_aspects" in trends:
                        legal_analysis_md.append("\n**Unique Aspects:**")
                        for aspect in trends["unique_aspects"]:
                            legal_analysis_md.append(f"- {aspect}")
            
            if "investigative_techniques" in analysis:
                techniques = analysis["investigative_techniques"]
                legal_analysis_md.append("\n### Investigative Techniques")
                
                if isinstance(techniques, str):
                    # AI generated string format
                    legal_analysis_md.append(techniques)
                elif isinstance(techniques, dict):
                    # Expected nested structure
                    if "methods" in techniques:
                        legal_analysis_md.append("**Methods:**")
                        for method in techniques["methods"]:
                            legal_analysis_md.append(f"- {method}")
                    
                    if "cooperation" in techniques:
                        legal_analysis_md.append("\n**Cooperation:**")
                        for coop in techniques["cooperation"]:
                            legal_analysis_md.append(f"- {coop}")
            
            if "whistleblower_analysis" in analysis:
                whistleblower = analysis["whistleblower_analysis"]
                legal_analysis_md.append("\n### Whistleblower Analysis")
                
                if isinstance(whistleblower, str):
                    # AI generated string format
                    legal_analysis_md.append(whistleblower)
                elif isinstance(whistleblower, dict):
                    # Expected nested structure
                    if "role_assessment" in whistleblower:
                        legal_analysis_md.append("**Role Assessment:**")
                        for role in whistleblower["role_assessment"]:
                            legal_analysis_md.append(f"- {role}")
                    
                    if "indicators" in whistleblower:
                        legal_analysis_md.append("\n**Indicators:**")
                        for indicator in whistleblower["indicators"]:
                            legal_analysis_md.append(f"- {indicator}")
                    
                    if "implications" in whistleblower:
                        legal_analysis_md.append("\n**Implications:**")
                        for implication in whistleblower["implications"]:
                            legal_analysis_md.append(f"- {implication}")
        
        # Combine legal analysis with quotes
        if quotes_md or legal_analysis_md:
            sections["legal_analysis"] = "\n".join(
                quotes_md + ["\n"] + legal_analysis_md
            )
        
        # Format blog outline
        if "blog_outline" in article_json:
            blog = article_json["blog_outline"]
            blog_md = []
            
            if "compelling_hooks" in blog:
                blog_md.append("### Compelling Hooks/Angles")
                for i, hook in enumerate(blog["compelling_hooks"], 1):
                    blog_md.append(f"{i}. {hook}")
            
            if "structure" in blog:
                structure = blog["structure"]
                blog_md.append("\n### Blog Post Structure")
                
                if "lead_paragraph" in structure:
                    blog_md.append(f"**Lead:** {structure['lead_paragraph']}")
                
                if "key_sections" in structure:
                    blog_md.append("\n**Key Sections:**")
                    for section in structure["key_sections"]:
                        blog_md.append(f"- **{section.get('title', 'Section')}**")
                        if "content_points" in section:
                            for point in section["content_points"]:
                                blog_md.append(f"  - {point}")
            
            if "practical_takeaways" in blog:
                takeaways = blog["practical_takeaways"]
                blog_md.append("\n### Practical Takeaways")
                
                # Handle both dict and list formats
                if isinstance(takeaways, dict):
                    # Expected format: {audience: [points]}
                    for audience, points in takeaways.items():
                        blog_md.append(f"**{audience.replace('_', ' ').title()}:**")
                        for point in points:
                            blog_md.append(f"- {point}")
                elif isinstance(takeaways, list):
                    # AI returned list format: [point1, point2, ...]
                    for point in takeaways:
                        blog_md.append(f"- {point}")
                else:
                    blog_md.append(f"- {str(takeaways)}")
            
            sections["blog_outline"] = "\n".join(blog_md)
        
        return sections
    
    def _extract_article_sections(self, article_text: str) -> Dict[str, str]:
        """Extract key sections from article analysis to avoid redundancy."""
        sections = {}
        
        # Extract overview section (first substantive paragraph)
        lines = article_text.split("\n")
        overview_started = False
        overview_lines = []
        
        for line in lines:
            if "OVERVIEW" in line or "Relevance Score:" in line:
                overview_started = True
                continue
            elif overview_started and line.strip():
                if (
                    line.startswith("#")
                    or line.startswith("**")
                    or "FACT PATTERN" in line
                ):
                    break
                overview_lines.append(line.strip())
        
        sections["overview"] = "\n".join(overview_lines)
        
        # Extract case facts (fact pattern section)
        case_facts_lines = []
        in_facts = False
        for line in lines:
            if "FACT PATTERN" in line or "Parties Involved" in line:
                in_facts = True
                continue
            elif in_facts and line.startswith("###") and "LEGAL ANALYSIS" in line:
                break
            elif in_facts and line.strip():
                case_facts_lines.append(line)
        
        sections["case_facts"] = "\n".join(case_facts_lines)
        
        # Extract legal analysis section
        legal_lines = []
        in_legal = False
        for line in lines:
            if "LEGAL ANALYSIS" in line:
                in_legal = True
                continue
            elif in_legal and line.startswith("###") and "BLOG POST" in line:
                break
            elif in_legal and line.strip():
                legal_lines.append(line)
        
        sections["legal_analysis"] = "\n".join(legal_lines)
        
        # Extract blog outline
        blog_lines = []
        in_blog = False
        for line in lines:
            if "BLOG POST OUTLINE" in line:
                in_blog = True
                continue
            elif in_blog and line.strip():
                blog_lines.append(line)
        
        sections["blog_outline"] = "\n".join(blog_lines)
        
        # Extract takeaways (practical takeaways section)
        takeaway_lines = []
        in_takeaways = False
        for line in lines:
            if "Practical Takeaways" in line or "TAKEAWAYS" in line:
                in_takeaways = True
                continue
            elif in_takeaways and (line.startswith("###") or line.startswith("##")):
                break
            elif in_takeaways and line.strip():
                takeaway_lines.append(line)
        
        sections["takeaways"] = "\n".join(takeaway_lines)
        
        return sections
    
    def _extract_market_intelligence(self, insight_text: str) -> Dict[str, str]:
        """Extract market intelligence sections from insight analysis."""
        sections = {}
        lines = insight_text.split("\n")
        
        # Extract comparable cases
        cases_lines = []
        in_cases = False
        for line in lines:
            if "COMPARABLE CASES" in line or "Case Name:" in line:
                in_cases = True
                continue
            elif in_cases and "REGULATORY INTELLIGENCE" in line:
                break
            elif in_cases and line.strip():
                cases_lines.append(line)
        
        sections["comparable_cases"] = "\n".join(cases_lines)
        
        # Extract regulatory trends
        regulatory_lines = []
        in_regulatory = False
        for line in lines:
            if "REGULATORY INTELLIGENCE" in line or "Agency Guidance" in line:
                in_regulatory = True
                continue
            elif in_regulatory and ("MARKET" in line or "FINANCIAL" in line):
                break
            elif in_regulatory and line.strip():
                regulatory_lines.append(line)
        
        sections["regulatory_trends"] = "\n".join(regulatory_lines)
        
        # Extract market impact
        market_lines = []
        in_market = False
        for line in lines:
            if "MARKET" in line and "IMPACT" in line:
                in_market = True
                continue
            elif in_market and "PREDICTIVE" in line:
                break
            elif in_market and line.strip():
                market_lines.append(line)
        
        sections["market_impact"] = "\n".join(market_lines)
        
        return sections
    
    def _create_article_report(
        self, detailed_analyses: List[Dict], all_relevant_articles: List[Dict]
    ) -> str:
        """Create article report with detailed outlines for high-priority and summaries for medium-priority."""
        try:
            if not all_relevant_articles:
                return "No relevant articles found for analysis."
            
            combined_content = []
            
            # Add header
            combined_content.append("# DAILY INTELLIGENCE REPORT")
            combined_content.append("=" * 60)
            combined_content.append(
                f"**Total Relevant Articles:** {len(all_relevant_articles)}"
            )
            combined_content.append(
                f"**High Priority (Blog Outlines):** {len(detailed_analyses)}"
            )
            combined_content.append(
                f"**Medium Priority (Summaries):** {len(all_relevant_articles) - len(detailed_analyses)}"
            )
            combined_content.append(
                f"**Report Generated:** {datetime.now().strftime('%B %d, %Y')}"
            )
            combined_content.append("=" * 60)
            
            # Create lookup for detailed analyses
            detailed_lookup = {
                analysis["article"].id: analysis for analysis in detailed_analyses
            }
            
            # Sort all relevant articles by score (highest first)
            sorted_articles = sorted(
                all_relevant_articles, key=lambda x: x["score"], reverse=True
            )
            
            # Section 1: High Priority Articles with Blog Outlines
            high_priority_count = 0
            for item in sorted_articles:
                if item["score"] >= 80 and item["article"].id in detailed_lookup:
                    if high_priority_count == 0:
                        combined_content.append(
                            "\n# HIGH PRIORITY ARTICLES - Blog Outlines"
                        )
                        combined_content.append("=" * 60)
                    high_priority_count += 1
                    
                    analysis = detailed_lookup[item["article"].id]
                    combined_content.append(
                        f"\n## ARTICLE {high_priority_count}: {analysis['article'].title}"
                    )
                    combined_content.append(
                        f"**Relevance Score:** {analysis['score']}/100"
                    )
                    combined_content.append(
                        f"**Practice Areas:** {', '.join(analysis['practice_areas'])}"
                    )
                    combined_content.append(
                        f"**Dollar Amount:** {analysis['dollar_amount']}"
                    )
                    combined_content.append(
                        f"**Whistleblower Indicators:** {analysis['whistleblower_indicators']}"
                    )
                    combined_content.append(
                        f"**Blog Potential:** {analysis['blog_potential']}"
                    )
                    combined_content.append(
                        f"**Source:** [{analysis['article'].url}]({analysis['article'].url})"
                    )
                    combined_content.append("-" * 60)
                    combined_content.append(analysis["analysis"])
                    combined_content.append("\n" + "-" * 60)
            
            # Section 2: Medium Priority Articles with Summaries
            medium_priority_count = 0
            for item in sorted_articles:
                if item["score"] >= 50 and item["score"] < 80:
                    if medium_priority_count == 0:
                        combined_content.append(
                            "\n# MEDIUM PRIORITY ARTICLES - Monitoring"
                        )
                        combined_content.append("=" * 60)
                    medium_priority_count += 1
                    
                    combined_content.append(
                        f"\n## ARTICLE {medium_priority_count}: {item['analysis_article'].title}"
                    )
                    combined_content.append(f"**Relevance Score:** {item['score']}/100")
                    combined_content.append(
                        f"**Practice Areas:** {', '.join(item['practice_areas'])}"
                    )
                    combined_content.append(
                        f"**Dollar Amount:** {item['dollar_amount']}"
                    )
                    combined_content.append(
                        f"**Whistleblower Indicators:** {item['whistleblower_indicators']}"
                    )
                    combined_content.append(
                        f"**Blog Potential:** {item['blog_potential']}"
                    )
                    combined_content.append(
                        f"**Source:** [{item['analysis_article'].url}]({item['analysis_article'].url})"
                    )
                    combined_content.append(f"**Summary:** {item['summary']}")
                    combined_content.append("-" * 40)
            
            return "\n".join(combined_content)
            
        except Exception as e:
            print(f"Error creating article report: {e}")
            return "Error generating article report"
    
    def _create_intelligence_report(
        self,
        detailed_analyses: List[Dict],
        all_scored_articles: List[Dict],
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """Create intelligence report with high-priority analyses and appendix of all articles."""
        try:
            combined_content = []

            # Overview Header
            date_range = (
                f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
                if start_date.date() != end_date.date()
                else start_date.strftime("%B %d, %Y")
            )
            
            # Count relevant articles by priority
            high_priority = len([a for a in all_scored_articles if a["score"] >= 80])
            medium_priority = len(
                [a for a in all_scored_articles if a["score"] >= 50 and a["score"] < 80]
            )
            total_relevant = len([a for a in all_scored_articles if a["score"] >= 50])
            
            combined_content.append(f"# Intelligence Report")
            combined_content.append(f"## {date_range}")
            combined_content.append("")
            combined_content.append("### Overview")
            combined_content.append("")
            combined_content.append(
                f"- **Total Articles Reviewed:** {len(all_scored_articles)}"
            )
            combined_content.append(
                f"- **Relevant to Practice:** {total_relevant} articles (≥50 score)"
            )
            combined_content.append(
                f"- **High Priority:** {high_priority} articles (≥80 score)"
            )
            combined_content.append(
                f"- **Medium Priority:** {medium_priority} articles (50-79 score)"
            )
            combined_content.append(
                f"- **Detailed Blog Outlines:** {len(detailed_analyses)} prepared"
            )
            combined_content.append("")
            
                        # Section 1: High Priority Articles with Detailed Blog Outlines
            if detailed_analyses:
                combined_content.append("---")
                combined_content.append("")
                combined_content.append("## High Priority Articles")
                combined_content.append(
                    "*Articles scoring ≥80 with detailed blog post outlines*"
                )
                combined_content.append("")

                # Sort by score (highest first)
                sorted_analyses = sorted(
                    detailed_analyses, key=lambda x: x["score"], reverse=True
                )

                for i, analysis in enumerate(sorted_analyses, 1):
                    combined_content.append(f"### {i}. {analysis['article'].title}")
                    combined_content.append("")
                    combined_content.append(
                        f"**Relevance Score:** {analysis['score']}/100 | **Dollar Amount:** {analysis['dollar_amount']} | **Blog Potential:** {analysis.get('blog_potential', 'Low')}"
                    )
                    combined_content.append("")
                    combined_content.append(
                        f"**Practice Areas:** {', '.join(analysis['practice_areas'])}"
                    )
                    combined_content.append("")
                    combined_content.append(
                        f"**Whistleblower Elements:** {analysis['whistleblower_indicators']}"
                    )
                    combined_content.append("")
                    combined_content.append(
                        f"**Source:** [{analysis['article'].url}]({analysis['article'].url})"
                    )
                    combined_content.append("")
                    combined_content.append("#### Detailed Analysis & Blog Outline")
                    combined_content.append("")
                    # Check if analysis content is JSON and format it properly
                    analysis_content = analysis["analysis"]
                    
                    # Check for JSON content (with or without markdown code fences)
                    content_stripped = analysis_content.strip()
                    is_json_content = (
                        (
                            content_stripped.startswith("{")
                            and content_stripped.endswith("}")
                        )
                        or (
                            content_stripped.startswith("```")
                            and "{" in content_stripped
                            and "}" in content_stripped
                        )
                        or (
                            content_stripped.lower().startswith("json")
                            and "{" in content_stripped
                            and "}" in content_stripped
                        )
                    )
                    
                    if is_json_content:
                        # This is JSON content, clean it and create a summary instead of showing raw JSON
                        try:
                            import json

                            cleaned_analysis_content = self._clean_json_content(
                                analysis_content
                            )
                            json_data = json.loads(cleaned_analysis_content)
                            
                            # Case Overview
                            if "case_overview" in json_data:
                                case_overview = json_data["case_overview"]
                                if "summary" in case_overview:
                                    combined_content.append(
                                        f"**Case Summary:** {case_overview['summary']}"
                                    )
                                    combined_content.append("")
                                if "significance" in case_overview:
                                    combined_content.append(
                                        f"**Significance:** {case_overview['significance']}"
                                    )
                                    combined_content.append("")
                            
                            # Fact Pattern
                            if "fact_pattern" in json_data:
                                fact_pattern = json_data["fact_pattern"]
                                if (
                                    "misconduct_details" in fact_pattern
                                    and fact_pattern["misconduct_details"]
                                ):
                                    combined_content.append(
                                        f"**Key Facts:** {fact_pattern['misconduct_details']}"
                                    )
                                    combined_content.append("")
                                if (
                                    "parties" in fact_pattern
                                    and fact_pattern["parties"]
                                ):
                                    combined_content.append(
                                        "**Key Parties:** "
                                        + ", ".join(fact_pattern["parties"])
                                    )
                                    combined_content.append("")
                                if (
                                    "legal_framework" in fact_pattern
                                    and fact_pattern["legal_framework"]
                                ):
                                    combined_content.append(
                                        f"**Legal Framework:** {fact_pattern['legal_framework']}"
                                    )
                                    combined_content.append("")
                            
                            # Legal Analysis (comprehensive)
                            if (
                                "legal_analysis" in json_data
                                and json_data["legal_analysis"]
                            ):
                                legal_analysis = json_data["legal_analysis"]
                                if isinstance(legal_analysis, dict):
                                    if (
                                        "enforcement_trends" in legal_analysis
                                        and legal_analysis["enforcement_trends"]
                                    ):
                                        combined_content.append(
                                            f"**Enforcement Trends:** {legal_analysis['enforcement_trends']}"
                                        )
                                        combined_content.append("")
                                    if (
                                        "investigative_techniques" in legal_analysis
                                        and legal_analysis["investigative_techniques"]
                                    ):
                                        combined_content.append(
                                            f"**Investigative Techniques:** {legal_analysis['investigative_techniques']}"
                                        )
                                        combined_content.append("")
                                    if (
                                        "whistleblower_analysis" in legal_analysis
                                        and legal_analysis["whistleblower_analysis"]
                                    ):
                                        combined_content.append(
                                            f"**Whistleblower Considerations:** {legal_analysis['whistleblower_analysis']}"
                                        )
                                        combined_content.append("")
                                    if "key_issues" in legal_analysis:
                                        combined_content.append(
                                            f"**Legal Issues:** {legal_analysis['key_issues']}"
                                        )
                                        combined_content.append("")
                                elif (
                                    isinstance(legal_analysis, str)
                                    and len(legal_analysis) > 50
                                ):
                                    # Show first 200 chars of legal analysis
                                    combined_content.append(
                                        f"**Legal Analysis:** {legal_analysis[:200]}..."
                                    )
                                    combined_content.append("")
                            
                            # Blog Outline
                            if "blog_outline" in json_data:
                                blog_outline = json_data["blog_outline"]
                                if (
                                    "compelling_hooks" in blog_outline
                                    and blog_outline["compelling_hooks"]
                                ):
                                    combined_content.append("**Blog Post Hooks:**")
                                    for hook in blog_outline[
                                        "compelling_hooks"
                                    ]:  # Show all hooks
                                        combined_content.append(f"- {hook}")
                                    combined_content.append("")
                                
                                if (
                                    "structure" in blog_outline
                                    and blog_outline["structure"]
                                ):
                                    combined_content.append("**Blog Structure:**")
                                    for section in blog_outline["structure"]:
                                        combined_content.append(f"- {section}")
                                    combined_content.append("")
                                
                                if (
                                    "practical_takeaways" in blog_outline
                                    and blog_outline["practical_takeaways"]
                                ):
                                    combined_content.append("**Practical Takeaways:**")
                                    for takeaway in blog_outline["practical_takeaways"]:
                                        combined_content.append(f"- {takeaway}")
                                    combined_content.append("")
                                
                                if (
                                    "key_takeaways" in blog_outline
                                    and blog_outline["key_takeaways"]
                                ):
                                    combined_content.append("**Key Takeaways:**")
                                    for takeaway in blog_outline["key_takeaways"]:
                                        combined_content.append(f"- {takeaway}")
                                    combined_content.append("")
                            
                            # Supporting Quotes (show multiple if available)
                            if (
                                "supporting_quotes" in json_data
                                and json_data["supporting_quotes"]
                            ):
                                quotes = json_data["supporting_quotes"]
                                if isinstance(quotes, list) and len(quotes) > 0:
                                    if len(quotes) == 1:
                                        combined_content.append("**Key Quote:**")
                                    else:
                                        combined_content.append("**Key Quotes:**")
                                    
                                    for quote in quotes[:3]:  # Show up to 3 quotes
                                        # Handle both string quotes and structured quote objects
                                        if isinstance(quote, dict):
                                            quote_text = quote.get("quote", "")
                                            speaker = quote.get("speaker", "")
                                            title = quote.get("title", "")
                                            if quote_text:
                                                if speaker:
                                                    attribution = f" - {speaker}"
                                                    if title:
                                                        attribution += f", {title}"
                                                    combined_content.append(
                                                        f'"{quote_text}"{attribution}'
                                                    )
                                                else:
                                                    combined_content.append(
                                                        f'"{quote_text}"'
                                                    )
                                        elif isinstance(quote, str):
                                            combined_content.append(f'"{quote}"')
                                    combined_content.append("")
                            
                            # Research Citations
                            if (
                                "research_citations" in json_data
                                and json_data["research_citations"]
                            ):
                                citations = json_data["research_citations"]
                                if isinstance(citations, dict):
                                    if (
                                        "additional_research_links" in citations
                                        and citations["additional_research_links"]
                                    ):
                                        combined_content.append(
                                            "**Additional Research:**"
                                        )
                                        for link in citations[
                                            "additional_research_links"
                                        ][
                                            :3
                                        ]:  # Show up to 3 links
                                            combined_content.append(f"- {link}")
                                        combined_content.append("")
                        except (json.JSONDecodeError, KeyError):
                            # Fallback: clean the JSON markers and show first 200 chars
                            cleaned_content = self._clean_json_content(analysis_content)
                            combined_content.append(f"{cleaned_content[:200]}...")
                    else:
                        # This is markdown content, show it directly
                        combined_content.append(analysis_content)
                    combined_content.append("")
                    if i < len(sorted_analyses):
                        combined_content.append("---")
                        combined_content.append("")
            
            # Section 2: Comprehensive Article Summary
            combined_content.append("---")
            combined_content.append("")
            combined_content.append("## All Articles Reviewed")
            combined_content.append("")

            # Group articles by score ranges
            high_priority_items = [a for a in all_scored_articles if a["score"] >= 80]
            medium_priority_items = [
                a for a in all_scored_articles if a["score"] >= 50 and a["score"] < 80
            ]
            low_priority_items = [a for a in all_scored_articles if a["score"] < 50]

            # Medium Priority Section (High priority already covered above)
            if medium_priority_items:
                combined_content.append("### Medium Priority Articles (Score 50-79)")
                combined_content.append("*Relevant to practice but lower priority*")
                combined_content.append("")
                for i, item in enumerate(
                    sorted(
                        medium_priority_items, key=lambda x: x["score"], reverse=True
                    ),
                    1,
                ):
                    combined_content.append(
                        f"**{i}. {item['analysis_article'].title}** (Score: {item['score']})"
                    )
                    combined_content.append(
                        f"- **Amount:** {item['dollar_amount']} | **Published:** {item['analysis_article'].published_date.strftime('%Y-%m-%d')}"
                    )
                    combined_content.append(
                        f"- **Practice Areas:** {', '.join(item['practice_areas'])}"
                    )
                    combined_content.append(f"- **Summary:** {item['summary']}")
                    combined_content.append(
                        f"- **Link:** [{item['analysis_article'].url}]({item['analysis_article'].url})"
                    )
                    combined_content.append("")

            # Low Priority Section  
            if low_priority_items:
                combined_content.append("### Lower Priority Articles (Score <50)")
                combined_content.append(
                    "*Reviewed but less relevant to fraud/qui-tam practice*"
                )
                combined_content.append("")
                for i, item in enumerate(
                    sorted(low_priority_items, key=lambda x: x["score"], reverse=True),
                    1,
                ):
                    combined_content.append(
                        f"**{i}. {item['analysis_article'].title}** (Score: {item['score']})"
                    )
                    combined_content.append(
                        f"- **Published:** {item['analysis_article'].published_date.strftime('%Y-%m-%d')} | **Link:** [{item['analysis_article'].url}]({item['analysis_article'].url})"
                    )
                    combined_content.append("")

            # Summary statistics
            if (
                not detailed_analyses
                and not medium_priority_items
                and not low_priority_items
            ):
                combined_content.append(
                    "*No additional articles to report for this period.*"
                )
                combined_content.append("")
            
            return "\n".join(combined_content)
            
        except Exception as e:
            print(f"Error creating intelligence report: {e}")
            return "Error generating intelligence report"
    
    def _extract_insights_for_verification(
        self, detailed_analyses: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract AI-generated content for citation verification from both article and insight analysis."""
        content_to_verify = []
        
        for analysis in detailed_analyses:
            # Get the raw JSON content if available (contains both article and insight analysis)
            if "analysis_json" in analysis:
                try:
                    cleaned_analysis_json = self._clean_json_content(
                        analysis["analysis_json"]
                    )
                    json_content = json.loads(cleaned_analysis_json)
                    
                    # Extract content from both analysis stages that contains external citations
                    if "article_analysis" in json_content:
                        # Article analysis may contain research_citations that need verification
                        content_to_verify.append(
                            json.dumps(json_content["article_analysis"])
                        )
                    
                    if "insight_analysis" in json_content:
                        # Insight analysis definitely contains external citations that need verification
                        content_to_verify.append(
                            json.dumps(json_content["insight_analysis"])
                        )
                        
                except (json.JSONDecodeError, KeyError) as e:
                    print(
                        f"Warning: Could not parse analysis JSON for verification: {e}"
                    )
                    # Fallback to text analysis
                    analysis_text = analysis.get("analysis", "")
                    if analysis_text:
                        content_to_verify.append(analysis_text)
            else:
                # Fallback: use the formatted text analysis
                analysis_text = analysis.get("analysis", "")
                if analysis_text:
                    content_to_verify.append(analysis_text)
                    
        return content_to_verify
    
    def _update_analysis_with_verified_insights(
        self,
        combined_analysis: str,
        original_insights: List[str],
        verified_insights: List[str],
    ) -> str:
        """Update the combined analysis with verified insights content."""
        if len(original_insights) != len(verified_insights):
            print("Warning: Mismatch between original and verified insights count")
            return combined_analysis
        
        updated_analysis = combined_analysis
        
        # Replace each original insight section with its verified version
        for original, verified in zip(original_insights, verified_insights):
            if original != verified:
                # Only replace if verification made changes
                updated_analysis = updated_analysis.replace(original, verified)
                
        return updated_analysis
