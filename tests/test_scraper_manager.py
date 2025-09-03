"""Tests for the ScraperManager class."""

import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import date, datetime
from blogsai.scrapers.manager import ScraperManager


class TestScraperManager(unittest.TestCase):
    """Test cases for the ScraperManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('blogsai.scrapers.manager.config') as mock_config:
            mock_config.sources.get.return_value = {
                'doj': {'name': 'Department of Justice', 'url': 'https://doj.gov'}
            }
            mock_config.scraping = MagicMock()
            self.manager = ScraperManager()
    
    @patch('blogsai.scrapers.manager.db_session')
    def test_scrape_all_sources_success(self, mock_db_session):
        """Test successful scraping of all sources."""
        # Mock database session
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock scraper
        mock_scraper = MagicMock()
        mock_scraper.source_config.name = "Department of Justice"
        self.manager.scrapers = {'doj': mock_scraper}
        
        # Mock source lookup
        mock_source = MagicMock()
        mock_source.id = 1
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_source
        
        # Mock scraping log
        mock_log = MagicMock()
        
        with patch.object(self.manager, '_create_scraping_log', return_value=mock_log), \
             patch.object(self.manager, '_get_articles_from_scraper', return_value=[]), \
             patch.object(self.manager, '_save_articles', return_value={'new_articles': 0, 'duplicate_articles': 0, 'total_articles': 0, 'article_results': []}):
            
            result = self.manager.scrape_all_sources(days_back=1)
            
            self.assertIn("Department of Justice", result)
            self.assertEqual(result["Department of Justice"]['new_articles'], 0)
    
    @patch('blogsai.scrapers.manager.db_session')
    def test_scrape_all_sources_source_not_found(self, mock_db_session):
        """Test scraping when source is not found in database."""
        # Mock database session
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock scraper
        mock_scraper = MagicMock()
        mock_scraper.source_config.name = "Department of Justice"
        self.manager.scrapers = {'doj': mock_scraper}
        
        # Mock source not found
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        
        result = self.manager.scrape_all_sources(days_back=1)
        
        self.assertIn("Department of Justice", result)
        self.assertEqual(result["Department of Justice"]['new_articles'], 0)
    
    def test_get_articles_from_scraper_with_date_range(self):
        """Test getting articles from scraper with date range support."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_date_range.return_value = [{'title': 'Test Article'}]
        
        articles = self.manager._get_articles_from_scraper(mock_scraper, days_back=1)
        
        mock_scraper.scrape_date_range.assert_called_once()
        self.assertEqual(len(articles), 1)
    
    def test_get_articles_from_scraper_without_date_range(self):
        """Test getting articles from scraper without date range support."""
        mock_scraper = MagicMock()
        # Remove scrape_date_range method
        del mock_scraper.scrape_date_range
        mock_scraper.scrape_recent.return_value = [{'title': 'Test Article'}]
        
        articles = self.manager._get_articles_from_scraper(mock_scraper, days_back=1)
        
        mock_scraper.scrape_recent.assert_called_once_with(1)
        self.assertEqual(len(articles), 1)
    
    def test_create_empty_result(self):
        """Test creation of empty result dictionary."""
        result = self.manager._create_empty_result()
        
        expected_keys = ['new_articles', 'duplicate_articles', 'total_articles', 'article_results']
        for key in expected_keys:
            self.assertIn(key, result)
            self.assertEqual(result[key], 0 if key != 'article_results' else [])
    
    @patch('blogsai.scrapers.manager.logging')
    def test_log_error(self, mock_logging):
        """Test error logging functionality."""
        error_message = "Test error"
        self.manager._log_error(error_message)
        
        mock_logging.error.assert_called_once_with(f"ScraperManager: {error_message}")
    
    def test_emit_progress(self):
        """Test progress emission."""
        with patch('builtins.print') as mock_print:
            test_message = "Test progress message"
            self.manager._emit_progress(test_message)
            
            mock_print.assert_called_once_with(test_message)
    
    def test_emit_progress_with_callback(self):
        """Test progress emission with callback."""
        callback_messages = []
        
        def progress_callback(msg):
            callback_messages.append(msg)
        
        test_message = "Test progress message"
        self.manager._emit_progress_with_callback(test_message, progress_callback)
        
        self.assertEqual(len(callback_messages), 1)
        self.assertEqual(callback_messages[0], test_message)
    
    def test_emit_progress_without_callback(self):
        """Test progress emission without callback."""
        with patch.object(self.manager, '_emit_progress') as mock_emit:
            test_message = "Test progress message"
            self.manager._emit_progress_with_callback(test_message, None)
            
            mock_emit.assert_called_once_with(test_message)
    
    @patch('blogsai.scrapers.manager.db_session')
    def test_scrape_single_source_exception_handling(self, mock_db_session):
        """Test exception handling in single source scraping."""
        # Mock database session to raise exception
        mock_db_session.side_effect = Exception("Database connection failed")
        
        # Mock scraper
        mock_scraper = MagicMock()
        mock_scraper.source_config.name = "Department of Justice"
        
        result = self.manager._scrape_single_source(None, 'doj', mock_scraper, 1)
        
        # Should return empty result on exception
        self.assertEqual(result['new_articles'], 0)
        self.assertEqual(result['total_articles'], 0)
    
    @patch('blogsai.scrapers.manager.db_session')
    def test_scrape_all_sources_date_range(self, mock_db_session):
        """Test scraping all sources for a date range."""
        # Mock database session
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock scraper
        mock_scraper = MagicMock()
        mock_scraper.source_config.name = "Department of Justice"
        self.manager.scrapers = {'doj': mock_scraper}
        
        # Mock source lookup
        mock_source = MagicMock()
        mock_source.id = 1
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_source
        
        with patch.object(self.manager, '_scrape_single_source_date_range') as mock_scrape:
            mock_scrape.return_value = {'new_articles': 5, 'total_articles': 10}
            
            start_date = date(2023, 1, 1)
            end_date = date(2023, 1, 31)
            result = self.manager.scrape_all_sources_date_range(start_date, end_date)
            
            self.assertIn("Department of Justice", result)
            mock_scrape.assert_called_once()


class TestScraperManagerIntegration(unittest.TestCase):
    """Integration tests for ScraperManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('blogsai.scrapers.manager.config') as mock_config:
            mock_config.sources.get.return_value = {}
            mock_config.scraping = MagicMock()
            self.manager = ScraperManager()
    
    def test_init_scrapers_empty_config(self):
        """Test scraper initialization with empty configuration."""
        self.assertEqual(len(self.manager.scrapers), 0)
    
    @patch('blogsai.scrapers.manager.DOJScraper')
    def test_init_scrapers_with_config(self, mock_doj_scraper):
        """Test scraper initialization with valid configuration."""
        with patch('blogsai.scrapers.manager.config') as mock_config:
            mock_config.sources.get.return_value = {
                'doj': {'name': 'Department of Justice', 'url': 'https://doj.gov'}
            }
            mock_config.scraping = MagicMock()
            
            manager = ScraperManager()
            
            self.assertIn('doj', manager.scrapers)
            mock_doj_scraper.assert_called_once()


if __name__ == '__main__':
    unittest.main()
