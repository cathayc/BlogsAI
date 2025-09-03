"""Database connection and session management."""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str):
        self.database_url = database_url

        # Ensure data directory exists for SQLite
        if database_url.startswith("sqlite"):
            db_path = database_url.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Configure SQLite for better concurrency handling
        if database_url.startswith("sqlite"):
            self.engine = create_engine(
                database_url,
                echo=False,
                pool_timeout=30,
                pool_recycle=-1,
                pool_pre_ping=True,
                connect_args={
                    "timeout": 60,  # 60 second timeout for locks
                    "check_same_thread": False,
                    "isolation_level": None,  # Enable autocommit mode
                },
            )
        else:
            self.engine = create_engine(database_url, echo=False)

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_session_sync(self) -> Session:
        """Get a synchronous database session."""
        return self.SessionLocal()

    def populate_initial_sources(self, config_manager):
        """Populate the database with initial source records."""
        from .models import Source

        db = self.get_session_sync()
        try:
            # Get all configured sources
            config = config_manager.load_config()

            for category, sources in config.sources.items():
                for source_id, source_config in sources.items():
                    # Check if source already exists (use the full name, not the ID)
                    existing = (
                        db.query(Source).filter_by(name=source_config.name).first()
                    )
                    if not existing:
                        source = Source(
                            name=source_config.name,  # Use the full name, not the ID
                            source_type=category,  # 'agencies' or 'news'
                            base_url=source_config.base_url,
                            scraper_type=source_config.scraper_type,
                            enabled=source_config.enabled,
                        )
                        db.add(source)

            db.commit()

        finally:
            db.close()

    def delete_articles(self, article_ids: list) -> dict:
        """
        Delete articles and all their associated scoring/analysis data.

        Args:
            article_ids: List of article IDs to delete

        Returns:
            dict: Result with success status and details
        """
        from .models import Article, ReportArticle

        if not article_ids:
            return {"success": False, "error": "No article IDs provided"}

        # Initialize variables in case of exception
        articles_deleted = 0
        report_associations_deleted = 0

        try:
            session = self.get_session_sync()
            try:
                # First, delete any report associations (ReportArticle entries)
                # This prevents foreign key constraint issues
                report_articles_deleted = (
                    session.query(ReportArticle)
                    .filter(ReportArticle.article_id.in_(article_ids))
                    .delete(synchronize_session=False)
                )

                # Now delete the articles themselves
                # This will also clear all the scoring/analysis data since it's in the same table
                articles_deleted = (
                    session.query(Article)
                    .filter(Article.id.in_(article_ids))
                    .delete(synchronize_session=False)
                )

                session.commit()

                return {
                    "success": True,
                    "articles_deleted": articles_deleted,
                    "report_associations_deleted": report_articles_deleted,
                    "message": f"Successfully deleted {articles_deleted} articles and {report_associations_deleted} report associations",
                }
            finally:
                session.close()

        except Exception as e:
            return {"success": False, "error": f"Failed to delete articles: {str(e)}"}

    def migrate_database(self):
        """Apply any necessary database migrations."""
        from sqlalchemy import inspect, text

        try:
            # Check if relevance scoring columns exist, add if they don't
            inspector = inspect(self.engine)
            columns = [col["name"] for col in inspector.get_columns("articles")]

            if "relevance_score" not in columns:
                print("Adding relevance scoring columns...")

                # Add the new columns using raw SQL
                with self.engine.connect() as conn:
                    conn.execute(
                        text("ALTER TABLE articles ADD COLUMN relevance_score INTEGER")
                    )
                    conn.execute(
                        text("ALTER TABLE articles ADD COLUMN practice_areas TEXT")
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN dollar_amount VARCHAR(200)"
                        )
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN whistleblower_indicators VARCHAR(500)"
                        )
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN blog_potential VARCHAR(50)"
                        )
                    )
                    conn.execute(
                        text("ALTER TABLE articles ADD COLUMN relevance_summary TEXT")
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN relevance_scored_at DATETIME"
                        )
                    )
                    conn.commit()

            # Check for detailed analysis columns
            if "detailed_analysis" not in columns:
                print("Adding analysis cache columns...")

                with self.engine.connect() as conn:
                    conn.execute(
                        text("ALTER TABLE articles ADD COLUMN detailed_analysis TEXT")
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN detailed_analysis_json TEXT"
                        )
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN detailed_analysis_tokens INTEGER"
                        )
                    )
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN detailed_analysis_at DATETIME"
                        )
                    )
                    conn.commit()

                print("Analysis migration done")
            elif "detailed_analysis_json" not in columns:
                print("Adding JSON analysis column...")

                with self.engine.connect() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE articles ADD COLUMN detailed_analysis_json TEXT"
                        )
                    )
                    conn.commit()

                print("JSON analysis migration done")

            # Check for modified_at column
            if "modified_at" not in columns:
                print("Adding modified_at column...")

                with self.engine.connect() as conn:
                    # SQLite doesn't support CURRENT_TIMESTAMP in ALTER TABLE, so we use a static default
                    conn.execute(
                        text("ALTER TABLE articles ADD COLUMN modified_at DATETIME")
                    )
                    # Update existing rows to have the current timestamp
                    conn.execute(
                        text(
                            "UPDATE articles SET modified_at = datetime('now') WHERE modified_at IS NULL"
                        )
                    )
                    conn.commit()

                print("Modified at migration done")

            # Check for high_priority_only column in reports table
            reports_columns = [col["name"] for col in inspector.get_columns("reports")]
            if "high_priority_only" not in reports_columns:
                print("Adding high_priority_only column to reports...")

                with self.engine.connect() as conn:
                    # Add the new column with default value True (existing reports were high priority only)
                    conn.execute(
                        text("ALTER TABLE reports ADD COLUMN high_priority_only BOOLEAN DEFAULT 1")
                    )
                    conn.commit()

                print("High priority only migration done")

            print("Migration done")

        except Exception as e:
            print(f"Migration error: {e}")


def migrate_database():
    """Standalone function to apply database migrations."""
    try:
        # Get database path from distribution manager
        from ..config.distribution import get_distribution_manager

        dist_manager = get_distribution_manager()
        db_path = str(dist_manager.get_database_path())

        if not db_path:
            print("No database path found")
            return

        # Create database manager and run migrations
        db_url = f"sqlite:///{db_path}"
        manager = DatabaseManager(db_url)
        manager.migrate_database()

    except Exception as e:
        print(f"Migration error: {e}")
