"""Tests for the ReportGenerator class."""

import unittest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
from blogsai.reporting.generator import ReportGenerator


class TestReportGenerator(unittest.TestCase):
    """Test cases for the ReportGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('blogsai.reporting.generator.config') as mock_config, \
             patch('blogsai.reporting.generator.app_dirs') as mock_app_dirs:
            mock_config.reporting.formats = ['html', 'json', 'markdown']
            mock_app_dirs.reports_dir = '/tmp/reports'
            self.generator = ReportGenerator()
    
    @patch('blogsai.reporting.generator.db_session')
    def test_generate_report_files_success(self, mock_db_session):
        """Test successful report file generation."""
        # Mock database session
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock report
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.title = "Test Report"
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_report
        
        # Mock articles
        mock_articles = [MagicMock()]
        
        with patch.object(self.generator, '_get_report_articles', return_value=mock_articles), \
             patch.object(self.generator, '_generate_format', return_value='/tmp/reports/test.html') as mock_generate:
            
            result = self.generator.generate_report_files(report_id=1)
            
            self.assertIsInstance(result, dict)
            self.assertEqual(len(result), 3)  # html, json, markdown
            mock_generate.assert_called()
    
    @patch('blogsai.reporting.generator.db_session')
    def test_generate_report_files_report_not_found(self, mock_db_session):
        """Test report file generation when report is not found."""
        # Mock database session
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock report not found
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        
        with self.assertRaises(ValueError) as context:
            self.generator.generate_report_files(report_id=999)
        
        self.assertIn("Report 999 not found", str(context.exception))
    
    def test_get_report_by_id_success(self):
        """Test successful report retrieval by ID."""
        mock_db = MagicMock()
        mock_report = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_report
        
        result = self.generator._get_report_by_id(mock_db, report_id=1)
        
        self.assertEqual(result, mock_report)
        mock_db.query.assert_called_once()
    
    def test_get_report_by_id_exception(self):
        """Test report retrieval with database exception."""
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database error")
        
        with patch.object(self.generator, '_log_error') as mock_log:
            result = self.generator._get_report_by_id(mock_db, report_id=1)
            
            self.assertIsNone(result)
            mock_log.assert_called_once()
    
    def test_generate_all_formats_success(self):
        """Test generation of all configured formats."""
        mock_report = MagicMock()
        mock_report.id = 1
        mock_articles = [MagicMock()]
        
        with patch.object(self.generator, '_generate_format', return_value='/tmp/reports/test.html'):
            result = self.generator._generate_all_formats(mock_report, mock_articles)
            
            self.assertIsInstance(result, dict)
            self.assertEqual(len(result), 3)  # html, json, markdown
    
    def test_generate_all_formats_with_exception(self):
        """Test format generation with exception in one format."""
        mock_report = MagicMock()
        mock_report.id = 1
        mock_articles = [MagicMock()]
        
        def mock_generate_format(report, articles, fmt):
            if fmt == 'html':
                raise Exception("HTML generation failed")
            return f'/tmp/reports/test.{fmt}'
        
        with patch.object(self.generator, '_generate_format', side_effect=mock_generate_format), \
             patch.object(self.generator, '_log_error') as mock_log:
            
            result = self.generator._generate_all_formats(mock_report, mock_articles)
            
            # Should continue with other formats even if one fails
            self.assertEqual(len(result), 2)  # json, markdown (html failed)
            mock_log.assert_called()
    
    def test_update_report_file_paths(self):
        """Test updating report with generated file paths."""
        mock_report = MagicMock()
        generated_files = {
            'html': '/tmp/reports/test.html',
            'json': '/tmp/reports/test.json',
            'markdown': '/tmp/reports/test.md'
        }
        
        self.generator._update_report_file_paths(mock_report, generated_files)
        
        self.assertEqual(mock_report.html_file, '/tmp/reports/test.html')
        self.assertEqual(mock_report.json_file, '/tmp/reports/test.json')
        self.assertEqual(mock_report.markdown_file, '/tmp/reports/test.md')
    
    def test_update_report_file_paths_exception(self):
        """Test updating report file paths with exception."""
        mock_report = MagicMock()
        # Simulate exception when setting attribute
        mock_report.__setattr__ = Mock(side_effect=Exception("Attribute error"))
        
        generated_files = {'html': '/tmp/reports/test.html'}
        
        with patch.object(self.generator, '_log_error') as mock_log:
            self.generator._update_report_file_paths(mock_report, generated_files)
            
            mock_log.assert_called_once()
    
    @patch('blogsai.reporting.generator.logging')
    def test_log_error(self, mock_logging):
        """Test error logging functionality."""
        error_message = "Test error"
        self.generator._log_error(error_message)
        
        mock_logging.error.assert_called_once_with(f"ReportGenerator: {error_message}")
    
    @patch('os.makedirs')
    def test_init_creates_output_directory(self, mock_makedirs):
        """Test that output directory is created during initialization."""
        with patch('blogsai.reporting.generator.config') as mock_config, \
             patch('blogsai.reporting.generator.app_dirs') as mock_app_dirs:
            mock_config.reporting.formats = ['html']
            mock_app_dirs.reports_dir = '/tmp/test_reports'
            
            ReportGenerator()
            
            mock_makedirs.assert_called_once_with('/tmp/test_reports', exist_ok=True)


class TestReportGeneratorIntegration(unittest.TestCase):
    """Integration tests for ReportGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('blogsai.reporting.generator.config') as mock_config, \
             patch('blogsai.reporting.generator.app_dirs') as mock_app_dirs:
            mock_config.reporting.formats = ['html', 'json']
            mock_app_dirs.reports_dir = '/tmp/reports'
            self.generator = ReportGenerator()
    
    @patch('blogsai.reporting.generator.db_session')
    def test_full_report_generation_flow(self, mock_db_session):
        """Test complete report generation flow."""
        # Mock database session
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock report and articles
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.title = "Integration Test Report"
        mock_report.analysis = "Test analysis content"
        
        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.content = "Test content"
        
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_report
        
        with patch.object(self.generator, '_get_report_articles', return_value=[mock_article]), \
             patch.object(self.generator, '_generate_format') as mock_generate_format:
            
            # Mock file generation
            mock_generate_format.side_effect = lambda r, a, fmt: f'/tmp/reports/test.{fmt}'
            
            result = self.generator.generate_report_files(report_id=1)
            
            self.assertIn('html', result)
            self.assertIn('json', result)
            self.assertEqual(result['html'], '/tmp/reports/test.html')
            self.assertEqual(result['json'], '/tmp/reports/test.json')


if __name__ == '__main__':
    unittest.main()
