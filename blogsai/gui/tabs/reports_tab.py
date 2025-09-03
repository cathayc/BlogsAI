"""Reports tab for managing generated reports."""

import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QMenu,
    QAction,
)
from PyQt5.QtCore import Qt

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.core import get_db
from blogsai.database.models import Report
from blogsai.gui.dialogs.report_dialog import ReportViewDialog


class ReportsTab(QWidget):
    """Reports tab for viewing and downloading generated reports."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.reports_data = []
        self.setup_ui()
        self.load_reports()

    def refresh_on_tab_switch(self):
        """Called when this tab becomes active to refresh the reports list."""
        self.load_reports()

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

        # Reports list
        reports_group = self.create_reports_section()
        layout.addWidget(reports_group)

        # Set the content widget to the scroll area and add scroll area to tab
        scroll_area.setWidget(content_widget)

        # Create tab layout and add scroll area
        tab_layout = QVBoxLayout(self)
        tab_layout.addWidget(scroll_area)

    def create_reports_section(self):
        """Create the reports management section."""
        reports_group = QGroupBox("Generated Reports")
        reports_layout = QVBoxLayout(reports_group)

        # Reports table
        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(4)
        self.reports_table.setHorizontalHeaderLabels(
            ["Date", "Type", "Articles", "Status"]
        )

        # Make table stretch to fill space
        header = self.reports_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Articles
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Status

        self.reports_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.reports_table.setToolTip(
            "Double-click to view report • Right-click for download options"
        )

        # Connect double-click to view report
        self.reports_table.itemDoubleClicked.connect(self.view_selected_report)

        # Enable right-click context menu
        self.reports_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.reports_table.customContextMenuRequested.connect(self.show_context_menu)

        # Top action bar with refresh button on left
        top_actions_layout = QHBoxLayout()

        # Refresh button (top left)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_reports)
        refresh_btn.setToolTip("Refresh the reports list")
        top_actions_layout.addWidget(refresh_btn)

        top_actions_layout.addStretch()
        reports_layout.addLayout(top_actions_layout)

        reports_layout.addWidget(self.reports_table)

        # Bottom action buttons layout (download options on right)
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()  # Push download buttons to the right

        # Download buttons with format options
        self.download_html_btn = QPushButton("Download HTML")
        self.download_html_btn.clicked.connect(
            lambda: self.download_selected_report("html")
        )
        self.download_html_btn.setEnabled(False)  # Disabled until a report is selected
        actions_layout.addWidget(self.download_html_btn)

        self.download_pdf_btn = QPushButton("Download PDF")
        self.download_pdf_btn.clicked.connect(
            lambda: self.download_selected_report("pdf")
        )
        self.download_pdf_btn.setEnabled(False)  # Disabled until a report is selected
        actions_layout.addWidget(self.download_pdf_btn)

        reports_layout.addLayout(actions_layout)

        # Connect selection changed signal
        self.reports_table.selectionModel().selectionChanged.connect(
            self.on_report_selection_changed
        )

        return reports_group

    def load_reports(self):
        """Load reports into the reports table."""
        self.reports_table.setRowCount(0)

        db = get_db()
        try:
            reports = db.query(Report).order_by(Report.created_at.desc()).all()

            # Store reports data for view/download functionality
            self.reports_data = reports

            self.reports_table.setRowCount(len(reports))

            for i, report in enumerate(reports):
                from ...utils.timezone_utils import format_local_datetime
                
                self.reports_table.setItem(
                    i, 0, QTableWidgetItem(format_local_datetime(report.created_at))
                )
                self.reports_table.setItem(i, 1, QTableWidgetItem(report.report_type))

                # Count articles in report
                article_count = (
                    len(report.report_articles) if report.report_articles else 0
                )
                self.reports_table.setItem(i, 2, QTableWidgetItem(str(article_count)))

                self.reports_table.setItem(i, 3, QTableWidgetItem("Completed"))

        except Exception as e:
            print(f"Error loading reports: {e}")
            self.reports_data = []
        finally:
            db.close()

    def on_report_selection_changed(self):
        """Handle report selection changes."""
        selected_rows = self.reports_table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0

        self.download_html_btn.setEnabled(has_selection)
        self.download_pdf_btn.setEnabled(has_selection)

    def show_context_menu(self, position):
        """Show right-click context menu for download options."""
        if not self.reports_table.itemAt(position):
            return

        selected_rows = self.reports_table.selectionModel().selectedRows()
        if not selected_rows or not self.reports_data:
            return

        menu = QMenu(self)

        # View option
        view_action = QAction("View Report", self)
        view_action.triggered.connect(self.view_selected_report)
        menu.addAction(view_action)

        menu.addSeparator()

        # Download options
        download_html_action = QAction("Download HTML", self)
        download_html_action.triggered.connect(
            lambda: self.download_selected_report("html")
        )
        menu.addAction(download_html_action)

        download_pdf_action = QAction("Download PDF", self)
        download_pdf_action.triggered.connect(
            lambda: self.download_selected_report("pdf")
        )
        menu.addAction(download_pdf_action)

        # Show context menu at cursor position
        menu.exec_(self.reports_table.mapToGlobal(position))

    def view_selected_report(self):
        """View the selected report in a dialog."""
        selected_rows = self.reports_table.selectionModel().selectedRows()
        if not selected_rows or not self.reports_data:
            return

        row = selected_rows[0].row()
        if row < len(self.reports_data):
            report = self.reports_data[row]
            dialog = ReportViewDialog(report, self)
            dialog.exec_()

    def download_selected_report(self, format_type="html"):
        """Download the selected report to a file."""
        selected_rows = self.reports_table.selectionModel().selectedRows()
        if not selected_rows or not self.reports_data:
            return

        row = selected_rows[0].row()
        if row < len(self.reports_data):
            report = self.reports_data[row]

            # Suggest a filename based on format
            safe_title = "".join(
                c for c in report.title if c.isalnum() or c in (" ", "-", "_")
            ).strip()

            if format_type == "pdf":
                default_filename = f"{safe_title}.pdf"
                file_filter = "PDF Files (*.pdf);;All Files (*)"
                dialog_title = "Save Report as PDF"
            else:  # default to HTML
                default_filename = f"{safe_title}.html"
                file_filter = "HTML Files (*.html);;All Files (*)"
                dialog_title = "Save Report as HTML"

            # Open file dialog - default to reports directory
            from ...config.distribution import get_distribution_manager

            dist_manager = get_distribution_manager()
            reports_dir = dist_manager.get_reports_directory()
            default_path = reports_dir / default_filename

            file_path, selected_filter = QFileDialog.getSaveFileName(
                self, dialog_title, str(default_path), file_filter
            )

            if file_path:
                try:
                    # Generate HTML content for the report
                    from blogsai.reporting.generator import ReportGenerator

                    generator = ReportGenerator()

                    # Get articles for this report
                    db = get_db()
                    try:
                        articles = generator._get_report_articles(db, report.id)

                        if format_type == "pdf" or file_path.lower().endswith(".pdf"):
                            # Generate PDF file
                            self.update_progress("Generating PDF report...")
                            generator._generate_pdf(report, articles, Path(file_path))
                        else:
                            # Generate HTML file (default)
                            generator._generate_html(report, articles, Path(file_path))
                    finally:
                        db.close()

                    format_name = "PDF" if format_type == "pdf" else "HTML"
                    QMessageBox.information(
                        self,
                        "Success",
                        f"{format_name} report saved successfully to:\n{file_path}",
                    )

                except Exception as e:
                    QMessageBox.critical(
                        self, "Error", f"Failed to save report:\n{str(e)}"
                    )

    def update_progress(self, message):
        """Update progress (placeholder for compatibility)."""
        # This could be connected to a progress dialog in the future
        print(f"Progress: {message}")
