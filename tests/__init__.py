import unittest
from unittest.mock import patch, MagicMock
from blogsai.gui.workers.analysis_worker import AnalysisWorker

class TestAnalysisWorker(unittest.TestCase):
    def setUp(self):
        # Set up any necessary test data or state
        self.worker = AnalysisWorker(start_date='2025-01-01', end_date='2025-01-31')

    @patch('blogsai.gui.workers.analysis_worker.AnalysisEngine')
    def test_execute_task_analysis_only(self, MockAnalysisEngine):
        # Mock the AnalysisEngine and its methods
        mock_engine = MockAnalysisEngine.return_value
        mock_engine.generate_intelligence_report.return_value = {'success': True}

        # Set analysis_only to True
        self.worker.kwargs['analysis_only'] = True

        # Execute the task
        result = self.worker.execute_task()

        # Assert the expected result
        self.assertTrue(result['success'])
        mock_engine.generate_intelligence_report.assert_not_called()

    @patch('blogsai.gui.workers.analysis_worker.AnalysisEngine')
    def test_execute_task_generate_report(self, MockAnalysisEngine):
        # Mock the AnalysisEngine and its methods
        mock_engine = MockAnalysisEngine.return_value
        mock_engine.generate_intelligence_report.return_value = {'success': True}

        # Set analysis_only to False
        self.worker.kwargs['analysis_only'] = False

        # Execute the task
        result = self.worker.execute_task()

        # Assert the expected result
        self.assertTrue(result['success'])
        mock_engine.generate_intelligence_report.assert_called_once()

    @patch('blogsai.gui.workers.analysis_worker.AnalysisEngine')
    def test_handle_api_key_error(self, MockAnalysisEngine):
        # Simulate an APIKeyInvalidError
        mock_engine = MockAnalysisEngine.return_value
        mock_engine.generate_intelligence_report.side_effect = self.worker._handle_api_key_error(Exception('API Key Error'))

        # Execute the task
        result = self.worker.execute_task()

        # Assert the expected result
        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'api_key_invalid')

if __name__ == '__main__':
    unittest.main()
