# BlogsAI

AI-powered analysis of government agency press releases with enhanced external research capabilities. Generate daily and weekly intelligence reports by scraping DOJ, SEC, CFTC and conducting AI-driven research on related enforcement trends.

## Features

- **Government source scraping**: DOJ, SEC, CFTC press releases with deduplication
- **AI analysis**: GPT-4 powered analysis with customizable prompts
- **Flexible reporting**: Daily and weekly reports in HTML, JSON, and Markdown formats
- **Local operation**: SQLite database, file outputs
- **Configurable**: YAML-based configuration for sources and prompts

## Quick Start

1. **Install dependencies**:
   ```bash
   poetry install
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Initialize the application**:
   ```bash
   poetry run blogsai init
   ```

4. **Run the complete pipeline**:
   ```bash
   poetry run blogsai run
   ```

## Commands

- `blogsai init` - Initialize database and verify configuration
- `blogsai scrape [--days N]` - Scrape articles from sources
- `blogsai analyze [--type daily|weekly] [--date YYYY-MM-DD]` - Generate analysis report
- `blogsai run [--days N] [--type daily|weekly]` - Run complete pipeline

## Configuration

- `config/sources.yaml` - Configure data sources
- `config/settings.yaml` - Application settings
- `prompts/` - AI analysis prompt templates

## Output

Reports are generated in `data/reports/` in multiple formats:
- HTML: Full formatted report with styling
- JSON: Structured data for programmatic use
- Markdown: Text-based report for documentation

## Development Status

This is an MVP focused on core functionality. The scraping implementation is currently partial (DOJ scraper implemented, others are placeholders) and can be extended as needed.


