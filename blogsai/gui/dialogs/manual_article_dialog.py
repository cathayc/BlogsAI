"""Dialog for manually inputting articles."""

import hashlib
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QDateEdit,
    QPushButton,
    QMessageBox,
    QGroupBox,
)
from PyQt5.QtCore import Qt, QDate

from ...config.config import ConfigManager
from ...database.database import DatabaseManager
from ...database.models import Article, Source


class ManualArticleDialog(QDialog):
    """Dialog for manually entering article information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.article = None
        self.config_manager = ConfigManager()
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog interface."""
        self.setWindowTitle("Add Article Manually")
        self.setFixedSize(600, 500)
        self.setModal(True)

        # Main layout
        layout = QVBoxLayout(self)

        # Article information group
        article_group = QGroupBox("Article Information")
        article_layout = QFormLayout(article_group)

        # Title input
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter article title...")
        article_layout.addRow("Title:", self.title_input)

        # Source input
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText(
            "e.g., Bloomberg, BBC, Reuters, Wall Street Journal..."
        )
        article_layout.addRow("Source:", self.source_input)

        # Published date input
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setMaximumDate(QDate.currentDate())
        article_layout.addRow("Published Date:", self.date_input)

        # Content input
        content_label = QLabel("Content:")
        article_layout.addRow(content_label)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText(
            "Paste or type the article content here..."
        )
        self.content_input.setMinimumHeight(200)
        article_layout.addRow(self.content_input)

        layout.addWidget(article_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        self.save_btn = QPushButton("Save Article")
        self.save_btn.clicked.connect(self.save_article)
        self.save_btn.setDefault(True)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Focus on title input
        self.title_input.setFocus()

    def save_article(self):
        """Save the manually entered article to the database."""
        # Get form data
        title = self.title_input.text().strip()
        source_name = self.source_input.text().strip()
        content = self.content_input.toPlainText().strip()
        published_date = self.date_input.date().toPyDate()

        # Validate inputs
        if not title:
            QMessageBox.warning(
                self, "Validation Error", "Please enter a title for the article."
            )
            self.title_input.setFocus()
            return

        if not source_name:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please enter a source for the article (e.g., Bloomberg, BBC, etc.).",
            )
            self.source_input.setFocus()
            return

        if not content:
            QMessageBox.warning(
                self, "Validation Error", "Please enter content for the article."
            )
            self.content_input.setFocus()
            return

        if len(title) > 500:
            QMessageBox.warning(
                self, "Validation Error", "Title must be 500 characters or less."
            )
            self.title_input.setFocus()
            return

        if len(source_name) > 200:
            QMessageBox.warning(
                self, "Validation Error", "Source name must be 200 characters or less."
            )
            self.source_input.setFocus()
            return

        try:
            # Get database connection
            config = self.config_manager.load_config()
            db_manager = DatabaseManager(config.database.url)
            session = db_manager.get_session_sync()

            try:
                # Find or create source with the user-specified name
                source = session.query(Source).filter_by(name=source_name).first()
                if not source:
                    source = Source(
                        name=source_name,
                        source_type="manual",
                        base_url=f"manual://{source_name.lower().replace(' ', '-')}",
                        scraper_type="manual",
                    )
                    session.add(source)
                    session.commit()

                # Generate content hash for deduplication
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # Check if article with same content already exists
                existing_article = (
                    session.query(Article).filter_by(content_hash=content_hash).first()
                )
                if existing_article:
                    from ...utils.timezone_utils import format_local_date
                    
                    QMessageBox.warning(
                        self,
                        "Duplicate Article",
                        f"An article with identical content already exists:\n\n"
                        f"Title: {existing_article.title}\n"
                        f"Date: {format_local_date(existing_article.published_date)}\n\n"
                        f"Please check if this is a duplicate.",
                    )
                    return

                # Generate unique URL for manual articles
                manual_url = f"manual://{source_name.lower().replace(' ', '-')}/article/{content_hash[:16]}"

                # Create the article
                from ...utils.timezone_utils import to_utc
                
                # Convert local date to UTC datetime
                local_datetime = datetime.combine(published_date, datetime.min.time())
                utc_datetime = to_utc(local_datetime)
                
                article = Article(
                    source_id=source.id,
                    title=title,
                    content=content,
                    url=manual_url,
                    content_hash=content_hash,
                    published_date=utc_datetime,
                    word_count=len(content.split()),
                    author=source_name,
                    category="Manual",
                )

                session.add(article)
                session.commit()

                # Store the article for parent to access if needed
                self.article = article

                QMessageBox.information(
                    self,
                    "Success",
                    f"Article '{title}' has been saved successfully!\n\n"
                    f"Source: {source_name}\n"
                    f"Word count: {article.word_count}\n"
                    f"Published date: {published_date.strftime('%Y-%m-%d')}",
                )

                self.accept()

            finally:
                session.close()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to save article:\n{str(e)}\n\n"
                f"Please check the database connection and try again.",
            )
