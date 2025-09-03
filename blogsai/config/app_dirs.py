"""Platform-specific application directory management."""

import os
import sys
import sqlite3
from pathlib import Path
from typing import Optional
import platformdirs
import shutil


class AppDirectories:
    """Manages platform-specific application directories."""

    APP_NAME = "BlogsAI"
    APP_AUTHOR = "BlogsAI"

    def __init__(self):
        self._app_data_dir = None
        self._app_config_dir = None
        self._app_cache_dir = None
        self._app_logs_dir = None
        self._custom_data_location = None
        self._custom_location_checked = False

        # Check for portable/development mode
        self._is_portable = self._check_portable_mode()
        self._is_development = self._check_development_mode()

    def _check_portable_mode(self) -> bool:
        """Check if running in portable mode."""
        return (
            os.getenv("BLOGSAI_PORTABLE", "").lower() in ("1", "true", "yes")
            or (Path(__file__).parent.parent.parent / "PORTABLE").exists()
            or (Path(sys.executable).parent / "PORTABLE").exists()
        )

    def _check_development_mode(self) -> bool:
        """Check if running in development mode."""
        return (
            os.getenv("BLOGSAI_DEV", "").lower() in ("1", "true", "yes")
            or "pytest" in sys.modules
            or os.path.exists(Path(__file__).parent.parent.parent / ".git")
        )

    def _get_custom_location(self) -> Optional[Path]:
        """Get custom data location with caching."""
        if not self._custom_location_checked:
            self._custom_data_location = self._get_saved_data_location()
            self._custom_location_checked = True
        return self._custom_data_location

    @property
    def app_data_dir(self) -> Path:
        """Get the main application data directory."""
        if self._app_data_dir is None:
            # Check for saved custom location first
            custom_location = self._get_custom_location()
            if custom_location:
                self._app_data_dir = custom_location
            elif self._is_portable:
                # Portable mode: everything in app directory
                if hasattr(sys, "_MEIPASS"):
                    # PyInstaller bundle
                    app_dir = Path(sys.executable).parent
                else:
                    # Development or regular Python
                    app_dir = Path(__file__).parent.parent.parent
                self._app_data_dir = app_dir / "data"
            elif self._is_development:
                # Development mode: use project directory
                self._app_data_dir = Path(__file__).parent.parent.parent / "data"
            else:
                # Production mode: use platformdirs
                self._app_data_dir = Path(
                    platformdirs.user_data_dir(
                        appname=self.APP_NAME, appauthor=self.APP_AUTHOR
                    )
                )
        return self._app_data_dir

    @property
    def app_config_dir(self) -> Path:
        """Get the application config directory."""
        if self._app_config_dir is None:
            # When using custom data location, keep config in the same directory
            custom_location = self._get_custom_location()
            if custom_location:
                self._app_config_dir = custom_location
            elif self._is_portable or self._is_development:
                # Use data directory for portable/dev mode
                self._app_config_dir = self.app_data_dir
            else:
                # Production mode: on macOS, both data and config should be in Application Support
                # platformdirs already handles this correctly
                self._app_config_dir = Path(
                    platformdirs.user_data_dir(
                        appname=self.APP_NAME, appauthor=self.APP_AUTHOR
                    )
                )
        return self._app_config_dir

    @property
    def app_cache_dir(self) -> Path:
        """Get the application cache directory."""
        if self._app_cache_dir is None:
            if self._is_portable or self._is_development:
                # Use data directory for portable/dev mode
                self._app_cache_dir = self.app_data_dir / "cache"
            else:
                # Production mode: use platformdirs
                self._app_cache_dir = Path(
                    platformdirs.user_cache_dir(
                        appname=self.APP_NAME, appauthor=self.APP_AUTHOR
                    )
                )
        return self._app_cache_dir

    @property
    def app_logs_dir(self) -> Path:
        """Get the application logs directory."""
        if self._app_logs_dir is None:
            if self._is_portable or self._is_development:
                # Use data directory for portable/dev mode
                self._app_logs_dir = self.app_data_dir / "logs"
            else:
                # Production mode: use platformdirs for proper cross-platform log directory
                # On macOS this will be ~/Library/Logs/BlogsAI
                # On other platforms, falls back to data directory
                try:
                    self._app_logs_dir = Path(
                        platformdirs.user_log_dir(
                            appname=self.APP_NAME, appauthor=self.APP_AUTHOR
                        )
                    )
                except Exception:
                    # Fallback to data directory if platformdirs fails
                    self._app_logs_dir = self.app_data_dir / "logs"
        return self._app_logs_dir

    @property
    def database_path(self) -> Path:
        """Get the database file path."""
        return self.app_data_dir / "blogsai.db"

    @property
    def reports_dir(self) -> Path:
        """Get the reports directory."""
        if self._is_portable or self._is_development:
            # Use data directory for portable/dev mode
            return self.app_data_dir / "reports"
        else:
            # Production mode: use user's Downloads folder
            try:
                downloads_dir = (
                    Path(platformdirs.user_downloads_dir()) / "BlogsAI Reports"
                )
                return downloads_dir
            except Exception:
                # Fallback to data directory if Downloads not accessible
                return self.app_data_dir / "reports"

    def get_reports_directory(self) -> Path:
        """Get the reports directory, creating it if needed and handling fallbacks."""
        preferred_dir = self.reports_dir

        # Try to create and use the preferred directory
        try:
            preferred_dir.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = preferred_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
            return preferred_dir
        except (PermissionError, OSError) as e:
            print(
                f"Warning: Cannot use preferred reports directory {preferred_dir}: {e}"
            )

            # Fallback to data directory
            fallback_dir = self.app_data_dir / "reports"
            try:
                fallback_dir.mkdir(parents=True, exist_ok=True)
                print(f"Using fallback reports directory: {fallback_dir}")
                return fallback_dir
            except Exception as fallback_error:
                print(
                    f"Error: Cannot create fallback reports directory: {fallback_error}"
                )
                raise RuntimeError(f"Cannot create reports directory") from e

    @property
    def prompts_dir(self) -> Path:
        """Get the prompts directory."""
        return self.app_config_dir / "prompts"

    @property
    def user_config_file(self) -> Path:
        """Get the user config file path."""
        return self.app_config_dir / "settings.yaml"

    @property
    def sources_config_file(self) -> Path:
        """Get the sources config file path."""
        return self.app_config_dir / "sources.yaml"

    def _get_saved_data_location(self) -> Optional[Path]:
        """Check for a saved custom data location."""
        # First check environment variable (highest priority)
        env_data_dir = os.getenv("BLOGSAI_DATA_DIR")
        if env_data_dir:
            return Path(env_data_dir)

        # Then check for config files in potential locations
        potential_locations = [
            # Check default location for a config file
            Path(platformdirs.user_data_dir(self.APP_NAME, self.APP_AUTHOR))
            / ".blogsai_config",
            # Check current directory for a config file (development)
            Path.cwd() / ".blogsai_config",
            # Check user home directory for a global config
            Path.home() / ".blogsai_config",
        ]

        for config_file in potential_locations:
            if config_file.exists():
                try:
                    with open(config_file, "r") as f:
                        for line in f:
                            if line.startswith("data_dir="):
                                saved_path = line.split("=", 1)[1].strip()
                                saved_path_obj = Path(saved_path)
                                if saved_path_obj.exists():
                                    return saved_path_obj
                except Exception:
                    # If we can't read the config file, continue
                    continue

        return None

    def get_bundled_resource_dir(self) -> Optional[Path]:
        """Get the bundled resources directory."""
        if hasattr(sys, "_MEIPASS"):
            # Running as PyInstaller bundle - check multiple possible locations
            bundle_dir = Path(sys._MEIPASS)

            # Try the locations defined in the build script
            possible_paths = [
                bundle_dir
                / "_internal"
                / "config",  # Primary location from build script
                bundle_dir / "_internal" / "defaults",  # Alternative defaults location
                bundle_dir / "config",  # Fallback location
            ]

            # Also check environment variables set by runtime hook
            if os.getenv("BLOGSAI_BUNDLED_CONFIG"):
                possible_paths.insert(0, Path(os.getenv("BLOGSAI_BUNDLED_CONFIG")))

            for path in possible_paths:
                if path.exists():
                    return path

            # If none found, return the expected path for error reporting
            return bundle_dir / "_internal" / "config"
        else:
            # Running from source
            return Path(__file__).parent.parent.parent / "data" / "config"

    def ensure_directories(self):
        """Create all necessary directories."""
        dirs_to_create = [
            self.app_data_dir,
            self.app_config_dir,
            self.app_cache_dir,
            self.app_logs_dir,
            self.prompts_dir,
        ]

        # Create basic directories
        for directory in dirs_to_create:
            directory.mkdir(parents=True, exist_ok=True)

        # Handle reports directory separately since it might be in Downloads
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            print(f"Reports directory created: {self.reports_dir}")
        except (PermissionError, OSError) as e:
            print(
                f"Warning: Could not create reports directory {self.reports_dir}: {e}"
            )
            # Try fallback location
            fallback_reports = self.app_data_dir / "reports"
            try:
                fallback_reports.mkdir(parents=True, exist_ok=True)
                print(f"Using fallback reports directory: {fallback_reports}")
            except Exception as fallback_error:
                print(
                    f"Warning: Could not create fallback reports directory: {fallback_error}"
                )

    def initialize_user_config(self, force_update: bool = False):
        """Initialize user configuration from bundled defaults."""
        bundled_config = self.get_bundled_resource_dir()

        if not bundled_config or not bundled_config.exists():
            # Try to create minimal default config instead of failing
            print(f"Warning: Bundled config directory not found: {bundled_config}")
            print("Creating minimal default configuration...")

            try:
                self._create_minimal_config()
                return
            except Exception as fallback_error:
                # Provide detailed debugging information if fallback also fails
                error_details = [
                    f"Bundled config directory not found: {bundled_config}",
                    f"Fallback config creation also failed: {fallback_error}",
                    f"PyInstaller bundle: {hasattr(sys, '_MEIPASS')}",
                ]

                if hasattr(sys, "_MEIPASS"):
                    bundle_dir = Path(sys._MEIPASS)
                    error_details.extend(
                        [
                            f"Bundle directory: {bundle_dir}",
                            f"Bundle contents: {list(bundle_dir.iterdir()) if bundle_dir.exists() else 'Directory does not exist'}",
                        ]
                    )

                    # Check for _internal directory
                    internal_dir = bundle_dir / "_internal"
                    if internal_dir.exists():
                        error_details.append(
                            f"_internal contents: {list(internal_dir.iterdir())}"
                        )
                    else:
                        error_details.append("_internal directory not found")

                error_message = "\n".join(error_details)
                raise FileNotFoundError(error_message)

        # Copy settings.yaml if it doesn't exist or force update
        bundled_settings = bundled_config / "settings.yaml"
        if bundled_settings.exists() and (
            not self.user_config_file.exists() or force_update
        ):
            self.user_config_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_settings, self.user_config_file)
            print(f"Copied settings: {bundled_settings} → {self.user_config_file}")

        # Copy sources.yaml if it doesn't exist or force update
        bundled_sources = bundled_config / "sources.yaml"
        if bundled_sources.exists() and (
            not self.sources_config_file.exists() or force_update
        ):
            self.sources_config_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_sources, self.sources_config_file)
            print(f"Copied sources: {bundled_sources} → {self.sources_config_file}")

        # Copy prompts directory if it doesn't exist, is empty, or force update
        bundled_prompts = bundled_config / "prompts"
        prompts_need_copy = (
            not self.prompts_dir.exists()
            or force_update
            or (
                self.prompts_dir.exists() and not any(self.prompts_dir.iterdir())
            )  # Empty directory
        )

        if bundled_prompts.exists() and prompts_need_copy:
            if self.prompts_dir.exists():
                shutil.rmtree(self.prompts_dir)
            shutil.copytree(bundled_prompts, self.prompts_dir)
            print(f"Copied prompts: {bundled_prompts} → {self.prompts_dir}")

    def _create_minimal_config(self):
        """Create minimal default configuration when bundled config is not available."""
        # Ensure directories exist
        self.user_config_file.parent.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal settings.yaml
        if not self.user_config_file.exists():
            minimal_settings = """# BlogsAI Configuration
openai:
  api_key: ""
  model: "gpt-4"
  max_tokens: 4000

analysis:
  batch_size: 10
  relevance_threshold: 0.7

output:
  format: "markdown"
  include_metadata: true
"""
            self.user_config_file.write_text(minimal_settings)
            print(f"Created minimal settings: {self.user_config_file}")

        # Create minimal sources.yaml
        if not self.sources_config_file.exists():
            minimal_sources = """# News Sources Configuration
sources:
  government:
    cisa:
      name: "CISA Cybersecurity Advisories"
      url: "https://www.cisa.gov/news-events/cybersecurity-advisories"
      enabled: true
      category: "cybersecurity"
    
  news:
    reuters:
      name: "Reuters Technology"
      url: "https://www.reuters.com/technology/"
      enabled: true
      category: "technology"
"""
            self.sources_config_file.write_text(minimal_sources)
            print(f"Created minimal sources: {self.sources_config_file}")

        # Create minimal prompts
        if not (self.prompts_dir / "article_analysis.txt").exists():
            minimal_prompt = """Analyze the following article and provide:
1. Key points and insights
2. Relevance to cybersecurity/technology
3. Potential impact assessment

Article: {article_content}
"""
            (self.prompts_dir / "article_analysis.txt").write_text(minimal_prompt)
            print(
                f"Created minimal prompt: {self.prompts_dir / 'article_analysis.txt'}"
            )

    def initialize_database(self, force_update: bool = False):
        """Initialize database from bundled default or create new one."""
        bundled_config = self.get_bundled_resource_dir()

        # Ensure database directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        if not bundled_config:
            # Running from source - use the development database
            dev_db = Path(__file__).parent.parent.parent / "data" / "blogsai.db"
            if dev_db.exists() and (not self.database_path.exists() or force_update):
                if self.database_path.exists():
                    # Create backup
                    backup_path = self.database_path.with_suffix(".db.backup")
                    shutil.copy2(self.database_path, backup_path)
                    print(f"Created database backup: {backup_path}")

                shutil.copy2(dev_db, self.database_path)
                print(f"Copied database: {dev_db} → {self.database_path}")
                return
        else:
            # Running from bundle - copy bundled database if it exists
            bundled_db = bundled_config / "blogsai.db"
            if bundled_db.exists() and (
                not self.database_path.exists() or force_update
            ):
                if self.database_path.exists():
                    # Create backup
                    backup_path = self.database_path.with_suffix(".db.backup")
                    shutil.copy2(self.database_path, backup_path)
                    print(f"Created database backup: {backup_path}")

                shutil.copy2(bundled_db, self.database_path)
                print(f"Copied database: {bundled_db} → {self.database_path}")
                return

        # If no database exists and no bundled DB, create a new one
        if not self.database_path.exists():
            print("Creating new database with schema...")
            self._create_database_schema()

    def _create_database_schema(self):
        """Create database schema from scratch."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        try:
            # Create sources table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    scraper_type TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create articles table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY,
                    source_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL UNIQUE,
                    published_date TIMESTAMP NOT NULL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    author TEXT,
                    category TEXT,
                    tags TEXT,
                    word_count INTEGER,
                    sentiment_score REAL,
                    relevance_score INTEGER,
                    practice_areas TEXT,
                    dollar_amount TEXT,
                    whistleblower_indicators TEXT,
                    blog_potential TEXT,
                    relevance_summary TEXT,
                    relevance_scored_at TIMESTAMP,
                    detailed_analysis TEXT,
                    detailed_analysis_json TEXT,
                    detailed_analysis_tokens INTEGER,
                    detailed_analysis_at TIMESTAMP,
                    FOREIGN KEY (source_id) REFERENCES sources (id)
                )
            """
            )

            # Create reports table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    analysis TEXT NOT NULL,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    article_count INTEGER DEFAULT 0,
                    tokens_used INTEGER,
                    html_file TEXT,
                    json_file TEXT,
                    markdown_file TEXT
                )
            """
            )

            # Create report_articles table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS report_articles (
                    id INTEGER PRIMARY KEY,
                    report_id INTEGER NOT NULL,
                    article_id INTEGER NOT NULL,
                    FOREIGN KEY (report_id) REFERENCES reports (id),
                    FOREIGN KEY (article_id) REFERENCES articles (id)
                )
            """
            )

            # Create scraping_logs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_logs (
                    id INTEGER PRIMARY KEY,
                    source_id INTEGER NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL,
                    articles_found INTEGER DEFAULT 0,
                    articles_new INTEGER DEFAULT 0,
                    error_message TEXT,
                    FOREIGN KEY (source_id) REFERENCES sources (id)
                )
            """
            )

            # Insert default sources
            default_sources = [
                (
                    "Department of Justice",
                    "government",
                    "https://www.justice.gov",
                    "government",
                    1,
                ),
                (
                    "Securities and Exchange Commission",
                    "government",
                    "https://www.sec.gov",
                    "government",
                    1,
                ),
                (
                    "Commodity Futures Trading Commission",
                    "government",
                    "https://www.cftc.gov",
                    "government",
                    1,
                ),
                ("Manual URL", "manual", "", "manual", 1),
            ]

            cursor.executemany(
                """
                INSERT INTO sources (name, source_type, base_url, scraper_type, enabled)
                VALUES (?, ?, ?, ?, ?)
            """,
                default_sources,
            )

            conn.commit()
            print(f"Database schema created successfully: {self.database_path}")

        except Exception as e:
            print(f"Error creating database schema: {e}")
            conn.rollback()
        finally:
            conn.close()

    def setup_environment_variables(self):
        """Set up environment variables for the application."""
        os.environ["BLOGSAI_DATA_DIR"] = str(self.app_data_dir)
        os.environ["BLOGSAI_CONFIG_DIR"] = str(self.app_config_dir)
        os.environ["BLOGSAI_DB_PATH"] = str(self.database_path)
        os.environ["BLOGSAI_PROMPTS_DIR"] = str(self.prompts_dir)
        os.environ["BLOGSAI_LOGS_DIR"] = str(self.app_logs_dir)

    def get_platform_info(self) -> dict:
        """Get platform-specific directory information."""
        return {
            "platform": sys.platform,
            "app_data_dir": str(self.app_data_dir),
            "app_config_dir": str(self.app_config_dir),
            "app_cache_dir": str(self.app_cache_dir),
            "app_logs_dir": str(self.app_logs_dir),
            "database_path": str(self.database_path),
            "reports_dir": str(self.reports_dir),
            "prompts_dir": str(self.prompts_dir),
            "bundled_resources": str(self.get_bundled_resource_dir()),
        }

    def print_setup_info(self):
        """Print setup information for debugging."""
        info = self.get_platform_info()
        print("=== BlogsAI App Directories ===")
        for key, value in info.items():
            print(f"{key}: {value}")
        print("=" * 35)

    def is_first_time_setup_needed(self) -> dict:
        """
        Comprehensive check for first-time setup requirements.

        Returns:
            Dictionary with check results and overall status
        """
        checks = {
            "config_file": self._check_config_file(),
            "api_key": self._check_api_key(),
            "database": self._check_database(),
            "prompts": self._check_prompts(),
            "directories": self._check_directories(),
        }

        # Overall status - setup needed if ANY check fails
        checks["setup_needed"] = not all(
            check["status"] for check in checks.values() if isinstance(check, dict)
        )

        return checks

    def _check_config_file(self) -> dict:
        """Check if main configuration file exists and is valid."""
        config_file = self.user_config_file

        if not config_file.exists():
            return {
                "status": False,
                "message": f"Configuration file missing: {config_file}",
                "file": str(config_file),
            }

        # Check if file is readable and has basic structure
        try:
            import yaml

            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f)

            # Check for essential sections
            if not isinstance(config_data, dict):
                return {
                    "status": False,
                    "message": "Configuration file is not valid YAML",
                    "file": str(config_file),
                }

            # Check for required sections
            required_sections = ["openai", "analysis"]
            missing_sections = [
                section for section in required_sections if section not in config_data
            ]

            if missing_sections:
                return {
                    "status": False,
                    "message": f"Configuration file missing sections: {missing_sections}",
                    "file": str(config_file),
                }

            return {
                "status": True,
                "message": f"Configuration file is valid at {config_file}",
                "file": str(config_file),
            }

        except Exception as e:
            return {
                "status": False,
                "message": f"Configuration file is corrupted: {e}",
                "file": str(config_file),
            }

    def _check_api_key(self) -> dict:
        """Check if OpenAI API key is configured."""
        try:
            from .credential_manager import CredentialManager

            cred_manager = CredentialManager()
            api_key = cred_manager.get_api_key()

            if not api_key or api_key == "MISSING_API_KEY":
                return {
                    "status": False,
                    "message": "OpenAI API key not configured",
                    "storage": "system_keychain",
                }

            # Basic validation - should start with 'sk-' for OpenAI keys
            if not api_key.startswith("sk-"):
                return {
                    "status": False,
                    "message": "API key format appears invalid",
                    "storage": "system_keychain",
                }

            return {
                "status": True,
                "message": "API key is configured in system keychain",
                "storage": "system_keychain",
            }

        except Exception as e:
            return {
                "status": False,
                "message": f"Cannot access API key storage: {e}",
                "storage": "system_keychain",
            }

    def _check_database(self) -> dict:
        """Check if database exists and has proper schema."""
        db_path = self.database_path

        if not db_path.exists():
            return {
                "status": False,
                "message": f"Database file missing: {db_path}",
                "file": str(db_path),
            }

        # Check database schema
        try:
            import sqlite3

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                # Check for essential tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                # Define required tables based on actual schema
                required_tables = [
                    "articles",
                    "sources",
                    "reports",
                ]  # Core tables needed for operation
                missing_tables = [
                    table for table in required_tables if table not in tables
                ]

                if missing_tables:
                    return {
                        "status": False,
                        "message": f"Database missing tables: {missing_tables}",
                        "file": str(db_path),
                        "existing_tables": tables,
                    }

                return {
                    "status": True,
                    "message": f"Database schema is valid at {db_path} ({len(tables)} tables)",
                    "file": str(db_path),
                    "tables": tables,
                }

        except Exception as e:
            return {
                "status": False,
                "message": f"Database error: {e}",
                "file": str(db_path),
            }

    def _check_prompts(self) -> dict:
        """Check if AI prompts are available."""
        prompts_dir = self.prompts_dir

        if not prompts_dir.exists():
            return {
                "status": False,
                "message": f"Prompts directory missing: {prompts_dir}",
                "directory": str(prompts_dir),
            }

        # Check for essential prompt files
        required_prompts = [
            "article_analysis.txt",
            "citation_verifier.txt",
            "relevance_scorer.txt",
            "insight_analysis.txt",
        ]

        missing_prompts = []
        existing_prompts = []

        for prompt_file in required_prompts:
            prompt_path = prompts_dir / prompt_file
            if prompt_path.exists():
                # Check if file has content
                try:
                    content = prompt_path.read_text().strip()
                    if content:
                        existing_prompts.append(prompt_file)
                    else:
                        missing_prompts.append(f"{prompt_file} (empty)")
                except Exception:
                    missing_prompts.append(f"{prompt_file} (unreadable)")
            else:
                missing_prompts.append(prompt_file)

        if missing_prompts:
            return {
                "status": False,
                "message": f"Missing or invalid prompts: {missing_prompts}",
                "directory": str(prompts_dir),
                "existing": existing_prompts,
                "missing": missing_prompts,
            }

        return {
            "status": True,
            "message": f'All required prompts available at {prompts_dir} ({len(existing_prompts)} files: {", ".join(existing_prompts)})',
            "directory": str(prompts_dir),
            "prompts": existing_prompts,
        }

    def _check_directories(self) -> dict:
        """Check if all required directories exist and are writable."""
        required_dirs = {
            "data": self.app_data_dir,
            "config": self.app_config_dir,
            "cache": self.app_cache_dir,
            "logs": self.app_logs_dir,
            "prompts": self.prompts_dir,
        }

        # Don't check reports directory here since it might be in Downloads
        # and we handle that separately with fallbacks

        missing_dirs = []
        unwritable_dirs = []
        valid_dirs = []

        for name, directory in required_dirs.items():
            if not directory.exists():
                missing_dirs.append(f"{name}: {directory}")
                continue

            # Test write access
            try:
                test_file = directory / ".write_test"
                test_file.touch()
                test_file.unlink()
                valid_dirs.append(f"{name}: {directory}")
            except (PermissionError, OSError):
                unwritable_dirs.append(f"{name}: {directory}")

        issues = missing_dirs + unwritable_dirs
        if issues:
            return {
                "status": False,
                "message": f"Directory issues found: {len(issues)} problems",
                "missing": missing_dirs,
                "unwritable": unwritable_dirs,
                "valid": valid_dirs,
            }

        # Format directory list for display
        dir_list = []
        for dir_entry in valid_dirs:
            name, path = dir_entry.split(": ", 1)
            dir_list.append(f"{name} ({path})")

        return {
            "status": True,
            "message": f'All directories accessible ({len(valid_dirs)} directories): {"; ".join(dir_list)}',
            "directories": valid_dirs,
        }


# Global instance
app_dirs = AppDirectories()
