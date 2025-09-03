"""Base worker thread for background tasks."""

from PyQt5.QtCore import QThread, pyqtSignal


class BaseWorker(QThread):
    """Base class for worker threads."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs

    def run(self):
        """Override this method in subclasses."""
        try:
            result = self.execute_task()
            self.finished.emit(result)
        except Exception as e:
            self._log_error(e)
            self.error.emit(str(e))

    def execute_task(self):
        """Override this method to implement the specific task."""
        raise NotImplementedError("Subclasses must implement execute_task()")

    def _log_error(self, e):
        """Log the error details."""
        import logging

        logging.error(f"Error in {self.__class__.__name__}: {str(e)}")
