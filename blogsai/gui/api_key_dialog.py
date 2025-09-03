"""Dialog for API key setup and management."""

import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QGroupBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ..config.credential_manager import CredentialManager


class APIKeySetupDialog(QDialog):
    """Dialog for setting up the OpenAI API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = None
        self.credential_manager = CredentialManager()
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("OpenAI API Key Setup")
        self.setGeometry(200, 200, 600, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("OpenAI API Key Required")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Instructions
        instructions = QLabel(
            "BlogsAI needs an OpenAI API key to analyze articles and generate reports.\n"
            "Your API key will be encrypted and stored securely using your system's secure storage."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(instructions)

        # API Key input
        key_group = QGroupBox("API Key")
        key_layout = QVBoxLayout(key_group)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Enter your OpenAI API key...")
        key_layout.addWidget(self.key_input)

        # Show/hide toggle
        self.toggle_btn = QPushButton("Show")
        self.toggle_btn.clicked.connect(self.toggle_visibility)
        self.toggle_btn.setMaximumWidth(80)
        key_layout.addWidget(self.toggle_btn)

        layout.addWidget(key_group)

        # Instructions for getting API key
        help_group = QGroupBox("How to get your API key")
        help_layout = QVBoxLayout(help_group)

        help_text = QTextEdit()
        help_text.setMaximumHeight(120)
        help_text.setReadOnly(True)
        help_text.setHtml(
            """
        <ol>
        <li>Go to <a href="https://platform.openai.com/api-keys">platform.openai.com/api-keys</a></li>
        <li>Sign in to your OpenAI account (or create one)</li>
        <li>Click "Create new secret key"</li>
        <li>Copy the key and paste it above</li>
        <li>Make sure you have sufficient credits in your OpenAI account</li>
        </ol>
        """
        )
        help_layout.addWidget(help_text)

        layout.addWidget(help_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("Test Key")
        self.test_btn.clicked.connect(self.test_api_key)
        button_layout.addWidget(self.test_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save & Continue")
        save_btn.clicked.connect(self.save_api_key)
        save_btn.setStyleSheet(
            "font-weight: bold; background-color: #27ae60; color: white;"
        )
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def toggle_visibility(self):
        """Toggle API key visibility."""
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.setText("Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.toggle_btn.setText("Show")

    def test_api_key(self):
        """Test the API key."""
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Error", "Please enter an API key first")
            return

        # Basic validation - just check minimum length
        if len(api_key) < 20:
            QMessageBox.warning(
                self, "Error", "API key seems too short. Please check it."
            )
            return

        QMessageBox.information(
            self,
            "Success",
            "API key format looks correct! Click 'Save & Continue' to proceed.",
        )

    def save_api_key(self):
        """Save the API key."""
        api_key = self.key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Error", "Please enter an API key")
            return

        # Basic validation - just check minimum length
        if len(api_key) < 20:
            QMessageBox.warning(
                self, "Error", "API key seems too short. Please check it."
            )
            return

        # Use secure storage to save the key
        success, message = self.credential_manager.save_api_key(api_key)
        if success:
            self.api_key = api_key

            # Show success message
            QMessageBox.information(
                self, "Success", f"API key stored securely.\n\n{message}"
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to save API key:\n\n{message}")

    def get_api_key(self):
        """Get the saved API key."""
        return self.api_key


def prompt_for_api_key(parent=None):
    """Show API key setup dialog and return the key."""
    dialog = APIKeySetupDialog(parent)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_api_key()
    return None
