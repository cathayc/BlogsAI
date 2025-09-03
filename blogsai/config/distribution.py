"""
Distribution and platform-specific configuration management.
Inspired by Calibre's approach to handling cross-platform deployment.
"""

import os
import sys
from pathlib import Path
from typing import Optional
import logging
import platformdirs

logger = logging.getLogger(__name__)

# Import the enhanced directory manager and error dialogs
try:
    from ..utils.directory_manager import create_secure_directories

    HAS_DIRECTORY_MANAGER = True
except ImportError:
    logger.warning("Enhanced directory manager not available, using fallback")
    HAS_DIRECTORY_MANAGER = False

try:
    from ..utils.error_dialogs import show_directory_error, show_startup_error

    HAS_ERROR_DIALOGS = True
except ImportError:
    logger.warning("Error dialogs not available")
    HAS_ERROR_DIALOGS = False


class DistributionManager:
    """Manages platform-specific paths and distribution modes."""

    def __init__(self):
        self._data_dir = None
        self._config_dir = None
        self._cache_dir = None
        self._logs_dir = None
        self._is_portable = None
        self._directories_initialized = False
        self._directories = None

        # Use centralized AppDirectories for path management
        from .app_dirs import AppDirectories

        self._app_dirs = AppDirectories()

    @property
    def is_portable(self) -> bool:
        """Check if running in portable mode."""
        if self._is_portable is None:
            # Check for portable mode indicators
            self._is_portable = (
                os.getenv("BLOGSAI_PORTABLE", "").lower() in ("1", "true", "yes")
                or (Path(__file__).parent.parent.parent / "PORTABLE").exists()
                or (Path(sys.executable).parent / "PORTABLE").exists()
            )
        return self._is_portable

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return (
            os.getenv("BLOGSAI_DEV", "").lower() in ("1", "true", "yes")
            or "pytest" in sys.modules
            or os.path.exists(Path(__file__).parent.parent.parent / ".git")
        )

    def get_data_directory(self) -> Path:
        """Get platform-appropriate data directory."""
        if self._data_dir is None:
            # Try enhanced directory manager first
            if self.initialize_directories_enhanced():
                return self._data_dir

            # Use centralized AppDirectories for path management
            self._data_dir = self._app_dirs.app_data_dir

            # Ensure directory exists with error handling
            try:
                self._data_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Data directory: {self._data_dir}")
            except (PermissionError, OSError) as e:
                logger.warning(f"Failed to create data directory {self._data_dir}: {e}")
                # Fallback to user-accessible directory
                fallback_dir = Path.home() / ".blogsai" / "data"
                try:
                    fallback_dir.mkdir(parents=True, exist_ok=True)
                    self._data_dir = fallback_dir
                    logger.info(f"Using fallback data directory: {self._data_dir}")
                except (PermissionError, OSError) as fallback_error:
                    logger.error(
                        f"Failed to create fallback directory {fallback_dir}: {fallback_error}"
                    )

                    # Show error dialog
                    if HAS_ERROR_DIALOGS:
                        show_directory_error(
                            directory_type="Data",
                            primary_path=self._data_dir,
                            fallback_path=fallback_dir,
                            error=e,
                        )

                    raise RuntimeError(f"Cannot create data directory: {e}") from e

        return self._data_dir

    def get_config_directory(self) -> Path:
        """Get platform-appropriate configuration directory."""
        return self._app_dirs.app_config_dir

    def get_cache_directory(self) -> Path:
        """Get platform-appropriate cache directory."""
        return self._app_dirs.app_cache_dir

    def get_logs_directory(self) -> Path:
        """Get platform-appropriate logs directory."""
        return self._app_dirs.app_logs_dir

    def get_database_path(self) -> Path:
        """Get the main database file path."""
        return self._app_dirs.database_path

    def get_settings_path(self) -> Path:
        """Get the settings file path."""
        return self._app_dirs.user_config_file

    def get_sources_path(self) -> Path:
        """Get the sources configuration file path."""
        return self._app_dirs.sources_config_file

    def get_prompts_directory(self) -> Path:
        """Get the prompts directory path."""
        return self._app_dirs.prompts_dir

    def get_reports_directory(self) -> Path:
        """Get the reports output directory path."""
        return self._app_dirs.get_reports_directory()

    def create_portable_marker(self) -> None:
        """Create a portable mode marker file."""
        marker_file = Path(__file__).parent.parent.parent / "PORTABLE"
        marker_file.touch()
        logger.info("Created portable mode marker")
        # Reset cached values
        self._is_portable = None
        self._data_dir = None
        self._config_dir = None
        self._cache_dir = None
        self._logs_dir = None

    def remove_portable_marker(self) -> None:
        """Remove the portable mode marker file."""
        marker_file = Path(__file__).parent.parent.parent / "PORTABLE"
        if marker_file.exists():
            marker_file.unlink()
            logger.info("Removed portable mode marker")
            # Reset cached values
            self._is_portable = None
            self._data_dir = None
            self._config_dir = None
            self._cache_dir = None
            self._logs_dir = None

    def get_distribution_info(self) -> dict:
        """Get information about the current distribution setup."""
        return {
            "mode": (
                "portable"
                if self.is_portable
                else ("development" if self.is_development else "production")
            ),
            "platform": sys.platform,
            "data_directory": str(self.get_data_directory()),
            "config_directory": str(self.get_config_directory()),
            "cache_directory": str(self.get_cache_directory()),
            "logs_directory": str(self.get_logs_directory()),
            "database_path": str(self.get_database_path()),
            "settings_path": str(self.get_settings_path()),
            "sources_path": str(self.get_sources_path()),
            "prompts_directory": str(self.get_prompts_directory()),
            "reports_directory": str(self.get_reports_directory()),
        }

    def initialize_directories_enhanced(self) -> bool:
        """
        Initialize directories using the enhanced directory manager.

        Returns:
            True if successful, False if fallback to legacy method needed
        """
        if not HAS_DIRECTORY_MANAGER or self._directories_initialized:
            return False

        try:
            self._directories = create_secure_directories(
                app_name="BlogsAI",
                app_author="BlogsAI",
                portable_mode=self.is_portable,
                development_mode=self.is_development,
            )

            # Update cached paths
            self._data_dir = self._directories["data"]
            self._config_dir = self._directories["config"]
            self._cache_dir = self._directories["cache"]
            self._logs_dir = self._directories["logs"]

            self._directories_initialized = True
            logger.info("Successfully initialized directories using enhanced manager")
            return True

        except Exception as e:
            logger.warning(f"Enhanced directory initialization failed: {e}")
            return False


# Global instance
_distribution_manager = None


def get_distribution_manager() -> DistributionManager:
    """Get the global distribution manager instance."""
    global _distribution_manager
    if _distribution_manager is None:
        _distribution_manager = DistributionManager()
    return _distribution_manager
