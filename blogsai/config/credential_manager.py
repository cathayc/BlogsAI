"""Secure credential management using keyring and fallback strategies."""

import os
import sys
import platform
from pathlib import Path
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages secure storage and retrieval of credentials."""

    SERVICE_NAME = "BlogsAI"
    API_KEY_NAME = "openai_api_key"

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Use distribution manager for data directory
            try:
                from .distribution import get_distribution_manager

                dist_manager = get_distribution_manager()
                self.data_dir = dist_manager.get_data_directory()
            except ImportError:
                # Fallback for cases where distribution manager isn't available
                self.data_dir = Path("data")
        self._keyring_available = None
        self._keyring_backend = None

    def _check_keyring_security(self) -> tuple[bool, str]:
        """Check if keyring is available and secure."""
        try:
            import keyring

            backend = keyring.get_keyring()
            backend_name = backend.__class__.__name__

            # Check for insecure backends
            insecure_backends = [
                "PlaintextKeyring",
                "UncryptedFileKeyring",
                "EncryptedFileKeyring",  # Still not ideal for production
            ]

            if any(insecure in backend_name for insecure in insecure_backends):
                return False, f"Insecure keyring backend: {backend_name}"

            # Test keyring functionality
            test_key = "blogsai_test"
            test_value = "test_value"

            keyring.set_password(self.SERVICE_NAME, test_key, test_value)
            retrieved = keyring.get_password(self.SERVICE_NAME, test_key)
            keyring.delete_password(self.SERVICE_NAME, test_key)

            if retrieved == test_value:
                return True, f"Secure keyring backend: {backend_name}"
            else:
                return False, f"Keyring test failed with backend: {backend_name}"

        except ImportError:
            return False, "Keyring not installed"
        except Exception as e:
            return False, f"Keyring error: {str(e)}"

    @property
    def keyring_available(self) -> bool:
        """Check if secure keyring is available."""
        if self._keyring_available is None:
            self._keyring_available, self._keyring_backend = (
                self._check_keyring_security()
            )
            if not self._keyring_available:
                logger.warning(f"Keyring not available: {self._keyring_backend}")
        return self._keyring_available

    def _get_env_fallback(self) -> Optional[str]:
        """Get API key from environment variables as fallback."""
        # Load from .env files
        try:
            from dotenv import load_dotenv

            env_files = [
                self.data_dir / ".env",
                Path(".env"),
                Path(".env.local"),
            ]

            for env_file in env_files:
                if env_file.exists():
                    load_dotenv(env_file, override=False)
        except ImportError:
            pass

        # Check environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key not in [
            "${OPENAI_API_KEY}",
            "your_openai_api_key_here",
            "MISSING_API_KEY",
        ]:
            return api_key

        return None

    def get_api_key(self) -> Optional[str]:
        """Get OpenAI API key from secure storage or fallback."""
        # Priority order:
        # 1. Secure keyring (production)
        # 2. Environment variables (development)

        # Try keyring first (production)
        if self.keyring_available:
            try:
                import keyring

                api_key = keyring.get_password(self.SERVICE_NAME, self.API_KEY_NAME)
                if api_key:
                    return api_key
            except Exception as e:
                logger.warning(f"Failed to retrieve from keyring: {e}")

        # Fallback to environment variables (development)
        return self._get_env_fallback()

    def save_api_key(self, api_key: str) -> tuple[bool, str]:
        """Save API key to secure storage."""
        if not api_key or len(api_key) < 20:
            return False, "Invalid API key format"

        # Try keyring first (production)
        if self.keyring_available:
            try:
                import keyring

                keyring.set_password(self.SERVICE_NAME, self.API_KEY_NAME, api_key)

                # Verify it was saved
                retrieved = keyring.get_password(self.SERVICE_NAME, self.API_KEY_NAME)
                if retrieved == api_key:
                    # Set environment variable for current session
                    os.environ["OPENAI_API_KEY"] = api_key
                    return True, "API key saved to secure keyring"
                else:
                    return False, "Failed to verify keyring storage"

            except Exception as e:
                logger.error(f"Keyring save failed: {e}")
                # Fall through to .env fallback

        # Fallback to .env file (development)
        try:
            user_env = self.data_dir / ".env"

            # Read existing content
            existing_content = ""
            if user_env.exists():
                with open(user_env, "r") as f:
                    existing_content = f.read()

            # Update or add the API key
            lines = existing_content.split("\n") if existing_content else []
            updated = False

            for i, line in enumerate(lines):
                if line.startswith("OPENAI_API_KEY="):
                    lines[i] = f"OPENAI_API_KEY={api_key}"
                    updated = True
                    break

            if not updated:
                lines.append(f"OPENAI_API_KEY={api_key}")

            # Write back to file
            user_env.parent.mkdir(parents=True, exist_ok=True)
            with open(user_env, "w") as f:
                f.write("\n".join(lines))

            # Set environment variable for current session
            os.environ["OPENAI_API_KEY"] = api_key

            # Warn if using insecure fallback
            if not self.keyring_available:
                logger.warning(f"API key saved to .env file (less secure): {user_env}")
                return (
                    True,
                    f"API key saved to .env file (development mode): {user_env}",
                )
            else:
                return True, "API key saved to .env file as fallback"

        except Exception as e:
            return False, f"Failed to save API key: {str(e)}"

    def delete_api_key(self) -> tuple[bool, str]:
        """Delete API key from all storage locations."""
        deleted_from = []
        errors = []

        # Remove from keyring
        if self.keyring_available:
            try:
                import keyring

                keyring.delete_password(self.SERVICE_NAME, self.API_KEY_NAME)
                deleted_from.append("keyring")
            except Exception as e:
                errors.append(f"keyring: {e}")

        # Remove from .env file
        try:
            user_env = self.data_dir / ".env"
            if user_env.exists():
                with open(user_env, "r") as f:
                    lines = f.readlines()

                # Filter out the API key line
                new_lines = [
                    line for line in lines if not line.startswith("OPENAI_API_KEY=")
                ]

                if len(new_lines) < len(lines):
                    with open(user_env, "w") as f:
                        f.writelines(new_lines)
                    deleted_from.append(".env file")
        except Exception as e:
            errors.append(f".env file: {e}")

        # Remove from environment
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
            deleted_from.append("environment variable")

        if deleted_from:
            return True, f"API key deleted from: {', '.join(deleted_from)}"
        elif errors:
            return False, f"Errors: {'; '.join(errors)}"
        else:
            return True, "No API key found to delete"

    def has_valid_api_key(self) -> bool:
        """Check if a valid API key is available."""
        api_key = self.get_api_key()
        return api_key is not None and len(api_key) >= 20

    def get_security_status(self) -> dict:
        """Get security status information."""
        is_secure, backend_info = self._check_keyring_security()

        return {
            "keyring_available": is_secure,
            "backend_info": backend_info,
            "platform": platform.system(),
            "has_api_key": self.has_valid_api_key(),
            "storage_location": (
                "keyring" if is_secure and self.get_api_key() else ".env file"
            ),
            "is_secure": is_secure and self.has_valid_api_key(),
        }

    def warn_insecure_setup(self) -> Optional[str]:
        """Return warning message if setup is insecure."""
        status = self.get_security_status()

        if not status["keyring_available"] and status["has_api_key"]:
            if platform.system() == "Linux":
                return (
                    "Security Warning: Your system lacks a secure credential storage backend.\n"
                    "Your API key is stored in a plain text file which is less secure.\n"
                    "Consider installing 'python3-secretstorage' or 'gnome-keyring' for better security."
                )
            elif platform.system() == "Windows":
                return (
                    "Security Warning: Windows Credential Manager is not available.\n"
                    "Your API key is stored in a plain text file which is less secure."
                )
            elif platform.system() == "Darwin":  # macOS
                return (
                    "Security Warning: macOS Keychain is not available.\n"
                    "Your API key is stored in a plain text file which is less secure."
                )

        return None
