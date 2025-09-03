#!/usr/bin/env python3
"""
Setup dialog for BlogsAI - allows users to choose data directory location.
"""

import os
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QTextEdit,
    QMessageBox,
    QApplication,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap


class SetupDialog(QDialog):
    """First-run setup dialog for choosing data directory."""

    def __init__(self):
        super().__init__()
        self.selected_path = None
        self.init_ui()

    def init_ui(self):
        """Initialize the setup dialog UI."""
        self.setWindowTitle("BlogsAI Setup - Choose Data Location")
        self.setFixedSize(600, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Welcome header
        self.create_welcome_section(layout)

        # Location selection
        self.create_location_section(layout)

        # Info section
        self.create_info_section(layout)

        # Buttons
        self.create_buttons(layout)

        # Set default selection
        self.recommended_radio.setChecked(True)
        self.on_location_changed()

    def create_welcome_section(self, layout):
        """Create welcome header section."""
        welcome_group = QGroupBox()
        welcome_layout = QVBoxLayout(welcome_group)

        # Title
        title = QLabel("Welcome to BlogsAI!")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(title)

        # Description
        desc = QLabel(
            "BlogsAI needs a location to store your settings, prompts, reports, and data.\n"
            "Please choose where you'd like these files to be stored:"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(desc)

        layout.addWidget(welcome_group)

    def create_location_section(self, layout):
        """Create location selection section."""
        location_group = QGroupBox("Data Location")
        location_layout = QVBoxLayout(location_group)

        # Create radio button group
        self.location_group = QButtonGroup(self)

        # Option 1: Recommended location
        self.recommended_radio = QRadioButton("Recommended Location")
        self.recommended_radio.setFont(QFont("Arial", 10, QFont.Bold))
        location_layout.addWidget(self.recommended_radio)
        self.location_group.addButton(self.recommended_radio, 1)

        # Show recommended path
        recommended_path = self.get_recommended_path()
        self.recommended_label = QLabel(f"   {recommended_path}")
        self.recommended_label.setStyleSheet("color: #666; margin-left: 20px;")
        location_layout.addWidget(self.recommended_label)

        # Benefits of recommended location
        benefits = QLabel("   Easy to find | Automatic backups | Standard location")
        benefits.setStyleSheet(
            "color: #2ecc71; margin-left: 20px; margin-bottom: 10px;"
        )
        location_layout.addWidget(benefits)

        # Option 2: Custom location
        self.custom_radio = QRadioButton("Custom Location")
        self.custom_radio.setFont(QFont("Arial", 10, QFont.Bold))
        location_layout.addWidget(self.custom_radio)
        self.location_group.addButton(self.custom_radio, 2)

        # Custom path selection
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(20, 0, 0, 0)

        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Choose a folder...")
        self.custom_path.setEnabled(False)
        custom_layout.addWidget(self.custom_path)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self.browse_for_folder)
        custom_layout.addWidget(self.browse_btn)

        location_layout.addLayout(custom_layout)

        # Connect radio buttons
        self.location_group.buttonClicked.connect(self.on_location_changed)

        layout.addWidget(location_group)

    def create_info_section(self, layout):
        """Create information section."""
        info_group = QGroupBox("What will be stored here?")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setMaximumHeight(120)
        info_text.setReadOnly(True)
        info_text.setHtml(
            """
        <b>config/</b> - Application settings and source configurations<br>
        <b>prompts/</b> - AI prompts that you can customize<br>
        <b>reports/</b> - Generated intelligence reports (HTML, PDF)<br>
        <b>logs/</b> - Application logs for troubleshooting<br>
        <b>blogsai.db</b> - Your articles and analysis database<br><br>
        <i>You can change this location later in Settings</i>
        """
        )
        info_layout.addWidget(info_text)

        layout.addWidget(info_group)

    def create_buttons(self, layout):
        """Create dialog buttons."""
        button_layout = QHBoxLayout()

        # Space filler
        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Continue button
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        )
        self.continue_btn.clicked.connect(self.accept_setup)
        button_layout.addWidget(self.continue_btn)

        layout.addLayout(button_layout)

    def get_recommended_path(self):
        """Get the recommended path for the current platform."""
        import platform

        system = platform.system()

        if system == "Windows":
            documents = Path.home() / "Documents"
            if documents.exists():
                return str(documents / "BlogsAI")
            else:
                return str(Path.home() / "BlogsAI")
        elif system == "Darwin":  # macOS
            return str(Path.home() / "BlogsAI")
        else:  # Linux
            return str(Path.home() / ".local/share/BlogsAI")

    def on_location_changed(self):
        """Handle location selection change."""
        if self.recommended_radio.isChecked():
            self.custom_path.setEnabled(False)
            self.browse_btn.setEnabled(False)
            self.selected_path = self.get_recommended_path()
        else:
            self.custom_path.setEnabled(True)
            self.browse_btn.setEnabled(True)
            self.selected_path = (
                self.custom_path.text() if self.custom_path.text() else None
            )

        # Update continue button state
        self.continue_btn.setEnabled(bool(self.selected_path))

    def browse_for_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose BlogsAI Data Directory",
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )

        if folder:
            # Append BlogsAI to the selected folder
            blogsai_folder = Path(folder) / "BlogsAI"
            self.custom_path.setText(str(blogsai_folder))
            self.selected_path = str(blogsai_folder)
            self.continue_btn.setEnabled(True)

    def accept_setup(self):
        """Accept the setup and validate the selection."""
        if not self.selected_path:
            QMessageBox.warning(self, "Error", "Please select a data directory.")
            return

        data_path = Path(self.selected_path)

        # Check if directory exists and is writable
        try:
            data_path.mkdir(parents=True, exist_ok=True)

            # Test write permissions
            test_file = data_path / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Cannot create or write to the selected directory:\n{str(e)}\n\nPlease choose a different location.",
            )
            return

        # Show confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Setup",
            f"BlogsAI data will be stored in:\n{self.selected_path}\n\nIs this correct?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.accept()

    def get_selected_path(self):
        """Get the user's selected data path."""
        return self.selected_path


def show_setup_dialog():
    """Show the setup dialog and return the selected path."""
    # Create QApplication if it doesn't exist
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    dialog = SetupDialog()
    result = dialog.exec_()

    if result == QDialog.Accepted:
        return dialog.get_selected_path()
    else:
        return None


if __name__ == "__main__":
    # Test the dialog
    path = show_setup_dialog()
    if path:
        print(f"Selected path: {path}")
    else:
        print("Setup cancelled")
