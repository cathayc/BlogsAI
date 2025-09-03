import click
from datetime import datetime, timedelta
from ..core import init_db, get_db, config
from ..scrapers.manager import ScraperManager
from ..analysis.analyzer import AnalysisEngine
from ..reporting.generator import ReportGenerator
from ..database.models import Report


@click.group()
def cli():
    pass


@cli.command()
@click.option("--days", default=None, help="Days to scrape back")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
def scrape(days, start_date, end_date):

    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            click.echo(f"Scraping {start_date} to {end_date}...")
        except ValueError:
            click.echo("Invalid date format. Use YYYY-MM-DD.")
            exit(1)
    elif start_date or end_date:
        click.echo("Both dates required for range.")
        exit(1)
    else:
        if days is None:
            days = 1
        click.echo(f"Scraping last {days} day(s)...")

    init_db()
    scraper_manager = ScraperManager()

    try:
        if start_date and end_date:
            results = scraper_manager.scrape_all_sources_date_range(start_dt, end_dt)
        else:
            results = scraper_manager.scrape_all_sources(days_back=days)

        total = sum(len(articles) for articles in results.values())
        click.echo(f"\nFound {total} new articles:")
        for source, articles in results.items():
            click.echo(f"  {source}: {len(articles)}")

    except Exception as e:
        click.echo(f"Scraping error: {e}")
        exit(1)


@cli.command()
@click.option("--start-date", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD), defaults to start-date")
@click.option("--verify-citations", is_flag=True, help="Verify citations")
@click.option("--refresh-scores", is_flag=True, help="Refresh relevance scores")
@click.option("--refresh-analysis", is_flag=True, help="Refresh detailed analysis")
@click.option(
    "--enable-insights",
    is_flag=True,
    help="Enable external research and insights analysis (higher cost)",
)
def intelligence(
    start_date,
    end_date,
    verify_citations,
    refresh_scores,
    refresh_analysis,
    enable_insights,
):

    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else start_dt
    except ValueError:
        click.echo("Invalid date format. Use YYYY-MM-DD.")
        exit(1)

    if end_dt < start_dt:
        click.echo("End date cannot be before start date.")
        exit(1)

    click.echo(
        f"Report: {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"
    )
    if verify_citations:
        click.echo("Citations enabled")
    if refresh_scores:
        click.echo("Score refresh enabled")
    if refresh_analysis:
        click.echo("Analysis refresh enabled")
    if enable_insights:
        click.echo("External insights enabled")

    # Initialize database
    init_db()

    # Step 1: Scrape government websites for the date range
    click.echo(f"Scraping...")
    scraper_manager = ScraperManager()

    try:
        scrape_results = scraper_manager.scrape_all_sources_date_range(
            start_dt.date(), end_dt.date()
        )

        # Aggregate results from all sources
        total_articles = sum(
            result["total_articles"] for result in scrape_results.values()
        )
        new_articles = sum(result["new_articles"] for result in scrape_results.values())
        duplicate_articles = sum(
            result["duplicate_articles"] for result in scrape_results.values()
        )

        click.echo(f"Total articles found: {total_articles}")
        click.echo(f"New articles: {new_articles}")
        click.echo(f"Duplicates skipped: {duplicate_articles}")

    except Exception as e:
        click.echo(f"Scraping failed: {e}")
        exit(1)

    # Step 2: Generate intelligence report
    click.echo(f"Analyzing...")
    analysis_engine = AnalysisEngine(enable_verification=verify_citations)

    try:
        result = analysis_engine.generate_intelligence_report(
            start_dt,
            end_dt,
            force_refresh_scores=refresh_scores,
            force_refresh_analysis=refresh_analysis,
            enable_insights=enable_insights,
        )

        if not result["success"]:
            click.echo(f"Report generation failed: {result['error']}")
            exit(1)

        click.echo(f"\nReport generated successfully:")
        click.echo(f"  ID: {result['report_id']}")
        click.echo(f"  Title: {result['title']}")
        click.echo(f"  Articles analyzed: {result['article_count']}")
        click.echo(f"  AI tokens used: {result['tokens_used']}")

        # Generate report files
        report_generator = ReportGenerator()
        files = report_generator.generate_report_files(result["report_id"])

        click.echo(f"\nReport files generated:")
        for format_type, filepath in files.items():
            click.echo(f"  {format_type.upper()}: {filepath}")

    except Exception as e:
        click.echo(f"Error during analysis: {e}")
        exit(1)


@cli.command()
@click.option("--days", default=1, help="Number of days to scrape back")
@click.option(
    "--type",
    "report_type",
    type=click.Choice(["daily"]),
    default="daily",
    help="Type of report to generate",
)
def run(days, report_type):
    """Run complete pipeline: scrape + analyze + generate report."""

    click.echo("Running complete BlogsAI pipeline...")

    # Initialize database
    init_db()

    # Step 1: Scrape
    click.echo(f"\n1. Scraping articles from the last {days} day(s)...")
    scraper_manager = ScraperManager()

    try:
        scrape_results = scraper_manager.scrape_all_sources(days_back=days)
        total_articles = sum(len(articles) for articles in scrape_results.values())
        click.echo(f"   Found {total_articles} new articles")

    except Exception as e:
        click.echo(f"   Scraping failed: {e}")
        exit(1)

    # Step 2: Analyze
    click.echo(f"\n2. Generating {report_type} analysis report...")
    analysis_engine = AnalysisEngine()

    try:
        result = analysis_engine.generate_daily_report()

        if not result["success"]:
            click.echo(f"   Analysis failed: {result['error']}")
            exit(1)

        click.echo(f"   Analyzed {result['article_count']} articles")

    except Exception as e:
        click.echo(f"   Analysis failed: {e}")
        exit(1)

    # Step 3: Generate files
    click.echo(f"\n3. Generating report files...")

    try:
        report_generator = ReportGenerator()
        files = report_generator.generate_report_files(result["report_id"])

        click.echo(f"\nPipeline completed successfully!")
        click.echo(f"Report: {result['title']}")
        click.echo(f"Files generated:")
        for format_type, filepath in files.items():
            click.echo(f"  {format_type.upper()}: {filepath}")

    except Exception as e:
        click.echo(f"   Report generation failed: {e}")
        exit(1)


@cli.command()
def init():
    """Initialize BlogsAI database and verify configuration."""

    click.echo("Initializing BlogsAI...")

    # Check API key configuration
    try:
        from ..config.credential_manager import CredentialManager

        cred_manager = CredentialManager()
        api_key = cred_manager.get_api_key()

        if not api_key or api_key == "MISSING_API_KEY":
            click.echo("Warning: OpenAI API key not configured")
            click.echo(
                "Use the GUI to configure your API key, or set OPENAI_API_KEY environment variable"
            )
        else:
            click.echo("OpenAI API key is configured")
    except Exception as e:
        click.echo(f"Warning: Could not check API key configuration: {e}")

    # Initialize database
    init_db()
    click.echo("Database tables created")

    # Create output directories
    os.makedirs(config.reporting.output_dir, exist_ok=True)
    click.echo(f"Output directory created: {config.reporting.output_dir}")

    # Verify configuration
    click.echo("Configuration loaded successfully")

    click.echo("\nBlogsAI initialized successfully!")
    click.echo("\nNext steps:")
    click.echo("1. Configure OpenAI API key:")
    click.echo("   - Use the GUI application to set up your API key securely, OR")
    click.echo("   - Set OPENAI_API_KEY environment variable")
    click.echo("2. Run 'blogsai run' to execute the full pipeline")
    click.echo("3. Or run individual commands: 'blogsai scrape' then 'blogsai analyze'")


@cli.command()
@click.option("--report-id", type=int, help="Generate PDF for specific report ID")
@click.option("--latest", is_flag=True, help="Generate PDF for the latest report")
@click.option("--list", "list_reports", is_flag=True, help="List available reports")
def pdf(report_id, latest, list_reports):
    """Generate PDF from existing report data without scraping or analysis."""

    if list_reports:
        # List available reports
        db = get_db()
        try:
            reports = (
                db.query(Report).order_by(Report.created_at.desc()).limit(10).all()
            )
            if reports:
                click.echo("Available reports:")
                for report in reports:
                    date_str = report.created_at.strftime("%Y-%m-%d %H:%M")
                    click.echo(
                        f"  ID {report.id}: {report.title} ({date_str}) - {report.article_count} articles"
                    )
            else:
                click.echo("No reports found.")
        finally:
            db.close()
        return

    db = get_db()
    try:
        if latest:
            # Get the most recent report
            report = db.query(Report).order_by(Report.created_at.desc()).first()
            if not report:
                click.echo("No reports found.")
                return
        elif report_id:
            # Get specific report by ID
            report = db.query(Report).filter_by(id=report_id).first()
            if not report:
                click.echo(f"Report with ID {report_id} not found.")
                return
        else:
            click.echo("Please specify --report-id, --latest, or --list")
            return

        click.echo(f"Generating PDF for: {report.title}")

        # Generate PDF using existing data
        generator = ReportGenerator()
        articles = generator._get_report_articles(db, report.id)

        # Generate only PDF directly
        from pathlib import Path

        safe_title = "".join(
            c for c in report.title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        pdf_path = Path(config.reporting.output_dir) / f"{safe_title}.pdf"

        generator._generate_pdf(report, articles, pdf_path)

        click.echo(f"PDF generated: {pdf_path}")

    except Exception as e:
        click.echo(f"Error generating PDF: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
