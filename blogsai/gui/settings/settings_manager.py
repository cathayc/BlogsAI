"""Settings management for the application."""

import os
import sys
import yaml
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QTextEdit,
    QHeaderView,
    QMessageBox,
    QCheckBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.config.distribution import get_distribution_manager


class SettingsManager:
    """Manages application settings and configuration."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.dist_manager = get_distribution_manager()
        self.setup_settings_widgets()

    def setup_settings_widgets(self):
        """Set up settings-related widgets."""
        # These will be populated by the create methods
        self.openai_key_input = None
        self.openai_model_input = None
        self.openai_research_model_input = None
        self.openai_tokens_input = None
        self.openai_temp_input = None
        self.max_articles_input = None
        self.delay_input = None
        self.retries_input = None
        self.timeout_input = None
        self.sources_table = None
        self.prompt_selector = None
        self.prompt_editor = None
        self.report_location_input = None

    def create_app_settings_tab(self):
        """Create the application settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # OpenAI Settings
        openai_group = QGroupBox("OpenAI Configuration")
        openai_layout = QGridLayout(openai_group)

        openai_layout.addWidget(QLabel("API Key:"), 0, 0)
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.Password)
        self.openai_key_input.setPlaceholderText("Enter OpenAI API Key")
        openai_layout.addWidget(self.openai_key_input, 0, 1)

        openai_layout.addWidget(QLabel("Analysis Model:"), 1, 0)
        self.openai_model_input = QLineEdit()
        openai_layout.addWidget(self.openai_model_input, 1, 1)

        openai_layout.addWidget(QLabel("Research Model:"), 2, 0)
        self.openai_research_model_input = QLineEdit()
        self.openai_research_model_input.setPlaceholderText(
            "Model for market intelligence (e.g., o3)"
        )
        openai_layout.addWidget(self.openai_research_model_input, 2, 1)

        openai_layout.addWidget(QLabel("Max Tokens:"), 3, 0)
        self.openai_tokens_input = QLineEdit()
        openai_layout.addWidget(self.openai_tokens_input, 3, 1)

        openai_layout.addWidget(QLabel("Temperature:"), 4, 0)
        self.openai_temp_input = QLineEdit()
        openai_layout.addWidget(self.openai_temp_input, 4, 1)

        layout.addWidget(openai_group)

        # Analysis Settings
        analysis_group = QGroupBox("Analysis Configuration")
        analysis_layout = QGridLayout(analysis_group)

        analysis_layout.addWidget(QLabel("Max Articles per Report:"), 0, 0)
        self.max_articles_input = QLineEdit()
        analysis_layout.addWidget(self.max_articles_input, 0, 1)

        layout.addWidget(analysis_group)

        # Scraping Settings
        scraping_group = QGroupBox("Scraping Configuration")
        scraping_layout = QGridLayout(scraping_group)

        scraping_layout.addWidget(QLabel("Delay Between Requests (seconds):"), 0, 0)
        self.delay_input = QLineEdit()
        scraping_layout.addWidget(self.delay_input, 0, 1)

        scraping_layout.addWidget(QLabel("Max Retries:"), 1, 0)
        self.retries_input = QLineEdit()
        scraping_layout.addWidget(self.retries_input, 1, 1)

        scraping_layout.addWidget(QLabel("Timeout (seconds):"), 2, 0)
        self.timeout_input = QLineEdit()
        scraping_layout.addWidget(self.timeout_input, 2, 1)

        layout.addWidget(scraping_group)

        # Report Location Settings
        location_group = self.create_report_location_section()
        layout.addWidget(location_group)

        layout.addStretch()
        return tab

    def create_report_location_section(self):
        """Create the report location settings section."""
        location_group = QGroupBox("Report Location")
        location_layout = QVBoxLayout(location_group)

        # Report location input field
        location_input_layout = QHBoxLayout()
        location_input_layout.addWidget(QLabel("Reports Directory:"))

        self.report_location_input = QLineEdit()
        self.report_location_input.setPlaceholderText("Path to reports directory...")
        location_input_layout.addWidget(self.report_location_input)

        # Browse button for selecting directory
        browse_location_btn = QPushButton("Browse...")
        browse_location_btn.clicked.connect(self.browse_report_location)
        location_input_layout.addWidget(browse_location_btn)

        location_layout.addLayout(location_input_layout)

        # Info label
        info_label = QLabel(
            "This is where generated intelligence reports will be saved."
        )
        info_label.setStyleSheet("color: #666; font-style: italic; margin-top: 5px;")
        location_layout.addWidget(info_label)

        return location_group

    def create_source_settings_tab(self):
        """Create the source settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Sources table
        sources_group = QGroupBox("Government Agency Sources")
        sources_layout = QVBoxLayout(sources_group)

        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(4)
        self.sources_table.setHorizontalHeaderLabels(
            ["Name", "Base URL", "Press Releases URL", "Enabled"]
        )

        # Make table stretch to fill space
        header = self.sources_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Base URL
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Press URL
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Enabled

        sources_layout.addWidget(self.sources_table)
        layout.addWidget(sources_group)

        layout.addStretch()
        return tab

    def create_prompts_tab(self):
        """Create the prompts management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Prompts selection and editing
        prompts_group = QGroupBox("AI Prompts Management")
        prompts_layout = QVBoxLayout(prompts_group)

        # Prompt selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Prompt:"))

        self.prompt_selector = QComboBox()
        self.prompt_selector.addItems(
            [
                "article_analysis.txt",
                "article_parser.txt",
                "citation_corrector.txt",
                "citation_verifier.txt",
                "insight_analysis.txt",
                "relevance_scorer.txt",
            ]
        )
        self.prompt_selector.currentTextChanged.connect(self.load_selected_prompt)
        selector_layout.addWidget(self.prompt_selector)

        selector_layout.addStretch()
        prompts_layout.addLayout(selector_layout)

        # Load the first prompt by default
        if self.prompt_selector.count() > 0:
            self.load_selected_prompt(self.prompt_selector.currentText())

        # Prompt editor
        editor_label = QLabel("Prompt Content:")
        editor_label.setFont(QFont("Arial", 10, QFont.Bold))
        prompts_layout.addWidget(editor_label)

        self.prompt_editor = QTextEdit()
        self.prompt_editor.setFont(QFont("Courier", 10))
        self.prompt_editor.setMinimumHeight(300)
        prompts_layout.addWidget(self.prompt_editor)

        # Save prompt button
        save_prompt_btn = QPushButton("Save This Prompt")
        save_prompt_btn.clicked.connect(self.save_selected_prompt)
        prompts_layout.addWidget(save_prompt_btn)

        layout.addWidget(prompts_group)

        layout.addStretch()
        return tab

    def load_settings(self):
        """Load settings from configuration files."""
        try:
            # Load application settings using distribution manager
            settings_path = self.dist_manager.get_settings_path()

            # Ensure the config directory exists
            settings_path.parent.mkdir(parents=True, exist_ok=True)

            if settings_path.exists():
                with open(settings_path, "r") as f:
                    settings = yaml.safe_load(f)

                # Populate OpenAI settings
                openai_config = settings.get("openai", {})
                if self.openai_key_input:
                    # Load API key from credential manager, not from settings
                    from blogsai.config.credential_manager import CredentialManager

                    credential_manager = CredentialManager()
                    api_key = credential_manager.get_api_key() or ""
                    self.openai_key_input.setText(api_key)
                if self.openai_model_input:
                    self.openai_model_input.setText(openai_config.get("model", ""))
                if self.openai_research_model_input:
                    self.openai_research_model_input.setText(
                        openai_config.get("research_model", "")
                    )
                if self.openai_tokens_input:
                    self.openai_tokens_input.setText(
                        str(openai_config.get("max_tokens", ""))
                    )
                if self.openai_temp_input:
                    self.openai_temp_input.setText(
                        str(openai_config.get("temperature", ""))
                    )

                # Populate analysis settings
                analysis_config = settings.get("analysis", {})
                if self.max_articles_input:
                    self.max_articles_input.setText(
                        str(analysis_config.get("max_articles_per_report", ""))
                    )

                # Populate scraping settings
                scraping_config = settings.get("scraping", {})
                if self.delay_input:
                    self.delay_input.setText(
                        str(scraping_config.get("delay_between_requests", ""))
                    )
                if self.retries_input:
                    self.retries_input.setText(
                        str(scraping_config.get("max_retries", ""))
                    )
                if self.timeout_input:
                    self.timeout_input.setText(str(scraping_config.get("timeout", "")))

            # Load sources.yaml using distribution manager
            sources_path = self.dist_manager.get_sources_path()

            if sources_path.exists():
                with open(sources_path, "r") as f:
                    sources_data = yaml.safe_load(f)
                    self.load_sources_table(sources_data)

            # Load first prompt
            if self.prompt_selector:
                self.load_selected_prompt(self.prompt_selector.currentText())

            # Load current report location using ConfigManager (distribution-aware)
            if hasattr(self, "report_location_input") and self.report_location_input:
                # Use ConfigManager to get the correct reports directory (distribution-aware)
                from blogsai.config.config import ConfigManager

                config_manager = ConfigManager()
                config = config_manager.load_config()
                report_dir = config.reporting.output_dir
                self.report_location_input.setText(report_dir)

        except Exception as e:
            print(f"Error loading settings: {e}")

    def load_sources_table(self, sources_data):
        """Load sources data into the table."""
        if not self.sources_table:
            return

        agencies = sources_data.get("sources", {}).get("agencies", {})

        self.sources_table.setRowCount(len(agencies))

        for i, (key, source) in enumerate(agencies.items()):
            self.sources_table.setItem(i, 0, QTableWidgetItem(source.get("name", "")))
            self.sources_table.setItem(
                i, 1, QTableWidgetItem(source.get("base_url", ""))
            )
            self.sources_table.setItem(
                i, 2, QTableWidgetItem(source.get("press_releases_url", ""))
            )

            # Enabled checkbox
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            enabled_item.setCheckState(
                Qt.Checked if source.get("enabled", False) else Qt.Unchecked
            )
            self.sources_table.setItem(i, 3, enabled_item)

    def load_selected_prompt(self, prompt_filename):
        """Load the selected prompt file."""
        if not self.prompt_editor:
            return

        try:
            # Use distribution manager to get proper prompts directory
            prompts_dir = self.dist_manager.get_prompts_directory()
            prompt_path = prompts_dir / prompt_filename

            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.prompt_editor.setPlainText(content)
            else:
                self.prompt_editor.setPlainText(
                    f"Prompt file not found: {prompt_filename}\nLooked in: {prompts_dir}"
                )
        except Exception as e:
            self.prompt_editor.setPlainText(f"Error loading prompt: {str(e)}")

    def save_selected_prompt(self):
        """Save the currently selected prompt."""
        if not self.prompt_editor or not self.prompt_selector:
            return

        try:
            prompt_filename = self.prompt_selector.currentText()
            # Use distribution manager to get proper prompts directory
            prompts_dir = self.dist_manager.get_prompts_directory()
            prompt_path = prompts_dir / prompt_filename

            # Ensure the prompts directory exists
            prompts_dir.mkdir(parents=True, exist_ok=True)

            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(self.prompt_editor.toPlainText())

            QMessageBox.information(
                self.main_window,
                "Success",
                f"Prompt saved: {prompt_filename}\nSaved to: {prompt_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Failed to save prompt:\n{str(e)}"
            )

    def save_all_settings(self):
        """Save all settings to configuration files."""
        try:
            # Update settings.yaml using distribution manager
            settings_path = self.dist_manager.get_settings_path()

            # Ensure the config directory exists
            settings_path.parent.mkdir(parents=True, exist_ok=True)

            settings = {}

            if settings_path.exists():
                with open(settings_path, "r") as f:
                    settings = yaml.safe_load(f)

            # Update OpenAI settings (excluding API key - handled by credential manager)
            if self.openai_key_input:
                # Save API key via credential manager, not in settings.yaml
                openai_key = self.openai_key_input.text().strip()
                if openai_key:
                    from blogsai.config.credential_manager import CredentialManager

                    credential_manager = CredentialManager()
                    credential_manager.save_api_key(openai_key)

                settings["openai"] = {
                    # Note: API key is managed separately via credential system
                    "model": (
                        self.openai_model_input.text().strip()
                        if self.openai_model_input
                        else ""
                    ),
                    "research_model": (
                        self.openai_research_model_input.text().strip()
                        if self.openai_research_model_input
                        else "o3"
                    ),
                    "max_tokens": (
                        int(self.openai_tokens_input.text())
                        if self.openai_tokens_input and self.openai_tokens_input.text()
                        else 4000
                    ),
                    "temperature": (
                        float(self.openai_temp_input.text())
                        if self.openai_temp_input and self.openai_temp_input.text()
                        else 0.3
                    ),
                }

            # Handle report location change
            if hasattr(self, "report_location_input") and self.report_location_input:
                new_location = self.report_location_input.text().strip()
                current_location = str(self.dist_manager.get_reports_directory())

                if new_location and new_location != current_location:
                    self.handle_report_location_change(new_location)

            # Update reporting settings with new location
            if hasattr(self, "report_location_input") and self.report_location_input:
                settings["reporting"] = settings.get("reporting", {})
                settings["reporting"][
                    "output_dir"
                ] = self.report_location_input.text().strip() or str(
                    self.dist_manager.get_reports_directory()
                )

            # Update analysis settings
            settings["analysis"] = settings.get("analysis", {})
            if self.max_articles_input:
                settings["analysis"]["max_articles_per_report"] = (
                    int(self.max_articles_input.text())
                    if self.max_articles_input.text()
                    else 50
                )

            # Update scraping settings
            if self.delay_input and self.retries_input and self.timeout_input:
                settings["scraping"] = {
                    "delay_between_requests": (
                        int(self.delay_input.text()) if self.delay_input.text() else 1
                    ),
                    "max_retries": (
                        int(self.retries_input.text())
                        if self.retries_input.text()
                        else 3
                    ),
                    "timeout": (
                        int(self.timeout_input.text())
                        if self.timeout_input.text()
                        else 30
                    ),
                    "user_agent": settings.get("scraping", {}).get(
                        "user_agent", "BlogsAI/1.0 (News Analysis Bot)"
                    ),
                }

            # Save settings.yaml
            with open(settings_path, "w") as f:
                yaml.dump(settings, f, default_flow_style=False, indent=2)

            # Update sources.yaml
            self.save_sources()

            QMessageBox.information(
                self.main_window, "Success", "All settings saved successfully!"
            )

        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Failed to save settings:\n{str(e)}"
            )

    def save_sources(self):
        """Save sources configuration."""
        if not self.sources_table:
            return

        # Use distribution manager for sources path
        sources_path = self.dist_manager.get_sources_path()

        # Ensure the config directory exists
        sources_path.parent.mkdir(parents=True, exist_ok=True)
        sources_data = {"sources": {"agencies": {}}}

        # Get current sources from table
        for i in range(self.sources_table.rowCount()):
            name_item = self.sources_table.item(i, 0)
            base_url_item = self.sources_table.item(i, 1)
            press_url_item = self.sources_table.item(i, 2)
            enabled_item = self.sources_table.item(i, 3)

            if name_item and base_url_item:
                # Create key from name (lowercase, remove spaces)
                key = name_item.text().lower().replace(" ", "").replace(".", "")
                if "justice" in key:
                    key = "doj"
                elif "securities" in key:
                    key = "sec"
                elif "commodity" in key:
                    key = "cftc"

                sources_data["sources"]["agencies"][key] = {
                    "name": name_item.text(),
                    "base_url": base_url_item.text(),
                    "press_releases_url": (
                        press_url_item.text() if press_url_item else ""
                    ),
                    "scraper_type": "government",
                    "enabled": (
                        enabled_item.checkState() == Qt.Checked
                        if enabled_item
                        else True
                    ),
                }

        # Save sources.yaml
        with open(sources_path, "w") as f:
            yaml.dump(sources_data, f, default_flow_style=False, indent=2)

    def browse_report_location(self):
        """Browse for a new data directory location."""
        from PyQt5.QtWidgets import QFileDialog

        # Get current location as starting point
        current_dir = self.report_location_input.text() or str(
            self.dist_manager.get_reports_directory()
        )

        # Ask user to select new directory
        new_folder = QFileDialog.getExistingDirectory(
            self.main_window,
            "Choose Reports Directory",
            current_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )

        if new_folder:
            self.report_location_input.setText(new_folder)

    def handle_report_location_change(self, new_location):
        """Handle report location change by moving existing reports to the new location."""
        try:
            current_location = self.dist_manager.get_reports_directory()

            # Confirm the change
            reply = QMessageBox.question(
                self.main_window,
                "Confirm Report Move",
                f"This will move all your existing reports from:\n{current_location}\n\n"
                f"To:\n{new_location}\n\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                import shutil

                new_path = Path(new_location)

                # Ensure the new directory exists
                new_path.mkdir(parents=True, exist_ok=True)

                # Move existing reports if the current directory exists and is different
                if current_location.exists() and current_location != new_path:
                    for report_file in current_location.glob("*"):
                        if report_file.is_file():
                            shutil.move(
                                str(report_file), str(new_path / report_file.name)
                            )

                # Update the settings.yaml file with the new report location
                settings_path = self.dist_manager.get_settings_path()
                settings = {}

                if settings_path.exists():
                    with open(settings_path, "r") as f:
                        settings = yaml.safe_load(f) or {}

                # Update the reporting output directory
                if "reporting" not in settings:
                    settings["reporting"] = {}
                settings["reporting"]["output_dir"] = str(new_location)

                # Save the updated settings
                with open(settings_path, "w") as f:
                    yaml.dump(settings, f, default_flow_style=False, indent=2)

                QMessageBox.information(
                    self.main_window,
                    "Success",
                    f"Reports successfully moved to:\n{new_location}\n\n"
                    f"Future reports will be saved to this location.",
                )

                # Update the input field to reflect the current state
                self.report_location_input.setText(new_location)

        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to change report location:\n{str(e)}",
            )
            # Revert the input field to the current location
            self.report_location_input.setText(
                str(self.dist_manager.get_reports_directory())
            )
