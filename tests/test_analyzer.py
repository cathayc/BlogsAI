"""Tests for the AnalysisEngine class."""

import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, date
from blogsai.analysis.analyzer import AnalysisEngine
from blogsai.analysis.openai_client import APIKeyInvalidError, OpenAIAPIError


class TestAnalysisEngine(unittest.TestCase):
    """Test cases for the AnalysisEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine(enable_verification=False)
    
    @patch('blogsai.analysis.analyzer.get_db')
    def test_generate_daily_report_success(self, mock_get_db):
        """Test successful daily report generation."""
        # Mock database session
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock articles
        mock_article = MagicMock()
        mock_article.id = 1
        mock_article.title = "Test Article"
        mock_article.content = "Test content"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_article]
        
        # Mock scoring
        with patch.object(self.engine, '_score_article_relevance') as mock_score:
            mock_score.return_value = {
                'success': True,
                'score': 75,
                'practice_areas': ['Healthcare'],
                'dollar_amount': '$1M',
                'whistleblower_indicators': 'Yes',
                'blog_potential': 'High',
                'summary': 'Test summary',
                'tokens_used': 100
            }
            
            # Mock analysis
            with patch.object(self.engine, '_generate_individual_analysis') as mock_analysis:
                mock_analysis.return_value = {
                    'success': True,
                    'analysis': 'Test analysis',
                    'tokens_used': 200
                }
                
                # Mock report creation
                with patch.object(self.engine, '_create_article_report') as mock_create:
                    mock_create.return_value = "Combined analysis"
                    
                    result = self.engine.generate_daily_report()
                    
                    self.assertTrue(result['success'])
                    self.assertIn('report_id', result)
                    self.assertEqual(result['article_count'], 1)
    
    @patch('blogsai.analysis.analyzer.get_db')
    def test_generate_daily_report_no_articles(self, mock_get_db):
        """Test daily report generation with no articles."""
        # Mock empty database result
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.engine.generate_daily_report()
        
        self.assertFalse(result['success'])
        self.assertIn('No articles found', result['error'])
    
    @patch('blogsai.analysis.analyzer.get_db')
    def test_score_article_relevance_api_key_error(self, mock_get_db):
        """Test article scoring with API key error."""
        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.content = "Test content"
        mock_article.relevance_score = None  # No cached score
        
        with patch.object(self.engine.openai_analyzer, 'analyze_articles') as mock_analyze:
            mock_analyze.side_effect = APIKeyInvalidError("Invalid API key")
            
            result = self.engine._score_article_relevance(mock_article)
            
            self.assertFalse(result['success'])
            self.assertEqual(result['error_type'], 'api_key_invalid')
    
    @patch('blogsai.analysis.analyzer.get_db')
    def test_score_article_relevance_cached(self, mock_get_db):
        """Test article scoring with cached result."""
        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.relevance_score = 80
        mock_article.practice_areas = '["Healthcare", "Finance"]'
        mock_article.dollar_amount = "$5M"
        mock_article.whistleblower_indicators = "Yes"
        mock_article.blog_potential = "High"
        mock_article.relevance_summary = "Cached summary"
        
        result = self.engine._score_article_relevance(mock_article)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['score'], 80)
        self.assertEqual(result['tokens_used'], 0)  # No tokens used for cached result
    
    def test_create_error_response(self):
        """Test error response creation."""
        error_msg = "Test error message"
        result = self.engine._create_error_response(error_msg)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], error_msg)
    
    def test_filter_articles_by_relevance(self):
        """Test article filtering by relevance score."""
        scored_articles = [
            {'score': 90, 'title': 'High priority'},
            {'score': 60, 'title': 'Medium priority'},
            {'score': 30, 'title': 'Low priority'},
            {'score': 85, 'title': 'High priority 2'}
        ]
        
        relevant, high_priority = self.engine._filter_articles_by_relevance(scored_articles)
        
        self.assertEqual(len(relevant), 3)  # Score >= 50
        self.assertEqual(len(high_priority), 2)  # Score >= 80
    
    @patch('blogsai.analysis.analyzer.logging')
    def test_log_error(self, mock_logging):
        """Test error logging functionality."""
        error_message = "Test error"
        self.engine._log_error(error_message)
        
        mock_logging.error.assert_called_once_with(f"AnalysisEngine: {error_message}")
    
    def test_emit_progress_with_callback(self):
        """Test progress emission with callback."""
        callback_messages = []
        
        def progress_callback(msg):
            callback_messages.append(msg)
        
        engine_with_callback = AnalysisEngine(progress_callback=progress_callback)
        test_message = "Test progress message"
        engine_with_callback._emit_progress(test_message)
        
        self.assertEqual(len(callback_messages), 1)
        self.assertEqual(callback_messages[0], test_message)
    
    def test_emit_progress_without_callback(self):
        """Test progress emission without callback (should print)."""
        with patch('builtins.print') as mock_print:
            test_message = "Test progress message"
            self.engine._emit_progress(test_message)
            
            mock_print.assert_called_once_with(test_message)


class TestAnalysisEngineIntegration(unittest.TestCase):
    """Integration tests for AnalysisEngine with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = AnalysisEngine(enable_verification=False)
    
    @patch('blogsai.analysis.analyzer.db_session')
    def test_generate_tiered_report_full_flow(self, mock_db_session):
        """Test complete tiered report generation flow."""
        # Mock database context manager
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock articles
        mock_article = MagicMock()
        mock_article.id = 1
        mock_article.title = "Integration Test Article"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_article]
        
        # Mock all the helper methods
        with patch.object(self.engine, '_score_articles_batch') as mock_score_batch, \
             patch.object(self.engine, '_filter_articles_by_relevance') as mock_filter, \
             patch.object(self.engine, '_generate_detailed_analyses') as mock_detailed, \
             patch.object(self.engine, '_create_article_report') as mock_create, \
             patch.object(self.engine, '_create_and_save_report') as mock_save:
            
            # Set up mock returns
            mock_score_batch.return_value = ([{'score': 80}], 100)
            mock_filter.return_value = ([{'score': 80}], [{'score': 80}])
            mock_detailed.return_value = [{'analysis': 'test', 'tokens_used': 50}]
            mock_create.return_value = "Combined analysis"
            mock_save.return_value = {
                'success': True,
                'report_id': 1,
                'title': 'Test Report',
                'article_count': 1
            }
            
            result = self.engine._generate_tiered_report('daily', datetime.now(), datetime.now())
            
            self.assertTrue(result['success'])
            self.assertEqual(result['report_id'], 1)


if __name__ == '__main__':
    unittest.main()
