"""Analysis tab for intelligence report generation."""

import sys
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QProgressBar,
    QScrollArea,
    QMessageBox,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.core import get_db
from blogsai.database.models import Article, Source
from blogsai.gui.dialogs.article_dialog import ArticleDetailDialog
from blogsai.gui.workers.analysis_worker import AnalysisWorker


class AnalysisTab(QWidget):
    """Analysis tab for generating intelligence reports."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.worker_thread = None
        self.preview_articles_data = []
        self.selected_article_ids = set()
        self.setup_ui()

        # Initial preview of articles for the default date range
        self.preview_articles()

    def setup_ui(self):
        """Set up the user interface."""
        # Create a scroll area for the entire tab content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create the content widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # Analysis options
        options_group = self.create_options_section()
        layout.addWidget(options_group)

        # Progress section
        progress_group = self.create_progress_section()
        layout.addWidget(progress_group)

        layout.addStretch()

        # Set the content widget to the scroll area and add scroll area to tab
        scroll_area.setWidget(content_widget)

        # Create tab layout and add scroll area
        tab_layout = QVBoxLayout(self)
        tab_layout.addWidget(scroll_area)

    def create_options_section(self):
        """Create the analysis options section."""
        options_group = QGroupBox("Analysis Options")
        options_layout = QVBoxLayout(options_group)

        # Date range for analysis with preview button
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Analyze articles from:"))

        self.analysis_start_date = QDateEdit()
        self.analysis_start_date.setDate(QDate.currentDate().addDays(-7))
        self.analysis_start_date.setCalendarPopup(True)
        date_layout.addWidget(self.analysis_start_date)

        date_layout.addWidget(QLabel("to:"))

        self.analysis_end_date = QDateEdit()
        self.analysis_end_date.setDate(QDate.currentDate())
        self.analysis_end_date.setCalendarPopup(True)
        date_layout.addWidget(self.analysis_end_date)

        # Add some spacing before the preview button
        date_layout.addSpacing(20)

        # Preview button inline with date range
        self.preview_btn = QPushButton("Preview Articles")
        self.preview_btn.clicked.connect(self.preview_articles)
        date_layout.addWidget(self.preview_btn)

        date_layout.addStretch()
        options_layout.addLayout(date_layout)

        # Analysis features
        features_layout = QVBoxLayout()

        self.enable_insights = QCheckBox(
            "Enable Market Intelligence Analysis (with Web Search)"
        )
        self.enable_insights.setChecked(True)
        self.enable_insights.setToolTip(
            "Generate comprehensive market intelligence using web search to find comparable cases, regulatory trends, and market analysis"
        )
        features_layout.addWidget(self.enable_insights)

        self.high_priority_only = QCheckBox(
            "Focus on High Priority Articles Only (score ≥80)"
        )
        self.high_priority_only.setChecked(True)
        self.high_priority_only.setToolTip(
            "When checked, only articles with score ≥80 get detailed analysis. When unchecked, all selected articles get detailed analysis."
        )
        features_layout.addWidget(self.high_priority_only)

        self.force_refresh = QCheckBox("Force Refresh All Analysis")
        features_layout.addWidget(self.force_refresh)

        self.verify_citations = QCheckBox("Verify Citations and Facts")
        features_layout.addWidget(self.verify_citations)

        options_layout.addLayout(features_layout)

        # Articles Preview section
        preview_label = QLabel("Articles Preview")
        preview_label.setFont(QFont("Arial", 12, QFont.Bold))
        preview_label.setStyleSheet("margin-top: 15px; margin-bottom: 5px;")
        options_layout.addWidget(preview_label)

        # Selection info label (initially hidden)
        selection_layout = QHBoxLayout()
        self.selection_info_label = QLabel("")
        self.selection_info_label.setVisible(False)
        self.selection_info_label.setStyleSheet("color: #666; font-style: italic;")

        selection_layout.addWidget(self.selection_info_label)
        selection_layout.addStretch()

        options_layout.addLayout(selection_layout)

        # Articles table
        self.articles_table = QTableWidget()
        self.articles_table.setColumnCount(6)
        self.articles_table.setHorizontalHeaderLabels(
            ["", "Date", "Source", "Title", "Relevance Score", "Modified"]
        )

        # Add select all checkbox and delete button above the table
        table_controls_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.setChecked(True)  # Default to checked
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        table_controls_layout.addWidget(self.select_all_checkbox)

        # Delete articles button next to select all
        self.delete_btn = QPushButton("Delete Articles")
        self.delete_btn.clicked.connect(self.delete_selected_articles)
        self.delete_btn.setEnabled(False)  # Disabled until articles are loaded
        self.delete_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold;"
        )
        self.delete_btn.setToolTip(
            "Delete selected articles and all associated scoring/analysis data"
        )
        table_controls_layout.addWidget(self.delete_btn)

        table_controls_layout.addStretch()
        options_layout.addLayout(table_controls_layout)

        # Make table stretch to fill space
        header = self.articles_table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.Fixed
        )  # Select checkbox - fixed width
        self.articles_table.setColumnWidth(
            0, 60
        )  # Set checkbox column to 60 pixels wide
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Source
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Title
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Score
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Modified

        # Calculate dynamic height
        table_height = min(500, max(250, 400))
        self.articles_table.setMinimumHeight(table_height)
        self.articles_table.setAlternatingRowColors(True)
        self.articles_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.articles_table.setToolTip(
            "Double-click a row to view full article details"
        )
        self.articles_table.itemDoubleClicked.connect(self.show_article_details)
        options_layout.addWidget(self.articles_table)

        # Articles count label
        self.articles_count_label = QLabel(
            "Articles automatically update when date range changes."
        )
        self.articles_count_label.setStyleSheet("color: #666; font-style: italic;")
        options_layout.addWidget(self.articles_count_label)

        # Output options
        output_layout = self.create_output_section()
        options_layout.addLayout(output_layout)

        # Button layout for analysis and report generation
        button_layout = QHBoxLayout()

        # Generate Report button
        self.generate_btn = QPushButton("Generate Intelligence Report")
        self.generate_btn.clicked.connect(self.generate_intelligence_report)
        button_layout.addWidget(self.generate_btn)

        options_layout.addLayout(button_layout)

        # Connect date change events to auto-preview
        self.analysis_start_date.dateChanged.connect(self.on_date_changed)
        self.analysis_end_date.dateChanged.connect(self.on_date_changed)

        return options_group

    def create_output_section(self):
        """Create the output options section."""
        output_layout = QVBoxLayout()

        # File path and format selection in one line
        # Order: "Save report to:" textbox -> format -> browse -> generate
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save report to:"))

        self.output_path = QLineEdit()
        self.output_path.setText(str(Path.home() / "BlogsAI_Report.html"))
        path_layout.addWidget(self.output_path)

        # Format selection between textbox and browse button
        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "PDF"])
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.format_combo.setToolTip("Select report format")
        path_layout.addWidget(self.format_combo)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_output_path)
        path_layout.addWidget(self.browse_btn)

        output_layout.addLayout(path_layout)

        return output_layout

    def create_progress_section(self):
        """Create the progress section."""
        progress_group = QGroupBox("Analysis Progress")
        progress_layout = QVBoxLayout(progress_group)

        # Progress bar removed per user request

        self.analysis_progress_text = QTextEdit()
        self.analysis_progress_text.setMinimumHeight(300)
        self.analysis_progress_text.setReadOnly(True)
        progress_layout.addWidget(self.analysis_progress_text)

        return progress_group

    def on_date_changed(self):
        """Handle date change to auto-preview articles."""
        # Automatically refresh articles when date range changes
        self.preview_articles()

    def preview_articles(self):
        """Preview articles that will be used for the report."""
        start_date = self.analysis_start_date.date().toPyDate()
        end_date = self.analysis_end_date.date().toPyDate()

        # Validate dates
        if start_date > end_date:
            QMessageBox.warning(self, "Error", "Start date must be before end date!")
            return

        # Convert to datetime for database query
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Query articles from database
        db = get_db()
        try:
            articles = (
                db.query(Article)
                .join(Source)
                .filter(
                    Article.published_date >= start_datetime,
                    Article.published_date <= end_datetime,
                )
                .order_by(Article.published_date.desc())
                .all()
            )

            # Store articles data for detail view
            self.preview_articles_data = articles

            # Initialize selection: select all by default
            self.selected_article_ids = {article.id for article in articles}

            # Update the table
            self.articles_table.setRowCount(len(articles))

            for i, article in enumerate(articles):
                # Checkbox for selection
                from PyQt5.QtWidgets import QCheckBox

                checkbox = QCheckBox()
                checkbox.setChecked(True)  # Default to selected
                checkbox.stateChanged.connect(
                    lambda state, aid=article.id: self.on_article_selection_changed(
                        aid, state
                    )
                )
                self.articles_table.setCellWidget(i, 0, checkbox)

                # Date
                date_item = QTableWidgetItem(
                    article.published_date.strftime("%Y-%m-%d")
                )
                self.articles_table.setItem(i, 1, date_item)

                # Source
                source_item = QTableWidgetItem(article.source.name)
                self.articles_table.setItem(i, 2, source_item)

                title = article.title
                title_item = QTableWidgetItem(title)
                title_item.setToolTip(article.title)  # Full title on hover
                self.articles_table.setItem(i, 3, title_item)

                # Relevance Score
                score = (
                    article.relevance_score
                    if article.relevance_score is not None
                    else "Not scored"
                )
                score_item = QTableWidgetItem(str(score))
                if isinstance(score, int):
                    # Color code the scores
                    if score >= 80:
                        score_item.setBackground(QColor(212, 237, 218))  # Light green
                    elif score >= 60:
                        score_item.setBackground(QColor(255, 243, 205))  # Light yellow
                    else:
                        score_item.setBackground(QColor(248, 215, 218))  # Light red
                self.articles_table.setItem(i, 4, score_item)

                # Modified At
                modified_at = (
                    article.modified_at if article.modified_at else article.scraped_at
                )
                modified_item = QTableWidgetItem(modified_at.strftime("%Y-%m-%d %H:%M"))
                self.articles_table.setItem(i, 5, modified_item)

            # Update count label
            high_priority_count = sum(
                1
                for article in articles
                if article.relevance_score and article.relevance_score >= 80
            )

            if len(articles) == 0:
                self.articles_count_label.setText(
                    "No articles found for the selected date range."
                )
                self.articles_count_label.setStyleSheet(
                    "color: #dc3545; font-style: italic;"
                )
                # Hide selection controls
                self.selection_info_label.setVisible(False)
            else:
                count_text = f"Found {len(articles)} articles"
                if high_priority_count > 0:
                    count_text += (
                        f" ({high_priority_count} high priority with score ≥80)"
                    )
                count_text += f" for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                self.articles_count_label.setText(count_text)
                self.articles_count_label.setStyleSheet(
                    "color: #28a745; font-style: normal;"
                )

                # Show selection controls
                self.selection_info_label.setVisible(True)
                self.update_selection_info()
                self.update_select_all_checkbox()

                # Enable delete button when articles are loaded
                self.delete_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to preview articles:\n{str(e)}"
            )
            self.articles_count_label.setText(f"Error loading articles: {str(e)}")
            self.articles_count_label.setStyleSheet(
                "color: #dc3545; font-style: italic;"
            )
        finally:
            db.close()

    def delete_selected_articles(self):
        """Delete selected articles and all associated scoring/analysis data."""
        if not self.selected_article_ids:
            QMessageBox.warning(
                self, "No Selection", "Please select articles to delete."
            )
            return

        # Confirm deletion
        selected_count = len(self.selected_article_ids)
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {selected_count} selected article(s) and all associated scoring/analysis data?\n\n"
            "This action cannot be undone and will NOT affect existing reports.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # Import database manager and config
            from blogsai.database.database import DatabaseManager
            from blogsai.config.config import ConfigManager

            # Get database URL from config
            config_manager = ConfigManager()
            config = config_manager.load_config()

            # Delete articles using the database manager
            db_manager = DatabaseManager(config.database.url)
            result = db_manager.delete_articles(list(self.selected_article_ids))

            if result["success"]:
                QMessageBox.information(
                    self,
                    "Deletion Complete",
                    f"Successfully deleted {result['articles_deleted']} articles and "
                    f"{result['report_associations_deleted']} report associations.",
                )

                # Refresh the article preview to show updated data
                self.preview_articles()

            else:
                QMessageBox.critical(
                    self,
                    "Deletion Failed",
                    f"Failed to delete articles: {result['error']}",
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while deleting articles:\n{str(e)}"
            )

    def on_article_selection_changed(self, article_id, state):
        """Handle changes in article selection checkboxes."""
        if state == 2:  # Qt.Checked
            self.selected_article_ids.add(article_id)
        else:  # Qt.Unchecked
            self.selected_article_ids.discard(article_id)

        self.update_selection_info()
        self.update_select_all_checkbox()

    def update_selection_info(self):
        """Update the selection information label."""
        if hasattr(self, "preview_articles_data"):
            total_articles = len(self.preview_articles_data)
            selected_count = len(self.selected_article_ids)

            # Count selected high priority articles
            selected_high_priority = 0
            for article in self.preview_articles_data:
                if (
                    article.id in self.selected_article_ids
                    and article.relevance_score
                    and article.relevance_score >= 80
                ):
                    selected_high_priority += 1

            info_text = f"{selected_count} of {total_articles} articles selected"
            if selected_high_priority > 0:
                info_text += f" ({selected_high_priority} high priority)"

            self.selection_info_label.setText(info_text)

    def show_article_details(self, item):
        """Show detailed information about the selected article."""
        row = item.row()
        if row < len(self.preview_articles_data):
            article = self.preview_articles_data[row]
            dialog = ArticleDetailDialog(article, self)
            dialog.exec_()

    def on_format_changed(self, format_type):
        """Handle format selection change."""
        current_path = Path(self.output_path.text())
        base_name = current_path.stem
        parent_dir = current_path.parent

        if format_type == "HTML":
            new_path = parent_dir / f"{base_name}.html"
        elif format_type == "PDF":
            new_path = parent_dir / f"{base_name}.pdf"
        else:
            new_path = current_path

        self.output_path.setText(str(new_path))

    def browse_output_path(self):
        """Browse for output file path."""
        format_type = self.format_combo.currentText()

        if format_type == "HTML":
            filter_text = "HTML Files (*.html);;All Files (*)"
            default_name = "BlogsAI_Report.html"
        elif format_type == "PDF":
            filter_text = "PDF Files (*.pdf);;All Files (*)"
            default_name = "BlogsAI_Report.pdf"
        else:
            filter_text = "All Files (*)"
            default_name = "BlogsAI_Report.html"

        # Default to reports directory
        from ...config.distribution import get_distribution_manager

        dist_manager = get_distribution_manager()
        reports_dir = dist_manager.get_reports_directory()
        default_path = reports_dir / default_name

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Report As", str(default_path), filter_text
        )

        if file_path:
            self.output_path.setText(file_path)

    def generate_intelligence_report(self):
        """Generate an intelligence report."""
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(
                self, "Warning", "Another operation is already running!"
            )
            return

        # Validate that articles have been previewed and selected
        if not hasattr(self, "selected_article_ids") or not self.selected_article_ids:
            QMessageBox.warning(
                self,
                "Error",
                "Please preview articles first and select which ones to include in the analysis!",
            )
            return

        # Get form data
        start_date = self.analysis_start_date.date().toPyDate()
        end_date = self.analysis_end_date.date().toPyDate()
        enable_insights = self.enable_insights.isChecked()
        high_priority_only = self.high_priority_only.isChecked()
        force_refresh = self.force_refresh.isChecked()

        # Validate dates
        if start_date > end_date:
            QMessageBox.warning(self, "Error", "Start date must be before end date!")
            return

        # Convert dates to datetime
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Get format and output path
        output_format = self.format_combo.currentText()
        output_path = self.output_path.text()

        # Start worker thread
        self.worker_thread = AnalysisWorker(
            start_date=start_datetime,
            end_date=end_datetime,
            selected_article_ids=list(self.selected_article_ids),
            enable_insights=enable_insights,
            high_priority_only=high_priority_only,
            force_refresh=force_refresh,
            output_format=output_format,
            output_path=output_path,
        )

        self.worker_thread.progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.report_finished)
        self.worker_thread.error.connect(self.show_error)

        self.generate_btn.setEnabled(False)
        # Progress bar removed
        self.main_window.status_label.setText("Generating Report...")
        self.main_window.status_label.setStyleSheet(
            "color: #f39c12; font-weight: bold;"
        )

        self.worker_thread.start()

    def update_progress(self, message):
        """Update progress display."""
        self.analysis_progress_text.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        )
        self.analysis_progress_text.verticalScrollBar().setValue(
            self.analysis_progress_text.verticalScrollBar().maximum()
        )

    def report_finished(self, result):
        """Handle report generation completion."""
        self.generate_btn.setEnabled(True)
        # Progress bar removed
        self.main_window.status_label.setText("Report Complete")
        self.main_window.status_label.setStyleSheet(
            "color: #2ecc71; font-weight: bold;"
        )

        if result.get("success", True):
            output_file = result.get("output_file", self.output_path.text())
            format_type = self.format_combo.currentText()

            QMessageBox.information(
                self,
                "Success",
                f"{format_type} report generated successfully!\n\nSaved to: {output_file}\n\nArticles analyzed: {result.get('article_count', 'Unknown')}",
            )
        else:
            # Check for specific error types
            error_type = result.get("error_type")
            if error_type == "api_key_invalid":
                QMessageBox.critical(
                    self,
                    "Invalid API Key",
                    f"OpenAI API Key Error\n\n"
                    f"{result.get('error', '')}\n\n"
                    f"To fix this:\n"
                    f"1. Go to Dashboard → App Settings\n"
                    f"2. Enter your valid OpenAI API key\n"
                    f"3. Click 'Save All Settings'\n"
                    f"4. Try again\n\n"
                    f"Get your API key from: https://platform.openai.com/api-keys",
                )
            elif error_type == "openai_api_error":
                QMessageBox.critical(
                    self,
                    "OpenAI API Error",
                    f"OpenAI API Issue\n\n"
                    f"{result.get('error', '')}\n\n"
                    f"This could be due to:\n"
                    f"• Rate limits (try again in a moment)\n"
                    f"• Insufficient API credits\n"
                    f"• Network connectivity issues\n"
                    f"• OpenAI service problems\n\n"
                    f"Check your OpenAI account at: https://platform.openai.com/",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Report generation failed:\n{result.get('error', 'Unknown error')}",
                )

    def on_select_all_changed(self, state):
        """Handle select all checkbox state change."""
        is_checked = state == Qt.Checked

        # Update all article checkboxes
        for row in range(self.articles_table.rowCount()):
            checkbox = self.articles_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(is_checked)

        # Update selection info
        self.update_selection_info()

    def update_select_all_checkbox(self):
        """Update the select all checkbox based on individual selections."""
        if not hasattr(self, "select_all_checkbox"):
            return

        total_articles = self.articles_table.rowCount()
        if total_articles == 0:
            return

        checked_count = 0
        for row in range(total_articles):
            checkbox = self.articles_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                checked_count += 1

        # Block signals to prevent recursive calls
        self.select_all_checkbox.blockSignals(True)

        if checked_count == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif checked_count == total_articles:
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)

        # Unblock signals
        self.select_all_checkbox.blockSignals(False)

    def show_error(self, error_message):
        """Show error message."""
        self.generate_btn.setEnabled(True)
        # Progress bar removed
        self.main_window.status_label.setText("Error")
        self.main_window.status_label.setStyleSheet(
            "color: #e74c3c; font-weight: bold;"
        )

        QMessageBox.critical(self, "Error", f"Operation failed:\n{error_message}")
