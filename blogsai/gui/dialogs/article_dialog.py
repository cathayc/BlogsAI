"""Article detail dialog for viewing individual articles."""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel
from PyQt5.QtGui import QFont


class ArticleDetailDialog(QDialog):
    """Dialog for showing detailed information about an article."""

    def __init__(self, article, parent=None):
        super().__init__(parent)
        self.article = article
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle(f"Article Details - {self.article.title}")
        self.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(self)

        # Article metadata
        metadata_text = f"""
<h3>{self.article.title}</h3>
<p><b>Source:</b> {self.article.source.name}</p>
<p><b>Published:</b> {self.article.published_date.strftime('%Y-%m-%d %H:%M')}</p>
<p><b>URL:</b> <a href="{self.article.url}">{self.article.url}</a></p>
<p><b>Word Count:</b> {self.article.word_count or 'Unknown'}</p>
<p><b>Relevance Score:</b> {self.article.relevance_score or 'Not scored'}</p>
"""

        if self.article.practice_areas:
            metadata_text += (
                f"<p><b>Practice Areas:</b> {self.article.practice_areas}</p>"
            )
        if self.article.dollar_amount:
            metadata_text += (
                f"<p><b>Dollar Amount:</b> {self.article.dollar_amount}</p>"
            )
        if self.article.whistleblower_indicators:
            metadata_text += f"<p><b>Whistleblower Elements:</b> {self.article.whistleblower_indicators}</p>"

        metadata_label = QLabel(metadata_text)
        metadata_label.setWordWrap(True)
        metadata_label.setOpenExternalLinks(True)
        layout.addWidget(metadata_label)

        # Article content
        content_label = QLabel("<b>Article Content:</b>")
        layout.addWidget(content_label)

        content_text = QTextEdit()
        content_text.setPlainText(self.article.content)
        content_text.setReadOnly(True)
        layout.addWidget(content_text)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
