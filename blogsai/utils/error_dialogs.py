"""
Centralized error dialog utilities for BlogsAI.
Provides consistent error reporting with GUI popups.
"""

import sys
import logging
import traceback
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

# Try to import PyQt5 components for GUI dialogs
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon

    HAS_GUI = True
except ImportError:
    logger.warning("PyQt5 not available - error dialogs will be console-only")
    HAS_GUI = False


class ErrorDialogManager:
    """Manages error dialogs and fallback console reporting."""

    def __init__(self, app_name: str = "BlogsAI"):
        self.app_name = app_name
        self._app = None
        self._parent_widget = None

    def set_parent_widget(self, parent: Optional["QWidget"] = None):
        """Set the parent widget for dialogs."""
        self._parent_widget = parent

    def _ensure_qapp(self) -> bool:
        """Ensure QApplication exists for showing dialogs."""
        if not HAS_GUI:
            return False

        try:
            self._app = QApplication.instance()
            if self._app is None:
                self._app = QApplication(sys.argv)
            return True
        except Exception as e:
            logger.error(f"Failed to create QApplication: {e}")
            return False

    def show_critical_error(
        self,
        title: str,
        message: str,
        details: Optional[str] = None,
        exit_app: bool = False,
    ) -> None:
        """
        Show a critical error dialog that requires user attention.

        Args:
            title: Dialog title
            message: Main error message
            details: Optional detailed error information
            exit_app: Whether to exit the application after showing the dialog
        """
        full_message = message
        if details:
            full_message += f"\n\nDetails:\n{details}"

        logger.critical(f"Critical Error - {title}: {message}")
        if details:
            logger.critical(f"Details: {details}")

        if self._ensure_qapp():
            try:
                msg_box = QMessageBox(self._parent_widget)
                msg_box.setWindowTitle(f"{self.app_name} - {title}")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setText(message)

                if details:
                    msg_box.setDetailedText(details)

                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.setDefaultButton(QMessageBox.Ok)

                # Make dialog modal and bring to front
                msg_box.setModal(True)
                msg_box.raise_()
                msg_box.activateWindow()

                msg_box.exec_()

            except Exception as e:
                logger.error(f"Failed to show GUI error dialog: {e}")
                self._show_console_error(title, full_message)
        else:
            self._show_console_error(title, full_message)

        if exit_app:
            sys.exit(1)

    def show_installation_error(
        self, operation: str, error: Exception, suggestions: Optional[List[str]] = None
    ) -> None:
        """
        Show an installation-specific error dialog.

        Args:
            operation: What operation failed (e.g., "Directory Creation")
            error: The exception that occurred
            suggestions: List of suggested solutions
        """
        title = f"Installation Error: {operation}"
        message = f"Failed to complete {operation.lower()}:\n\n{str(error)}"

        if suggestions:
            message += "\n\nSuggested solutions:\n"
            for i, suggestion in enumerate(suggestions, 1):
                message += f"{i}. {suggestion}\n"

        details = f"Error Type: {type(error).__name__}\n"
        details += f"Error Message: {str(error)}\n"
        details += f"Traceback:\n{traceback.format_exc()}"

        self.show_critical_error(title, message, details, exit_app=False)

    def show_directory_creation_error(
        self,
        directory_type: str,
        primary_path: Path,
        fallback_path: Optional[Path],
        error: Exception,
    ) -> None:
        """
        Show a directory creation error with specific suggestions.

        Args:
            directory_type: Type of directory (e.g., "Data", "Config")
            primary_path: The primary path that failed
            fallback_path: The fallback path (if any)
            error: The exception that occurred
        """
        suggestions = [
            "Restart the application as an administrator",
            f"Manually create the directory: {primary_path}",
            "Choose a different location during setup",
            "Contact support if the problem persists",
        ]

        if fallback_path:
            suggestions.insert(2, f"Use fallback location: {fallback_path}")

        operation = f"{directory_type} Directory Creation"
        self.show_installation_error(operation, error, suggestions)

    def show_permission_error(self, path: Path, operation: str) -> None:
        """
        Show a permission-specific error dialog.

        Args:
            path: The path that couldn't be accessed
            operation: The operation that failed
        """
        title = "Permission Error"
        message = f"Permission denied while trying to {operation}:\n\n{path}"

        suggestions = [
            "Run the application as administrator/root",
            "Check file/folder permissions",
            "Choose a different location with write access",
            "Contact your system administrator",
        ]

        message += "\n\nSuggested solutions:\n"
        for i, suggestion in enumerate(suggestions, 1):
            message += f"{i}. {suggestion}\n"

        details = f"Path: {path}\nOperation: {operation}\nPlatform: {sys.platform}"

        self.show_critical_error(title, message, details)

    def show_startup_error(
        self, component: str, error: Exception, can_continue: bool = False
    ) -> bool:
        """
        Show a startup error dialog.

        Args:
            component: The component that failed to start
            error: The exception that occurred
            can_continue: Whether the app can continue without this component

        Returns:
            True if user wants to continue (only if can_continue=True)
        """
        title = f"Startup Error: {component}"
        message = f"Failed to initialize {component}:\n\n{str(error)}"

        if can_continue:
            message += "\n\nThe application may continue with limited functionality."
            message += "\nDo you want to continue anyway?"

        details = f"Component: {component}\n"
        details += f"Error Type: {type(error).__name__}\n"
        details += f"Error Message: {str(error)}\n"
        details += f"Traceback:\n{traceback.format_exc()}"

        logger.error(f"Startup Error - {component}: {error}")
        logger.error(f"Details: {details}")

        if self._ensure_qapp() and can_continue:
            try:
                msg_box = QMessageBox(self._parent_widget)
                msg_box.setWindowTitle(f"{self.app_name} - {title}")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(message)
                msg_box.setDetailedText(details)

                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.No)

                msg_box.setModal(True)
                msg_box.raise_()
                msg_box.activateWindow()

                result = msg_box.exec_()
                return result == QMessageBox.Yes

            except Exception as gui_error:
                logger.error(f"Failed to show GUI startup dialog: {gui_error}")
                return False
        else:
            self.show_critical_error(title, message, details, exit_app=not can_continue)
            return False

    def _show_console_error(self, title: str, message: str) -> None:
        """Fallback console error display."""
        print("\n" + "=" * 60)
        print(f"ERROR: {title}")
        print("=" * 60)
        print(message)
        print("=" * 60)
        print("Please check the logs for more details.")
        print("=" * 60 + "\n")


# Global error dialog manager instance
_error_manager = None


def get_error_manager() -> ErrorDialogManager:
    """Get the global error dialog manager instance."""
    global _error_manager
    if _error_manager is None:
        _error_manager = ErrorDialogManager()
    return _error_manager


def set_error_dialog_parent(parent: Optional["QWidget"] = None):
    """Set the parent widget for error dialogs."""
    get_error_manager().set_parent_widget(parent)


def show_critical_error(
    title: str, message: str, details: Optional[str] = None, exit_app: bool = False
):
    """Convenience function to show critical error."""
    get_error_manager().show_critical_error(title, message, details, exit_app)


def show_installation_error(
    operation: str, error: Exception, suggestions: Optional[List[str]] = None
):
    """Convenience function to show installation error."""
    get_error_manager().show_installation_error(operation, error, suggestions)


def show_directory_error(
    directory_type: str,
    primary_path: Path,
    fallback_path: Optional[Path],
    error: Exception,
):
    """Convenience function to show directory creation error."""
    get_error_manager().show_directory_creation_error(
        directory_type, primary_path, fallback_path, error
    )


def show_permission_error(path: Path, operation: str):
    """Convenience function to show permission error."""
    get_error_manager().show_permission_error(path, operation)


def show_startup_error(
    component: str, error: Exception, can_continue: bool = False
) -> bool:
    """Convenience function to show startup error."""
    return get_error_manager().show_startup_error(component, error, can_continue)
