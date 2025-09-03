"""Dashboard tab for the main application."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QTabWidget,
    QScrollArea,
)
from PyQt5.QtCore import Qt

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.core import get_db
from blogsai.database.models import Article, Report, Source
from blogsai.gui.settings.settings_manager import SettingsManager


class DashboardTab(QWidget):
    """Dashboard tab containing stats and settings."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings_manager = SettingsManager(main_window)
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

        # Stats section
        stats_group = self.create_stats_section()
        layout.addWidget(stats_group)

        # Settings section
        settings_group = self.create_settings_section()
        layout.addWidget(settings_group)

        layout.addStretch()

        # Set the content widget to the scroll area and add scroll area to tab
        scroll_area.setWidget(content_widget)

        # Create tab layout and add scroll area
        tab_layout = QVBoxLayout(self)
        tab_layout.addWidget(scroll_area)

    def create_stats_section(self):
        """Create the quick stats section."""
        stats_group = QGroupBox("Quick Stats")
        stats_layout = QGridLayout(stats_group)

        # Get actual stats from database
        db = get_db()
        try:
            total_articles = db.query(Article).count()
            total_reports = db.query(Report).count()
            total_sources = db.query(Source).count()

            recent_articles = (
                db.query(Article)
                .filter(Article.scraped_at >= datetime.now() - timedelta(days=7))
                .count()
            )
        except:
            total_articles = total_reports = total_sources = recent_articles = 0
        finally:
            db.close()

        stats_layout.addWidget(QLabel(f"Total Articles: {total_articles}"), 0, 0)
        stats_layout.addWidget(QLabel(f"Total Reports: {total_reports}"), 0, 1)
        stats_layout.addWidget(QLabel(f"Active Sources: {total_sources}"), 1, 0)
        stats_layout.addWidget(QLabel(f"Articles This Week: {recent_articles}"), 1, 1)

        return stats_group

    def create_settings_section(self):
        """Create the configuration settings section."""
        settings_group = QGroupBox("Configuration Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Settings tabs
        self.settings_tabs = QTabWidget()

        # Application Settings tab
        self.settings_tabs.addTab(
            self.settings_manager.create_app_settings_tab(), "App Settings"
        )

        # Source Settings tab
        self.settings_tabs.addTab(
            self.settings_manager.create_source_settings_tab(), "Sources"
        )

        # Prompts Management tab
        self.settings_tabs.addTab(self.settings_manager.create_prompts_tab(), "Prompts")

        settings_layout.addWidget(self.settings_tabs)

        # Save settings button
        save_settings_btn = QPushButton("Save All Settings")
        save_settings_btn.clicked.connect(self.settings_manager.save_all_settings)
        save_settings_btn.setStyleSheet("font-weight: bold; background-color: #27ae60;")
        settings_layout.addWidget(save_settings_btn)

        return settings_group
