"""Modularized main window for BlogsAI desktop application."""

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QFrame,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor, QKeySequence
from PyQt5.QtWidgets import QShortcut

# Import blogsai modules

from blogsai.gui.tabs.dashboard_tab import DashboardTab
from blogsai.gui.tabs.collection_tab import CollectionTab
from blogsai.gui.tabs.analysis_tab import AnalysisTab
from blogsai.gui.tabs.reports_tab import ReportsTab


class MainWindow(QMainWindow):
    """Main application window using modularized components."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlogsAI")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize components
        self.base_font_size = 12  # Base font size for scaling
        self.zoom_factor = 1.0  # Current zoom factor

        self.setup_ui()
        self.setup_style()
        self.setup_shortcuts()

        # Load settings through dashboard tab
        if hasattr(self, "dashboard_tab"):
            self.dashboard_tab.settings_manager.load_settings()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts for zoom functionality."""
        # Zoom in shortcuts (Ctrl/Cmd + Plus, Ctrl/Cmd + Equal)
        zoom_in_shortcut1 = QShortcut(QKeySequence.ZoomIn, self)
        zoom_in_shortcut1.activated.connect(self.zoom_in)

        zoom_in_shortcut2 = QShortcut(QKeySequence("Ctrl+="), self)
        zoom_in_shortcut2.activated.connect(self.zoom_in)

        # Zoom out shortcut (Ctrl/Cmd + Minus)
        zoom_out_shortcut = QShortcut(QKeySequence.ZoomOut, self)
        zoom_out_shortcut.activated.connect(self.zoom_out)

        # Reset zoom shortcut (Ctrl/Cmd + 0)
        reset_zoom_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        reset_zoom_shortcut.activated.connect(self.reset_zoom)

        # For macOS, also add Cmd shortcuts
        if sys.platform == "darwin":
            cmd_zoom_in = QShortcut(QKeySequence("Cmd+="), self)
            cmd_zoom_in.activated.connect(self.zoom_in)

            cmd_zoom_out = QShortcut(QKeySequence("Cmd+-"), self)
            cmd_zoom_out.activated.connect(self.zoom_out)

            cmd_reset_zoom = QShortcut(QKeySequence("Cmd+0"), self)
            cmd_reset_zoom.activated.connect(self.reset_zoom)

    def zoom_in(self):
        """Increase font size."""
        if self.zoom_factor < 3.0:  # Maximum 300% zoom
            self.zoom_factor += 0.1
            self.apply_zoom()

    def zoom_out(self):
        """Decrease font size."""
        if self.zoom_factor > 0.5:  # Minimum 50% zoom
            self.zoom_factor -= 0.1
            self.apply_zoom()

    def reset_zoom(self):
        """Reset font size to default."""
        self.zoom_factor = 1.0
        self.apply_zoom()

    def apply_zoom(self):
        """Apply the current zoom factor to the application."""
        # Calculate new font size
        new_font_size = int(self.base_font_size * self.zoom_factor)

        # Create new font
        font = QFont()
        font.setPointSize(new_font_size)

        # Apply scaling to the entire application
        app = QApplication.instance()
        if app:
            # Set the font for the application
            app.setFont(font)

            # Update title font dynamically
            if hasattr(self, "title_label"):
                title_font_size = int(20 * self.zoom_factor)  # Scale from base 20pt
                title_font = QFont("Arial", title_font_size, QFont.Bold)
                self.title_label.setFont(title_font)

            # Combine base styles with zoom-specific styles
            zoom_style = (
                self.base_styles
                + f"""
                QWidget {{
                    font-size: {new_font_size}pt;
                }}
                QPushButton {{
                    font-size: {new_font_size}pt;
                    padding: {int(8 * self.zoom_factor)}px {int(16 * self.zoom_factor)}px;
                    min-height: {int(32 * self.zoom_factor)}px;
                }}
                QLabel {{
                    font-size: {new_font_size}pt;
                }}
                QLineEdit {{
                    font-size: {new_font_size}pt;
                    padding: {int(6 * self.zoom_factor)}px;
                    min-height: {int(24 * self.zoom_factor)}px;
                }}
                QTextEdit {{
                    font-size: {new_font_size}pt;
                    padding: {int(6 * self.zoom_factor)}px;
                }}
                QComboBox {{
                    font-size: {new_font_size}pt;
                    padding: {int(6 * self.zoom_factor)}px;
                    min-height: {int(24 * self.zoom_factor)}px;
                }}
                QTableWidget {{
                    font-size: {new_font_size}pt;
                }}
                QTableWidget::item {{
                    padding: {int(6 * self.zoom_factor)}px;
                    min-height: {int(20 * self.zoom_factor)}px;
                }}
                QHeaderView::section {{
                    font-size: {new_font_size}pt;
                    padding: {int(8 * self.zoom_factor)}px;
                    min-height: {int(24 * self.zoom_factor)}px;
                }}
                QCheckBox {{
                    font-size: {new_font_size}pt;
                    spacing: {int(6 * self.zoom_factor)}px;
                }}
                QGroupBox {{
                    font-size: {new_font_size}pt;
                    font-weight: bold;
                    padding-top: {int(15 * self.zoom_factor)}px;
                }}
                QTabBar::tab {{
                    font-size: {new_font_size}pt;
                    padding: {int(8 * self.zoom_factor)}px {int(16 * self.zoom_factor)}px;
                    min-height: {int(20 * self.zoom_factor)}px;
                }}
                QDateEdit {{
                    font-size: {new_font_size}pt;
                    padding: {int(6 * self.zoom_factor)}px;
                    min-height: {int(24 * self.zoom_factor)}px;
                }}
                QListWidget {{
                    font-size: {new_font_size}pt;
                }}
                QListWidget::item {{
                    padding: {int(4 * self.zoom_factor)}px;
                    min-height: {int(18 * self.zoom_factor)}px;
                }}
                QProgressBar {{
                    font-size: {new_font_size}pt;
                    text-align: center;
                    min-height: {int(20 * self.zoom_factor)}px;
                }}
            """
            )

            # Apply the combined style sheet
            self.setStyleSheet(zoom_style)

        # Update the status to show current zoom level
        zoom_percentage = int(self.zoom_factor * 100)

        # Update the menu zoom indicator
        if hasattr(self, "zoom_action"):
            self.zoom_action.setText(f"Zoom: {zoom_percentage}%")

        # Force a repaint to ensure all widgets update
        self.update()

    def setup_menu_bar(self):
        """Set up the application menu bar."""
        menubar = self.menuBar()

        # View menu for zoom controls
        view_menu = menubar.addMenu("View")

        # Zoom In action
        zoom_in_action = view_menu.addAction("Zoom In")
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.zoom_in)

        # Zoom Out action
        zoom_out_action = view_menu.addAction("Zoom Out")
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.zoom_out)

        # Reset Zoom action
        reset_zoom_action = view_menu.addAction("Reset Zoom")
        reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_zoom_action.triggered.connect(self.reset_zoom)

        view_menu.addSeparator()

        # Zoom level indicator (non-clickable)
        self.zoom_action = view_menu.addAction("Zoom: 100%")
        self.zoom_action.setEnabled(False)  # Make it non-clickable

    def setup_ui(self):
        """Set up the user interface."""
        # Set up menu bar
        self.setup_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Create hidden status label for backward compatibility (will be removed)
        self.status_label = QLabel()
        self.status_label.setVisible(False)

        # Create tabs using modular components
        self.create_tabs()

        # Connect tab change signal to refresh reports when Reports tab is selected
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def create_tabs(self):
        """Create all tabs using modular components."""
        # Dashboard tab
        self.dashboard_tab = DashboardTab(self)
        self.tabs.addTab(self.dashboard_tab, "Dashboard")

        # News Collection tab
        self.collection_tab = CollectionTab(self)
        self.tabs.addTab(self.collection_tab, "News Collection")

        # Analysis tab
        self.analysis_tab = AnalysisTab(self)
        self.tabs.addTab(self.analysis_tab, "Analysis")

        # Reports tab
        self.reports_tab = ReportsTab(self)
        self.tabs.addTab(self.reports_tab, "Reports")

    def on_tab_changed(self, index):
        """Handle tab change events."""
        # Get the current widget
        current_widget = self.tabs.widget(index)

        # If Reports tab is selected, refresh the reports list
        if current_widget == self.reports_tab:
            self.reports_tab.refresh_on_tab_switch()

    def setup_style(self):
        """Set up the application styling."""
        # Store base styles that will be combined with zoom styles
        self.base_styles = """
            QMainWindow {
                background-color: #ecf0f1;
            }
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #bdc3c7;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #3498db;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin: 10px 0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """

        # Apply initial zoom (100%)
        self.apply_zoom()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("BlogsAI")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("BlogsAI")

    # Force light theme - disable dark mode
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton, True)

    # Set light palette to override system dark mode
    light_palette = QPalette()
    light_palette.setColor(QPalette.Window, QColor(236, 240, 241))  # #ecf0f1
    light_palette.setColor(QPalette.WindowText, QColor(0, 0, 0))  # Black text
    light_palette.setColor(QPalette.Base, QColor(255, 255, 255))  # White background
    light_palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    light_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
    light_palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    light_palette.setColor(QPalette.Text, QColor(0, 0, 0))
    light_palette.setColor(QPalette.Button, QColor(240, 240, 240))
    light_palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    light_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    light_palette.setColor(QPalette.Link, QColor(52, 152, 219))  # #3498db
    light_palette.setColor(QPalette.Highlight, QColor(52, 152, 219))
    light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))

    app.setPalette(light_palette)

    # Create and show main window
    window = MainWindow()
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
