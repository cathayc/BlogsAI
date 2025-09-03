"""Environment variable and .env file management."""

import os
from pathlib import Path
from typing import Optional
from .credential_manager import CredentialManager


class EnvironmentManager:
    """Manages environment variables and .env files."""

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
        self.env_files = [
            self.data_dir / ".env",  # User-specific .env
            Path(".env"),  # Development .env
            Path(".env.local"),  # Local overrides
        ]
        self.credential_manager = CredentialManager(data_dir)

    def load_env_files(self):
        """Load environment variables from .env files."""
        try:
            from dotenv import load_dotenv

            for env_file in self.env_files:
                if env_file.exists():
                    load_dotenv(
                        env_file, override=False
                    )  # Don't override existing env vars
                    print(f"Loaded environment from: {env_file}")
        except ImportError:
            # python-dotenv not installed, skip
            pass

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key using secure credential manager."""
        return self.credential_manager.get_api_key()

    def has_valid_api_key(self) -> bool:
        """Check if a valid API key is available."""
        return self.credential_manager.has_valid_api_key()

    def save_api_key(self, api_key: str) -> tuple[bool, str]:
        """Save API key using secure credential manager."""
        return self.credential_manager.save_api_key(api_key)

    def get_security_status(self) -> dict:
        """Get security status from credential manager."""
        return self.credential_manager.get_security_status()

    def warn_insecure_setup(self) -> Optional[str]:
        """Get security warning if setup is insecure."""
        return self.credential_manager.warn_insecure_setup()

    def create_example_env(self):
        """Create an example .env file for users."""
        example_content = """# BlogsAI Environment Configuration
# Copy this file to .env and fill in your values

# OpenAI API Key (required for analysis)
# Get your API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Override default data directory
# BLOGSAI_DATA_DIR=/path/to/your/data

# Optional: Enable debug logging
# BLOGSAI_DEBUG=true
"""

        example_file = self.data_dir / ".env.example"
        with open(example_file, "w") as f:
            f.write(example_content)

        return example_file

    def setup_user_env(self):
        """Set up environment for end users."""
        user_env = self.data_dir / ".env"

        if not user_env.exists():
            # Create example file
            example_file = self.create_example_env()
            print(f"Created example environment file: {example_file}")
            print("Copy .env.example to .env and add your OpenAI API key")

        return user_env
