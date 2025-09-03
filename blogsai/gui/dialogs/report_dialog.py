"""Report view dialog for displaying report details."""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel
from PyQt5.QtGui import QFont


class ReportViewDialog(QDialog):
    """Dialog for showing detailed information about a report."""

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.report = report
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle(f"Report: {self.report.title}")
        self.setGeometry(200, 200, 900, 700)

        layout = QVBoxLayout(self)

        # Report metadata
        from ...utils.timezone_utils import format_local_datetime, format_local_date
        
        metadata_text = f"""
<h2>{self.report.title}</h2>
<p><b>Created:</b> {format_local_datetime(self.report.created_at)}</p>
<p><b>Type:</b> {self.report.report_type}</p>
<p><b>Date Range:</b> {format_local_date(self.report.start_date)} to {format_local_date(self.report.end_date)}</p>
<p><b>Articles Analyzed:</b> {self.report.article_count}</p>
<p><b>AI Tokens Used:</b> {self.report.tokens_used or 'Unknown'}</p>
"""

        metadata_label = QLabel(metadata_text)
        metadata_label.setWordWrap(True)
        layout.addWidget(metadata_label)

        # Report content
        content_label = QLabel("<b>Report Analysis:</b>")
        layout.addWidget(content_label)

        content_text = QTextEdit()
        content_text.setPlainText(
            self.report.analysis or "No analysis content available."
        )
        content_text.setReadOnly(True)
        layout.addWidget(content_text)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
