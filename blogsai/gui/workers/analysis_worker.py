"""Worker thread for analysis tasks."""

import sys
from pathlib import Path
from .base_worker import BaseWorker

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.analysis.analyzer import AnalysisEngine
from blogsai.analysis.openai_client import APIKeyInvalidError, OpenAIAPIError


class AnalysisWorker(BaseWorker):
    """Worker for generating intelligence reports and analysis-only tasks."""

    def execute_task(self):
        """Execute the report generation or analysis-only task."""
        # Initialize the analysis engine
        self.progress.emit("Initializing analysis engine...")
        engine = self._initialize_analysis_engine()

        # Extract task parameters from kwargs
        (
            start_date,
            end_date,
            selected_article_ids,
            enable_insights,
            high_priority_only,
            force_refresh,
            output_format,
            output_path,
            analysis_only,
        ) = self._extract_task_parameters()

        # Check if the task is analysis-only
        if analysis_only:
            return self._execute_analysis_only(
                engine,
                start_date,
                end_date,
                selected_article_ids,
                force_refresh,
                enable_insights,
            )
        else:
            self.progress.emit("Analyzing articles and generating report...")

        try:
            # Generate the report
            result = self._generate_report(
                engine,
                start_date,
                end_date,
                selected_article_ids,
                force_refresh,
                enable_insights,
                high_priority_only,
            )
        except APIKeyInvalidError as e:
            # Handle API key errors
            return self._handle_api_key_error(e)
        except OpenAIAPIError as e:
            # Handle OpenAI API errors
            return self._handle_openai_api_error(e)

        # Check if the report generation was successful
        if result.get("success", True):
            self.progress.emit("Generating final report file...")
            # Generate the report file in the requested format
            self._generate_report_file(
                result, start_date, end_date, output_format, output_path, high_priority_only
            )

        self.progress.emit("Report generation completed!")
        return result

    def _initialize_analysis_engine(self):
        """Initialize the analysis engine."""
        return AnalysisEngine(progress_callback=self.progress.emit)

    def _extract_task_parameters(self):
        """Extract task parameters from kwargs."""
        start_date = self.kwargs["start_date"]
        end_date = self.kwargs["end_date"]
        selected_article_ids = self.kwargs.get("selected_article_ids", None)
        enable_insights = self.kwargs.get("enable_insights", False)
        high_priority_only = self.kwargs.get("high_priority_only", True)
        force_refresh = self.kwargs.get("force_refresh", False)
        output_format = self.kwargs.get("output_format", "HTML")
        output_path = self.kwargs.get("output_path", "")
        analysis_only = self.kwargs.get("analysis_only", False)
        return (
            start_date,
            end_date,
            selected_article_ids,
            enable_insights,
            high_priority_only,
            force_refresh,
            output_format,
            output_path,
            analysis_only,
        )

    def _generate_report(
        self,
        engine,
        start_date,
        end_date,
        selected_article_ids,
        force_refresh,
        enable_insights,
        high_priority_only,
    ):
        """Generate the intelligence report."""
        if selected_article_ids:
            self.progress.emit(
                f"Analyzing {len(selected_article_ids)} selected articles..."
            )
            return engine.generate_intelligence_report_from_articles(
                selected_article_ids,
                force_refresh_scores=force_refresh,
                force_refresh_analysis=force_refresh,
                enable_insights=enable_insights,
                high_priority_only=high_priority_only,
            )
        else:
            return engine.generate_intelligence_report(
                start_date,
                end_date,
                force_refresh_scores=force_refresh,
                force_refresh_analysis=force_refresh,
                enable_insights=enable_insights,
                high_priority_only=high_priority_only,
            )

    def _handle_api_key_error(self, e):
        """Handle API key errors."""
        self.progress.emit(f"API Key Error: {str(e)}")
        return {"success": False, "error": str(e), "error_type": "api_key_invalid"}

    def _handle_openai_api_error(self, e):
        """Handle OpenAI API errors."""
        self.progress.emit(f"OpenAI API Error: {str(e)}")
        return {"success": False, "error": str(e), "error_type": "openai_api_error"}

    def _generate_report_file(
        self, result, start_date, end_date, output_format, output_path, high_priority_only
    ):
        """Generate the report file in the requested format."""
        from blogsai.reporting.generator import ReportGenerator
        from blogsai.database.models import Report
        from blogsai.core import get_db

        try:
            # Use the report ID from the analysis engine (which has linked articles)
            report_id = result.get("report_id")
            if not report_id:
                # Fallback: create report if analysis engine didn't create one
                report_id = self._create_report_record(result, start_date, end_date, high_priority_only)

            generator = ReportGenerator()
            if output_format.upper() == "PDF":
                # For PDF, we need to use the report generator's PDF method
                self._generate_pdf_report(generator, report_id, output_path)
            else:
                # For HTML, generate HTML from the report using the ReportGenerator
                self._generate_html_report(generator, report_id, output_path)
            result["output_file"] = output_path
        except Exception as e:
            result["success"] = False
            result["error"] = f"Failed to generate {output_format} file: {str(e)}"

    def _create_report_record(self, result, start_date, end_date, high_priority_only=True):
        """Create a report record in the database."""
        from blogsai.database.models import Report
        from blogsai.core import get_db

        db = get_db()
        try:
            report = Report(
                title=f"Intelligence Report {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                report_type="intelligence",
                start_date=start_date,
                end_date=end_date,
                analysis=result.get("analysis", ""),
                summary=result.get("summary", ""),
                article_count=result.get("article_count", 0),
                tokens_used=result.get("tokens_used", 0),
                high_priority_only=high_priority_only,
            )
            db.add(report)
            db.commit()
            return report.id
        finally:
            db.close()

    def _generate_pdf_report(self, generator, report_id, output_path):
        """Generate a PDF report."""
        from blogsai.database.models import Report
        from blogsai.core import get_db

        db = get_db()
        try:
            report = db.query(Report).filter_by(id=report_id).first()
            articles = generator._get_report_articles(db, report_id)
            generator._generate_pdf(report, articles, Path(output_path))
        finally:
            db.close()

    def _generate_html_report(self, generator, report_id, output_path):
        """Generate an HTML report."""
        from blogsai.database.models import Report
        from blogsai.core import get_db

        db = get_db()
        try:
            report = db.query(Report).filter_by(id=report_id).first()
            articles = generator._get_report_articles(db, report_id)
            generator._generate_html(report, articles, Path(output_path))
        finally:
            db.close()

    def _execute_analysis_only(
        self,
        engine,
        start_date,
        end_date,
        selected_article_ids,
        force_refresh,
        enable_insights,
    ):
        """Execute analysis-only task (relevance scoring and insights analysis)."""
        try:
            from blogsai.core import get_db
            from blogsai.database.models import Article

            # Get articles to analyze
            if selected_article_ids:
                self.progress.emit(
                    f"Running analysis on {len(selected_article_ids)} selected articles..."
                )

                # Get articles from database
                db = get_db()
                try:
                    articles = (
                        db.query(Article)
                        .filter(Article.id.in_(selected_article_ids))
                        .all()
                    )
                finally:
                    db.close()

            else:
                self.progress.emit(f"Finding articles in date range...")

                # Get articles by date range
                db = get_db()
                try:
                    articles = (
                        db.query(Article)
                        .filter(
                            Article.published_date >= start_date,
                            Article.published_date <= end_date,
                        )
                        .all()
                    )
                finally:
                    db.close()

            if not articles:
                return {
                    "success": False,
                    "error": "No articles found for analysis",
                    "article_count": 0,
                }

            self.progress.emit(f"Found {len(articles)} articles for analysis")

            # Run relevance scoring on all articles
            self.progress.emit("Running relevance scoring...")
            scored_count = 0

            for i, article in enumerate(articles, 1):
                try:
                    # Create a simple article object for scoring
                    article_data = {
                        "title": article.title,
                        "content": article.content,
                        "url": article.url,
                        "published_date": article.published_date,
                        "author": article.author,
                        "category": article.category,
                        "tags": article.tags.split(",") if article.tags else [],
                        "source_name": "Unknown",  # We'll get this if needed
                        "db_article_id": article.id,
                        # Add relevance fields that might be accessed
                        "relevance_score": article.relevance_score,
                        "practice_areas": article.practice_areas,
                        "dollar_amount": article.dollar_amount,
                        "whistleblower_indicators": article.whistleblower_indicators,
                        "blog_potential": article.blog_potential,
                        "relevance_summary": article.relevance_summary,
                        "detailed_analysis": article.detailed_analysis,
                        "detailed_analysis_tokens": article.detailed_analysis_tokens,
                        "detailed_analysis_at": article.detailed_analysis_at,
                    }

                    # Convert to namespace object for compatibility
                    class ArticleObj:
                        def __init__(self, data):
                            for key, value in data.items():
                                setattr(self, key, value)

                    article_obj = ArticleObj(article_data)

                    self.progress.emit(
                        f"Scoring article {i}/{len(articles)}: {article.title}..."
                    )

                    # Score the article (this will save to database)
                    score_data = engine._score_article_relevance(
                        article_obj, force_refresh=force_refresh
                    )

                    if score_data and score_data.get("score", 0) > 0:
                        scored_count += 1

                except Exception as e:
                    self.progress.emit(
                        f"Error scoring article {article.title}...: {str(e)}"
                    )
                    continue

            # Run detailed analysis on high-scoring articles if insights are enabled
            analyzed_count = 0
            relevant_articles = []

            if enable_insights:
                self.progress.emit("Running detailed analysis on relevant articles...")

                # Get articles with good scores for detailed analysis
                db = get_db()
                try:
                    relevant_articles = (
                        db.query(Article)
                        .filter(
                            Article.id.in_([a.id for a in articles]),
                            Article.relevance_score >= 50,  # Articles with score >= 50
                        )
                        .all()
                    )
                finally:
                    db.close()

                self.progress.emit(
                    f"Found {len(relevant_articles)} relevant articles for detailed analysis"
                )

                for i, article in enumerate(relevant_articles, 1):
                    try:
                        # Create article object for analysis
                        article_data = {
                            "title": article.title,
                            "content": article.content,
                            "url": article.url,
                            "published_date": article.published_date,
                            "author": article.author,
                            "category": article.category,
                            "tags": article.tags.split(",") if article.tags else [],
                            "source_name": "Unknown",  # We'll get this if needed
                            "db_article_id": article.id,
                            # Add relevance fields that might be accessed
                            "relevance_score": article.relevance_score,
                            "practice_areas": article.practice_areas,
                            "dollar_amount": article.dollar_amount,
                            "whistleblower_indicators": article.whistleblower_indicators,
                            "blog_potential": article.blog_potential,
                            "relevance_summary": article.relevance_summary,
                            "detailed_analysis": article.detailed_analysis,
                            "detailed_analysis_tokens": article.detailed_analysis_tokens,
                            "detailed_analysis_at": article.detailed_analysis_at,
                        }

                        article_obj = ArticleObj(article_data)

                        self.progress.emit(
                            f"Analyzing article {i}/{len(relevant_articles)}: {article.title}..."
                        )

                        # Run detailed analysis (this will save to database)
                        analysis_result = engine._generate_individual_analysis(
                            article_obj,
                            force_refresh=force_refresh,
                            enable_insights=True,
                        )

                        if analysis_result.get("success"):
                            analyzed_count += 1

                    except Exception as e:
                        self.progress.emit(
                            f"Error analyzing article {article.title}...: {str(e)}"
                        )
                        continue
            else:
                self.progress.emit("Skipping detailed analysis (insights disabled)")

            self.progress.emit("Analysis completed!")

            return {
                "success": True,
                "analysis_only": True,
                "article_count": len(articles),
                "scored_count": scored_count,
                "analyzed_count": analyzed_count,
                "relevant_count": len(relevant_articles),
            }

        except APIKeyInvalidError as e:
            self.progress.emit(f"API Key Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "api_key_invalid"}

        except OpenAIAPIError as e:
            self.progress.emit(f"OpenAI API Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "openai_api_error"}

        except Exception as e:
            self.progress.emit(f"Analysis Error: {str(e)}")
            return {"success": False, "error": str(e), "error_type": "analysis_error"}
