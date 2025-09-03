"""News collection tab for scraping from various sources."""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QDateEdit,
    QLineEdit,
    QTextEdit,
    QProgressBar,
    QScrollArea,
    QMessageBox,
    QDialog,
)
from PyQt5.QtCore import Qt, QDate

from ..workers.scraping_worker import ScrapingWorker, URLScrapingWorker


class CollectionTab(QWidget):
    """News collection tab for scraping from agencies and URLs."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.worker_thread = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Create a scroll area for the tab content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create the content widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # Agency collection section
        agency_group = self.create_agency_section()
        layout.addWidget(agency_group)

        # URL scraping section
        url_group = self.create_url_section()
        layout.addWidget(url_group)

        # Manual article input section
        manual_group = self.create_manual_section()
        layout.addWidget(manual_group)

        # Progress section
        progress_group = self.create_progress_section()
        layout.addWidget(progress_group)

        layout.addStretch()

        # Set the content widget to the scroll area and add scroll area to tab
        scroll_area.setWidget(content_widget)

        # Create tab layout and add scroll area
        tab_layout = QVBoxLayout(self)
        tab_layout.addWidget(scroll_area)

    def create_agency_section(self):
        """Create the agency collection section."""
        agency_group = QGroupBox("Collect from Government Agencies")
        agency_layout = QVBoxLayout(agency_group)

        # Agency selection
        agencies_layout = QHBoxLayout()
        agencies_layout.addWidget(QLabel("Agencies:"))

        self.agency_combo = QComboBox()
        self.agency_combo.addItems(["All Agencies", "DOJ", "SEC", "CFTC"])
        agencies_layout.addWidget(self.agency_combo)

        agencies_layout.addStretch()
        agency_layout.addLayout(agencies_layout)

        # Date range
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))

        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        self.start_date.setCalendarPopup(True)
        date_layout.addWidget(self.start_date)

        date_layout.addWidget(QLabel("To:"))

        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(self.end_date)

        date_layout.addStretch()
        agency_layout.addLayout(date_layout)

        # Collect button
        self.collect_btn = QPushButton("Collect News")
        self.collect_btn.clicked.connect(self.collect_from_agencies)
        agency_layout.addWidget(self.collect_btn)

        return agency_group

    def create_url_section(self):
        """Create the URL scraping section."""
        url_group = QGroupBox("Scrape from URL")
        url_layout = QVBoxLayout(url_group)

        url_input_layout = QHBoxLayout()
        url_input_layout.addWidget(QLabel("URL:"))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/news-article")
        url_input_layout.addWidget(self.url_input)

        self.scrape_url_btn = QPushButton("Scrape URL")
        self.scrape_url_btn.clicked.connect(self.scrape_from_url)
        url_input_layout.addWidget(self.scrape_url_btn)

        url_layout.addLayout(url_input_layout)

        return url_group

    def create_manual_section(self):
        """Create the manual article input section."""
        manual_group = QGroupBox("Add Article Manually")
        manual_layout = QVBoxLayout(manual_group)

        # Description text
        description = QLabel(
            "Add articles manually by entering the title, source, publication date, and content. "
            "This is useful for including relevant articles from Bloomberg, BBC, Reuters, or other sources not automatically scraped."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #666; font-style: italic; margin-bottom: 10px;"
        )
        manual_layout.addWidget(description)

        # Add article button
        self.add_manual_btn = QPushButton("Add Article Manually")
        self.add_manual_btn.clicked.connect(self.open_manual_dialog)
        manual_layout.addWidget(self.add_manual_btn)

        return manual_group

    def create_progress_section(self):
        """Create the progress section."""
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.collection_progress_text = QTextEdit()
        self.collection_progress_text.setMaximumHeight(150)
        self.collection_progress_text.setReadOnly(True)
        progress_layout.addWidget(self.collection_progress_text)

        return progress_group

    def collect_from_agencies(self):
        """Start collecting news from agencies."""
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(
                self, "Warning", "Another operation is already running!"
            )
            return

        # Get form data
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        agencies = (
            self.agency_combo.currentText()
            .lower()
            .replace(" agencies", "")
            .replace("all", "all")
        )

        # Validate dates
        if start_date > end_date:
            QMessageBox.warning(self, "Error", "Start date must be before end date!")
            return

        # Start worker thread
        self.worker_thread = ScrapingWorker(
            start_date=start_date, end_date=end_date, agencies=agencies
        )

        self.worker_thread.progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.collection_finished)
        self.worker_thread.error.connect(self.show_error)

        self.collect_btn.setEnabled(False)
        self.main_window.status_label.setText("Collecting News...")
        self.main_window.status_label.setStyleSheet(
            "color: #f39c12; font-weight: bold;"
        )

        self.worker_thread.start()

    def scrape_from_url(self):
        """Start scraping from a specific URL."""
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(
                self, "Warning", "Another operation is already running!"
            )
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL!")
            return

        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self,
                "Error",
                "Please enter a valid URL starting with http:// or https://!",
            )
            return

        # Start worker thread
        self.worker_thread = URLScrapingWorker(url=url)

        self.worker_thread.progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.collection_finished)
        self.worker_thread.error.connect(self.show_error)

        self.scrape_url_btn.setEnabled(False)
        self.main_window.status_label.setText("Scraping URL...")
        self.main_window.status_label.setStyleSheet(
            "color: #f39c12; font-weight: bold;"
        )

        self.worker_thread.start()

    def update_progress(self, message):
        """Update progress display."""
        from datetime import datetime

        self.collection_progress_text.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        )
        self.collection_progress_text.verticalScrollBar().setValue(
            self.collection_progress_text.verticalScrollBar().maximum()
        )

    def collection_finished(self, result):
        """Handle collection completion."""
        self.collect_btn.setEnabled(True)
        self.scrape_url_btn.setEnabled(True)
        self.main_window.status_label.setText("Collection Complete")
        self.main_window.status_label.setStyleSheet(
            "color: #2ecc71; font-weight: bold;"
        )

        if result.get("success", True):
            message = f"Collection completed successfully!\n\n"
            if "total_articles" in result:
                message += f"Total articles collected: {result['total_articles']}\n"
            if "new_articles" in result:
                message += f"New articles: {result['new_articles']}\n"
            if "duplicate_articles" in result:
                message += f"Duplicates skipped: {result['duplicate_articles']}\n"

            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.warning(
                self,
                "Warning",
                f"Collection completed with issues:\n{result.get('error', 'Unknown error')}",
            )

    def show_error(self, error_message):
        """Show error message."""
        self.collect_btn.setEnabled(True)
        self.scrape_url_btn.setEnabled(True)
        self.main_window.status_label.setText("Error")
        self.main_window.status_label.setStyleSheet(
            "color: #e74c3c; font-weight: bold;"
        )

        QMessageBox.critical(self, "Error", f"Operation failed:\n{error_message}")

    def open_manual_dialog(self):
        """Open the manual article input dialog."""
        from ..dialogs.manual_article_dialog import ManualArticleDialog

        dialog = ManualArticleDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Update progress display to show the article was added
            self.update_progress(f"Manual article added: {dialog.article.title}")

            # Show success message
            QMessageBox.information(
                self,
                "Article Added",
                f"Article '{dialog.article.title}' has been added successfully!\n\n"
                f"You can now analyze it in the Analysis tab.",
            )
