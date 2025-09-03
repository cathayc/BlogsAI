"""Configuration management for BlogsAI."""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .env_manager import EnvironmentManager
from .distribution import get_distribution_manager
from .credential_manager import CredentialManager


class ScrapingConfig(BaseModel):
    """Scraping configuration."""

    delay_between_requests: int = 1
    max_retries: int = 3
    timeout: int = 30
    user_agent: str = "BlogsAI/1.0"


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "sqlite:///data/blogsai.db"  # Will be updated by distribution manager
    echo: bool = False


class OpenAIConfig(BaseModel):
    """OpenAI configuration."""

    # Note: API key is managed separately via credential system
    model: str = "gpt-4o"
    research_model: str = (
        "gpt-4o"  # Model for market intelligence research with web search
    )
    max_tokens: int = 4000
    temperature: float = 0.3


class ReportingConfig(BaseModel):
    """Reporting configuration."""

    output_dir: str = "data/reports"  # Will be updated by distribution manager
    formats: List[str] = ["html", "json", "markdown"]
    include_source_links: bool = True


class SchedulingConfig(BaseModel):
    """Scheduling configuration."""

    daily_time: str = "09:00"
    timezone: str = "UTC"


class AnalysisConfig(BaseModel):
    """Analysis configuration."""

    max_articles_per_report: int = 50
    lookback_days: Dict[str, int] = {"daily": 1}


class SourceConfig(BaseModel):
    """Individual source configuration."""

    name: str
    base_url: str
    scraper_type: str
    enabled: bool = True
    press_releases_url: str = None
    rss_feeds: List[str] = None


class Config(BaseModel):
    """Main configuration class."""

    database: DatabaseConfig
    openai: OpenAIConfig
    reporting: ReportingConfig
    scheduling: SchedulingConfig
    analysis: AnalysisConfig
    scraping: ScrapingConfig
    sources: Dict[str, Dict[str, SourceConfig]]


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_dir: str = None):
        # Use distribution manager for paths
        self.dist_manager = get_distribution_manager()

        # Use distribution-aware config directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = self.dist_manager.get_config_directory()

        self._config: Config = None

        # Set up secure credential manager
        self.credential_manager = CredentialManager(str(self.config_dir))

        # Set up environment manager with distribution-aware data directory
        data_dir = str(self.dist_manager.get_data_directory())
        self.env_manager = EnvironmentManager(data_dir)
        self.env_manager.load_env_files()

        # Set up user environment if needed
        self.env_manager.setup_user_env()

        # Migrate any existing environment variables to secure storage
        self._migrate_credentials()

    def _get_config_dir(self, config_dir: str) -> Path:
        """Get the config directory, handling PyInstaller bundle structure."""
        # Check if environment variable for config directory is set
        env_config_dir = os.getenv("BLOGSAI_CONFIG_DIR")
        if env_config_dir:
            return Path(env_config_dir)

        if hasattr(sys, "_MEIPASS"):
            # Running as PyInstaller bundle - config files are in _internal
            return Path(sys._MEIPASS) / config_dir
        else:
            # Running from source
            return Path(config_dir)

    def load_config(self) -> Config:
        """Load configuration from YAML files."""
        if self._config is not None:
            return self._config

        # Use distribution manager paths
        settings_file = self.dist_manager.get_settings_path()
        sources_file = self.dist_manager.get_sources_path()

        # Create default config files if they don't exist
        self._ensure_config_files(settings_file, sources_file)

        # Load main settings
        with open(settings_file, "r") as f:
            settings_data = yaml.safe_load(f)

        # Load sources
        with open(sources_file, "r") as f:
            sources_data = yaml.safe_load(f)

        # Combine configurations
        config_data = {**settings_data, "sources": sources_data["sources"]}

        # Expand environment variables
        config_data = self._expand_env_vars(config_data)

        # Update paths using distribution manager
        config_data["database"][
            "url"
        ] = f"sqlite:///{self.dist_manager.get_database_path()}"
        config_data["reporting"]["output_dir"] = str(
            self.dist_manager.get_reports_directory()
        )

        # Parse sources into SourceConfig objects
        parsed_sources = {}
        for category, sources in config_data["sources"].items():
            parsed_sources[category] = {}
            for source_id, source_data in sources.items():
                parsed_sources[category][source_id] = SourceConfig(**source_data)

        config_data["sources"] = parsed_sources

        self._config = Config(**config_data)
        return self._config

    def _expand_env_vars(self, data: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(data, dict):
            return {k: self._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]
        elif isinstance(data, str):
            if data.startswith("${") and data.endswith("}"):
                env_var = data[2:-1]

                # Special handling for OpenAI API key
                if env_var == "OPENAI_API_KEY":
                    # Try secure storage first
                    api_key = self.credential_manager.get_api_key()
                    if api_key and api_key != "MISSING_API_KEY":
                        return api_key

                    # Fallback to environment manager
                    api_key = self.env_manager.get_openai_api_key()
                    if api_key:
                        return api_key
                    else:
                        # Return placeholder to indicate missing key
                        return "MISSING_API_KEY"

                return os.getenv(env_var, data)
        return data

    def get_all_sources(self) -> List[SourceConfig]:
        """Get all enabled sources across all categories."""
        config = self.load_config()
        sources = []
        for category in config.sources.values():
            for source in category.values():
                if source.enabled:
                    sources.append(source)
        return sources

    def get_sources_by_category(self, category: str) -> Dict[str, SourceConfig]:
        """Get sources by category (agencies or news)."""
        config = self.load_config()
        return config.sources.get(category, {})

    def _migrate_credentials(self) -> None:
        """Migrate credentials from environment variables to secure storage."""
        # SECURITY: Only migrate in development mode to prevent accidentally
        # distributing API keys in production builds
        if not self.dist_manager.is_development:
            return

        try:
            # Migrate OpenAI API key (development only)
            if self.credential_manager.migrate_from_env(
                "OPENAI_API_KEY", "openai", "api_key"
            ):
                print("Migrated OpenAI API key to secure storage")
        except Exception as e:
            print(f"Warning: Failed to migrate credentials: {e}")

    def _ensure_config_files(self, settings_file: Path, sources_file: Path) -> None:
        """Ensure configuration files exist, creating defaults if needed."""
        # Create settings.yaml if it doesn't exist
        if not settings_file.exists():
            default_settings = {
                "database": {"url": "sqlite:///data/blogsai.db", "echo": False},
                "openai": {
                    "model": "gpt-4o",
                    "research_model": "gpt-4o",
                    "max_tokens": 4000,
                    "temperature": 0.3,
                },
                "reporting": {
                    "output_dir": "data/reports",
                    "formats": ["html", "json", "markdown"],
                    "include_source_links": True,
                },
                "scheduling": {"daily_time": "09:00", "timezone": "UTC"},
                "analysis": {
                    "max_articles_per_report": 50,
                    "lookback_days": {"daily": 1},
                },
                "scraping": {
                    "delay_between_requests": 1,
                    "max_retries": 3,
                    "timeout": 30,
                    "user_agent": "BlogsAI/1.0",
                },
            }

            settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_file, "w") as f:
                yaml.dump(default_settings, f, default_flow_style=False, indent=2)

        # Create sources.yaml if it doesn't exist
        if not sources_file.exists():
            default_sources = {
                "sources": {
                    "agencies": {
                        "doj": {
                            "name": "Department of Justice",
                            "base_url": "https://www.justice.gov",
                            "scraper_type": "government",
                            "enabled": True,
                            "press_releases_url": "https://www.justice.gov/news",
                        },
                        "sec": {
                            "name": "Securities and Exchange Commission",
                            "base_url": "https://www.sec.gov",
                            "scraper_type": "government",
                            "enabled": True,
                            "press_releases_url": "https://www.sec.gov/news/pressreleases",
                        },
                        "cftc": {
                            "name": "Commodity Futures Trading Commission",
                            "base_url": "https://www.cftc.gov",
                            "scraper_type": "government",
                            "enabled": True,
                            "press_releases_url": "https://www.cftc.gov/PressRoom/PressReleases",
                        },
                    }
                }
            }

            sources_file.parent.mkdir(parents=True, exist_ok=True)
            with open(sources_file, "w") as f:
                yaml.dump(default_sources, f, default_flow_style=False, indent=2)

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from secure storage."""
        return self.credential_manager.get_api_key()

    def set_openai_api_key(self, api_key: str) -> bool:
        """Store OpenAI API key in secure storage."""
        success, _ = self.credential_manager.save_api_key(api_key)
        return success

    def get_distribution_info(self) -> dict:
        """Get distribution information."""
        return self.dist_manager.get_distribution_info()

    def enable_portable_mode(self) -> None:
        """Enable portable mode."""
        self.dist_manager.create_portable_marker()
        # Reload configuration with new paths
        self._config = None

    def disable_portable_mode(self) -> None:
        """Disable portable mode."""
        self.dist_manager.remove_portable_marker()
        # Reload configuration with new paths
        self._config = None
