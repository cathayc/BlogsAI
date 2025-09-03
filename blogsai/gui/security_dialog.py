"""Security status dialog for credential management."""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QGroupBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ..config.env_manager import EnvironmentManager
import os


class SecurityStatusDialog(QDialog):
    """Dialog showing security status and credential storage information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ..config.distribution import get_distribution_manager

        dist_manager = get_distribution_manager()
        self.env_manager = EnvironmentManager(str(dist_manager.get_data_directory()))
        self.setup_ui()
        self.update_status()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Security Status")
        self.setGeometry(200, 200, 550, 400)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("Credential Security Status")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Status display
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(250)
        layout.addWidget(self.status_text)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.update_status)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def update_status(self):
        """Update the security status display."""
        status = self.env_manager.get_security_status()

        # Format status information
        html_content = "<h3>Security Information</h3>"

        # Overall security status
        if status["is_secure"]:
            html_content += (
                "<p><span style='color: green;'><b>Secure Setup</b></span></p>"
            )
        else:
            html_content += "<p><span style='color: orange;'><b>Development/Insecure Setup</b></span></p>"

        # Platform info
        html_content += f"<p><b>Platform:</b> {status['platform']}</p>"

        # Keyring status
        if status["keyring_available"]:
            html_content += f"<p><b>Credential Storage:</b> <span style='color: green;'>Secure Keyring</span></p>"
            html_content += f"<p><b>Backend:</b> {status['backend_info']}</p>"
        else:
            html_content += f"<p><b>Credential Storage:</b> <span style='color: orange;'>.env File (Development)</span></p>"
            html_content += f"<p><b>Issue:</b> {status['backend_info']}</p>"

        # API key status
        if status["has_api_key"]:
            html_content += (
                f"<p><b>API Key:</b> <span style='color: green;'>Configured</span></p>"
            )
            html_content += (
                f"<p><b>Storage Location:</b> {status['storage_location']}</p>"
            )
        else:
            html_content += f"<p><b>API Key:</b> <span style='color: red;'>Not Configured</span></p>"

        # Security recommendations
        html_content += "<h3>Security Recommendations</h3>"

        if status["platform"] == "Linux" and not status["keyring_available"]:
            html_content += """
            <p>For better security on Linux, install a secure keyring backend:</p>
            <ul>
            <li><code>sudo apt-get install python3-secretstorage</code> (Ubuntu/Debian)</li>
            <li><code>sudo yum install python3-keyring</code> (RedHat/CentOS)</li>
            <li>Or install GNOME Keyring: <code>sudo apt-get install gnome-keyring</code></li>
            </ul>
            """
        elif status["platform"] == "Darwin" and not status["keyring_available"]:
            html_content += """
            <p>macOS Keychain should be available by default. If not working:</p>
            <ul>
            <li>Try reinstalling keyring: <code>pip install --upgrade keyring</code></li>
            <li>Check macOS security settings</li>
            </ul>
            """
        elif status["platform"] == "Windows" and not status["keyring_available"]:
            html_content += """
            <p>Windows Credential Manager should be available by default. If not working:</p>
            <ul>
            <li>Try reinstalling keyring: <code>pip install --upgrade keyring</code></li>
            <li>Check Windows security settings</li>
            </ul>
            """

        if status["keyring_available"]:
            html_content += "<p><span style='color: green;'>Your credentials are stored securely!</span></p>"
        else:
            html_content += """
            <p><span style='color: orange;'>Development Mode:</span> 
            Your API key is stored in a plain text .env file. This is fine for development but less secure for production use.</p>
            """

        self.status_text.setHtml(html_content)

        # Show warning if insecure
        warning = self.env_manager.warn_insecure_setup()
        if warning and not hasattr(self, "_warning_shown"):
            self._warning_shown = True
            QMessageBox.warning(self, "Security Notice", warning)


def show_security_status(parent=None):
    """Show the security status dialog."""
    dialog = SecurityStatusDialog(parent)
    dialog.exec_()
