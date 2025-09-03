"""Common error handling utilities for the BlogsAI application."""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional


def log_errors(logger_name: str = None):
    """Decorator to automatically log errors from functions."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = logging.getLogger(logger_name or func.__module__)
                logger.error(f"Error in {func.__name__}: {str(e)}")
                raise

        return wrapper

    return decorator


def safe_execute(
    func: Callable, default_return: Any = None, log_errors: bool = True
) -> Any:
    """Safely execute a function and return default value on error."""
    try:
        return func()
    except Exception as e:
        if log_errors:
            logging.error(f"Error in safe_execute: {str(e)}")
        return default_return


def create_error_response(
    error_message: str, error_type: str = "general_error"
) -> Dict[str, Any]:
    """Create a standardized error response dictionary."""
    return {"success": False, "error": error_message, "error_type": error_type}


def create_success_response(data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a standardized success response dictionary."""
    response = {"success": True}
    if data:
        response.update(data)
    return response


class ErrorHandler:
    """Centralized error handling class for consistent error management."""

    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(component_name)

    def log_error(self, message: str, exception: Exception = None):
        """Log an error message with optional exception details."""
        if exception:
            self.logger.error(f"{self.component_name}: {message} - {str(exception)}")
        else:
            self.logger.error(f"{self.component_name}: {message}")

    def log_warning(self, message: str):
        """Log a warning message."""
        self.logger.warning(f"{self.component_name}: {message}")

    def log_info(self, message: str):
        """Log an info message."""
        self.logger.info(f"{self.component_name}: {message}")

    def handle_exception(
        self, exception: Exception, context: str = ""
    ) -> Dict[str, Any]:
        """Handle an exception and return a standardized error response."""
        error_message = f"{context}: {str(exception)}" if context else str(exception)
        self.log_error(error_message, exception)

        # Determine error type based on exception class
        error_type = "general_error"
        if "APIKeyInvalidError" in str(type(exception)):
            error_type = "api_key_invalid"
        elif "OpenAIAPIError" in str(type(exception)):
            error_type = "openai_api_error"
        elif "DatabaseError" in str(type(exception)) or "IntegrityError" in str(
            type(exception)
        ):
            error_type = "database_error"

        return create_error_response(error_message, error_type)


def retry_on_failure(
    max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0
):
    """Decorator to retry function execution on failure."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        sleep_time = delay * (backoff_factor**attempt)
                        logging.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {sleep_time}s: {str(e)}"
                        )
                        time.sleep(sleep_time)
                    else:
                        logging.error(
                            f"All {max_retries} attempts failed for {func.__name__}"
                        )

            raise last_exception

        return wrapper

    return decorator
