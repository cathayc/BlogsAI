"""First-time setup dialog for production builds."""

import os
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.config.distribution import get_distribution_manager
from blogsai.gui.api_key_dialog import APIKeySetupDialog


class FirstTimeSetupDialog(QDialog):
    """Dialog for first-time setup in production builds."""

    def __init__(self, parent=None, setup_check_results=None):
        super().__init__(parent)
        self.dist_manager = get_distribution_manager()
        self.config_dir = None
        self.data_dir = None
        self.api_key = None
        self.setup_check_results = setup_check_results or {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("BlogsAI - First Time Setup")
        self.setFixedSize(600, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("Welcome to BlogsAI")
        header_label.setFont(QFont("Arial", 18, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        subtitle_label = QLabel(
            "Please configure the following settings to get started:"
        )
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)

        # Show setup check results if available
        if self.setup_check_results:
            self.add_setup_status_info(layout)

        layout.addSpacing(20)

        # Step 1: Config Directory
        self.create_config_section(layout)

        # Step 2: Data Directory
        self.create_data_section(layout)

        # Step 3: OpenAI API Key
        self.create_api_key_section(layout)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.finish_btn = QPushButton("Complete Setup")
        self.finish_btn.clicked.connect(self.complete_setup)
        self.finish_btn.setEnabled(True)  # Disabled until all fields are filled
        button_layout.addWidget(self.finish_btn)

        layout.addLayout(button_layout)

        # Initialize with current values
        self.update_current_values()

    def create_config_section(self, layout):
        """Create the config directory section."""
        config_group = QGroupBox("1. Configuration Directory")
        config_layout = QVBoxLayout(config_group)

        info_label = QLabel(
            "This directory will store application settings and prompts."
        )
        config_layout.addWidget(info_label)

        path_layout = QHBoxLayout()
        self.config_path_input = QLineEdit()
        self.config_path_input.setReadOnly(True)
        self.config_path_input.textChanged.connect(self.validate_inputs)
        path_layout.addWidget(self.config_path_input)

        config_browse_btn = QPushButton("Browse...")
        config_browse_btn.clicked.connect(self.browse_config_directory)
        path_layout.addWidget(config_browse_btn)

        config_layout.addLayout(path_layout)

        default_btn = QPushButton("Use Default Location")
        default_btn.clicked.connect(self.use_default_config)
        config_layout.addWidget(default_btn)

        layout.addWidget(config_group)

    def create_data_section(self, layout):
        """Create the data directory section."""
        data_group = QGroupBox("2. Data Directory (Reports)")
        data_layout = QVBoxLayout(data_group)

        info_label = QLabel(
            "This directory will store generated reports and the database."
        )
        data_layout.addWidget(info_label)

        path_layout = QHBoxLayout()
        self.data_path_input = QLineEdit()
        self.data_path_input.setReadOnly(True)
        self.data_path_input.textChanged.connect(self.validate_inputs)
        path_layout.addWidget(self.data_path_input)

        data_browse_btn = QPushButton("Browse...")
        data_browse_btn.clicked.connect(self.browse_data_directory)
        path_layout.addWidget(data_browse_btn)

        data_layout.addLayout(path_layout)

        default_btn = QPushButton("Use Default Location")
        default_btn.clicked.connect(self.use_default_data)
        data_layout.addWidget(default_btn)

        layout.addWidget(data_group)

    def create_api_key_section(self, layout):
        """Create the API key section."""
        api_group = QGroupBox("3. OpenAI API Key")
        api_layout = QVBoxLayout(api_group)

        info_label = QLabel(
            "Your OpenAI API key is required for AI analysis functionality."
        )
        api_layout.addWidget(info_label)

        button_layout = QHBoxLayout()
        self.api_key_status = QLabel("Not configured")
        self.api_key_status.setStyleSheet("color: red;")
        button_layout.addWidget(self.api_key_status)

        button_layout.addStretch()

        api_key_btn = QPushButton("Configure API Key")
        api_key_btn.clicked.connect(self.configure_api_key)
        button_layout.addWidget(api_key_btn)

        api_layout.addLayout(button_layout)

        layout.addWidget(api_group)

    def add_setup_status_info(self, layout):
        """Add setup status information to the dialog."""
        status_group = QGroupBox("Setup Status")
        status_layout = QVBoxLayout(status_group)

        status_text = QTextEdit()
        status_text.setReadOnly(True)
        status_text.setMaximumHeight(200)
        status_text.setStyleSheet("QTextEdit { background-color: #f5f5f5; }")

        # Build status text with better formatting
        status_lines = []
        failed_count = 0

        for check_name, result in self.setup_check_results.items():
            if isinstance(result, dict) and "status" in result:
                status = "OK" if result["status"] else "NEEDS ATTENTION"
                if not result["status"]:
                    failed_count += 1

                check_display = check_name.replace("_", " ").title()

                # Truncate very long messages for better display
                message = result["message"]
                if len(message) > 120:
                    # Find a good break point
                    if ": " in message:
                        parts = message.split(": ", 1)
                        if len(parts[0]) < 60:
                            message = f"{parts[0]}:\n    {parts[1]}"

                status_lines.append(f"{status} {check_display}: {message}")

        # Add summary at the top
        total_checks = len(
            [
                r
                for r in self.setup_check_results.values()
                if isinstance(r, dict) and "status" in r
            ]
        )
        passed_checks = total_checks - failed_count

        if failed_count == 0:
            summary = f"All {total_checks} setup checks passed!"
        else:
            summary = f"{failed_count} of {total_checks} checks need attention:"

        final_text = f"{summary}\n\n" + "\n\n".join(status_lines)
        status_text.setPlainText(final_text)
        status_layout.addWidget(status_text)

        layout.addWidget(status_group)

    def update_current_values(self):
        """Update inputs with current values."""
        # Set default config directory
        config_dir = self.dist_manager.get_config_directory()
        self.config_path_input.setText(str(config_dir))
        self.config_dir = config_dir

        # Set default data directory
        data_dir = self.dist_manager.get_data_directory()
        self.data_path_input.setText(str(data_dir))
        self.data_dir = data_dir

        # Check for existing API key
        self.check_existing_api_key()

    def browse_config_directory(self):
        """Browse for config directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Configuration Directory", str(self.config_path_input.text())
        )
        if directory:
            self.config_path_input.setText(directory)
            self.config_dir = Path(directory)

    def browse_data_directory(self):
        """Browse for data directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Data Directory", str(self.data_path_input.text())
        )
        if directory:
            self.data_path_input.setText(directory)
            self.data_dir = Path(directory)

    def use_default_config(self):
        """Use the default config directory."""
        default_dir = self.dist_manager.get_config_directory()
        self.config_path_input.setText(str(default_dir))
        self.config_dir = default_dir

    def use_default_data(self):
        """Use the default data directory."""
        default_dir = self.dist_manager.get_data_directory()
        self.data_path_input.setText(str(default_dir))
        self.data_dir = default_dir

    def configure_api_key(self):
        """Open API key configuration dialog."""
        dialog = APIKeySetupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.api_key = dialog.get_api_key()
            self.api_key_status.setText("Configured")
            self.api_key_status.setStyleSheet("color: green;")
            self.validate_inputs()

    def check_existing_api_key(self):
        """Check if API key already exists."""
        try:
            from blogsai.config.credential_manager import CredentialManager

            cred_manager = CredentialManager()
            api_key = cred_manager.get_api_key()
            if api_key and api_key != "MISSING_API_KEY":
                self.api_key = "existing"
                self.api_key_status.setText("Already configured")
                self.api_key_status.setStyleSheet("color: green;")
        except Exception as e:
            print(f"Error checking existing API key: {e}")
            pass

    def validate_inputs(self):
        """Validate all inputs and enable/disable finish button."""
        config_valid = bool(self.config_dir and Path(self.config_dir).exists())
        data_valid = bool(self.data_dir is not None)
        api_key_valid = bool(self.api_key is not None)

        all_valid = config_valid and data_valid and api_key_valid
        self.finish_btn.setEnabled(all_valid)

    def complete_setup(self):
        """Complete the setup process."""
        try:
            # Create directories if they don't exist
            os.makedirs(self.config_dir, exist_ok=True)
            os.makedirs(self.data_dir, exist_ok=True)

            # Update distribution manager paths if needed
            # This will be handled by the main application

            # Store the selected paths for retrieval
            self.selected_config_dir = self.config_dir
            self.selected_data_dir = self.data_dir

            QMessageBox.information(
                self,
                "Setup Complete",
                "BlogsAI has been configured successfully!\n\n"
                f"Configuration: {self.config_dir}\n"
                f"Data: {self.data_dir}\n"
                f"API Key: {'Configured' if self.api_key else 'Not configured'}",
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self, "Setup Error", f"Failed to complete setup:\n{str(e)}"
            )

    def get_setup_results(self):
        """Get the setup results."""
        return {
            "config_dir": self.selected_config_dir,
            "data_dir": self.selected_data_dir,
            "api_key_configured": self.api_key is not None,
        }
