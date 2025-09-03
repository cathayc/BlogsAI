from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..utils.timezone_utils import get_utc_now

Base = declarative_base()


class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False)
    base_url = Column(String(500), nullable=False)
    scraper_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
    articles = relationship(
        "Article", back_populates="source", cascade="all, delete-orphan"
    )


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    content_hash = Column(String(64), nullable=False, unique=True)
    published_date = Column(DateTime, nullable=False)
    scraped_at = Column(DateTime, default=get_utc_now)
    modified_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
    author = Column(String(200))
    category = Column(String(100))
    tags = Column(Text)

    # Content analysis
    word_count = Column(Integer)
    sentiment_score = Column(Float)  # For future sentiment analysis

    # Relevance scoring (cached to avoid re-running AI analysis)
    relevance_score = Column(Integer)  # 0-100 relevance score
    practice_areas = Column(Text)  # JSON string of practice areas
    dollar_amount = Column(String(200))  # Settlement/fine amount text
    whistleblower_indicators = Column(String(500))
    blog_potential = Column(String(50))
    relevance_summary = Column(Text)
    relevance_scored_at = Column(DateTime)
    detailed_analysis = Column(Text)
    detailed_analysis_json = Column(Text)  # Store raw JSON from AI
    detailed_analysis_tokens = Column(Integer)
    detailed_analysis_at = Column(DateTime)
    source = relationship("Source", back_populates="articles")
    report_articles = relationship("ReportArticle", back_populates="article")


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    report_type = Column(String(50), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    analysis = Column(Text, nullable=False)
    summary = Column(Text)
    created_at = Column(DateTime, default=get_utc_now)
    article_count = Column(Integer, default=0)
    tokens_used = Column(Integer)
    high_priority_only = Column(Boolean, default=True)  # Track analysis scope
    html_file = Column(String(500))
    json_file = Column(String(500))
    markdown_file = Column(String(500))
    report_articles = relationship("ReportArticle", back_populates="report")


class ReportArticle(Base):
    __tablename__ = "report_articles"
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)

    # Relationships
    report = relationship("Report", back_populates="report_articles")
    article = relationship("Article", back_populates="report_articles")


class ScrapingLog(Base):
    """Log of scraping activities."""

    __tablename__ = "scraping_logs"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    started_at = Column(DateTime, default=get_utc_now)
    completed_at = Column(DateTime)
    status = Column(String(50), nullable=False)  # 'running', 'completed', 'failed'
    articles_found = Column(Integer, default=0)
    articles_new = Column(Integer, default=0)
    error_message = Column(Text)

    # Relationship to source
    source = relationship("Source")
