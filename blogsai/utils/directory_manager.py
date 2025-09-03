"""
Enhanced directory management utility for macOS and cross-platform support.
Handles permissions, fallbacks, and provides better error reporting.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import platformdirs

logger = logging.getLogger(__name__)

# Import error dialog utilities
try:
    from .error_dialogs import show_directory_error, show_permission_error

    HAS_ERROR_DIALOGS = True
except ImportError:
    logger.warning("Error dialogs not available")
    HAS_ERROR_DIALOGS = False


class DirectoryManager:
    """Enhanced directory management with fallback strategies."""

    def __init__(self, app_name: str = "BlogsAI", app_author: str = "BlogsAI"):
        self.app_name = app_name
        self.app_author = app_author
        self.created_directories: List[Path] = []

    def create_directory_with_fallback(
        self, primary_path: Path, fallback_name: str
    ) -> Path:
        """
        Create a directory with fallback strategy.

        Args:
            primary_path: Primary directory path to try
            fallback_name: Name for fallback directory in user home

        Returns:
            Path to successfully created directory

        Raises:
            RuntimeError: If both primary and fallback creation fail
        """
        # Try primary path first
        try:
            primary_path.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = primary_path / ".write_test"
            test_file.touch()
            test_file.unlink()

            logger.info(f"Successfully created directory: {primary_path}")
            self.created_directories.append(primary_path)
            return primary_path

        except (PermissionError, OSError) as e:
            logger.warning(f"Failed to create primary directory {primary_path}: {e}")

            # Try fallback in user home
            fallback_path = Path.home() / f".{self.app_name.lower()}" / fallback_name
            try:
                fallback_path.mkdir(parents=True, exist_ok=True)
                # Test write access
                test_file = fallback_path / ".write_test"
                test_file.touch()
                test_file.unlink()

                logger.info(f"Using fallback directory: {fallback_path}")
                self.created_directories.append(fallback_path)
                return fallback_path

            except (PermissionError, OSError) as fallback_error:
                logger.error(
                    f"Failed to create fallback directory {fallback_path}: {fallback_error}"
                )

                # Show error dialog if available
                if HAS_ERROR_DIALOGS:
                    show_directory_error(
                        directory_type=fallback_name.title(),
                        primary_path=primary_path,
                        fallback_path=fallback_path,
                        error=e,
                    )

                raise RuntimeError(
                    f"Cannot create directory {fallback_name}: primary={e}, fallback={fallback_error}"
                ) from e

    def get_platform_directories(
        self, portable_mode: bool = False, development_mode: bool = False
    ) -> dict:
        """
        Get platform-appropriate directories with proper error handling.

        Returns:
            Dictionary with directory paths
        """
        if portable_mode:
            # Portable mode: everything in app directory
            if hasattr(sys, "_MEIPASS"):
                app_dir = Path(sys.executable).parent
            else:
                app_dir = Path(__file__).parent.parent.parent

            base_dir = app_dir / "data"
            return {
                "data": self.create_directory_with_fallback(base_dir, "data"),
                "config": self.create_directory_with_fallback(
                    base_dir / "config", "config"
                ),
                "cache": self.create_directory_with_fallback(
                    base_dir / "cache", "cache"
                ),
                "logs": self.create_directory_with_fallback(base_dir / "logs", "logs"),
            }

        elif development_mode:
            # Development mode: use project directory
            project_dir = Path(__file__).parent.parent.parent / "data"
            return {
                "data": self.create_directory_with_fallback(project_dir, "data"),
                "config": self.create_directory_with_fallback(
                    project_dir / "config", "config"
                ),
                "cache": self.create_directory_with_fallback(
                    project_dir / "cache", "cache"
                ),
                "logs": self.create_directory_with_fallback(
                    project_dir / "logs", "logs"
                ),
            }

        else:
            # Production mode: use platformdirs
            return {
                "data": self.create_directory_with_fallback(
                    Path(platformdirs.user_data_dir(self.app_name, self.app_author)),
                    "data",
                ),
                "config": self.create_directory_with_fallback(
                    Path(platformdirs.user_config_dir(self.app_name, self.app_author)),
                    "config",
                ),
                "cache": self.create_directory_with_fallback(
                    Path(platformdirs.user_cache_dir(self.app_name, self.app_author)),
                    "cache",
                ),
                "logs": self.create_directory_with_fallback(
                    Path(platformdirs.user_log_dir(self.app_name, self.app_author)),
                    "logs",
                ),
            }

    def check_directory_permissions(self, path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if directory is readable and writable.

        Returns:
            (is_accessible, error_message)
        """
        try:
            if not path.exists():
                return False, f"Directory does not exist: {path}"

            if not path.is_dir():
                return False, f"Path is not a directory: {path}"

            # Test read access
            list(path.iterdir())

            # Test write access
            test_file = path / ".permission_test"
            test_file.touch()
            test_file.unlink()

            return True, None

        except PermissionError as e:
            return False, f"Permission denied: {e}"
        except OSError as e:
            return False, f"OS error: {e}"

    def get_directory_info(self, directories: dict) -> dict:
        """Get detailed information about directories."""
        info = {}
        for name, path in directories.items():
            accessible, error = self.check_directory_permissions(path)
            info[name] = {
                "path": str(path),
                "exists": path.exists(),
                "accessible": accessible,
                "error": error,
                "size_mb": self._get_directory_size_mb(path) if path.exists() else 0,
            }
        return info

    def _get_directory_size_mb(self, path: Path) -> float:
        """Get directory size in MB."""
        try:
            total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            return total_size / (1024 * 1024)  # Convert to MB
        except (OSError, PermissionError):
            return 0.0

    def cleanup_test_files(self):
        """Remove any test files that might have been left behind."""
        for directory in self.created_directories:
            try:
                test_files = [".write_test", ".permission_test"]
                for test_file in test_files:
                    test_path = directory / test_file
                    if test_path.exists():
                        test_path.unlink()
            except (OSError, PermissionError):
                pass  # Ignore cleanup errors


def create_secure_directories(
    app_name: str = "BlogsAI",
    app_author: str = "BlogsAI",
    portable_mode: bool = False,
    development_mode: bool = False,
) -> dict:
    """
    Convenience function to create all necessary directories with proper error handling.

    Returns:
        Dictionary with created directory paths
    """
    manager = DirectoryManager(app_name, app_author)
    directories = manager.get_platform_directories(portable_mode, development_mode)

    # Log directory information
    info = manager.get_directory_info(directories)
    logger.info("Directory creation summary:")
    for name, details in info.items():
        status = "OK" if details["accessible"] else "FAILED"
        logger.info(f"  {status} {name}: {details['path']}")
        if details["error"]:
            logger.warning(f"    Error: {details['error']}")

    # Clean up any test files
    manager.cleanup_test_files()

    return directories
