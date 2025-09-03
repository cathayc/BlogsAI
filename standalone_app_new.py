#!/usr/bin/env python3
"""
Enhanced standalone entry point for BlogsAI desktop application.
Uses the new Calibre-inspired distribution system.
"""

import os
import sys
import logging
from pathlib import Path

# Import error handling utilities early
try:
    from blogsai.utils.error_dialogs import show_startup_error, show_critical_error, set_error_dialog_parent
    HAS_ERROR_DIALOGS = True
except ImportError:
    print("Warning: Error dialogs not available")
    HAS_ERROR_DIALOGS = False
    
    def show_startup_error(component, error, can_continue=False):
        print(f"STARTUP ERROR - {component}: {error}")
        return False
    
    def show_critical_error(title, message, details=None, exit_app=False):
        print(f"CRITICAL ERROR - {title}: {message}")
        if exit_app:
            sys.exit(1)
    
    def set_error_dialog_parent(parent):
        pass

def main():
    """Main application entry point with enhanced distribution support."""
    print("Starting BlogsAI Desktop Application...")
    
    try:
        # Ensure blogsai package is available
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Initialize the distribution system first
        print("Initializing distribution system...")
        try:
            from blogsai.config.distribution import get_distribution_manager
            from blogsai.config.config import ConfigManager
            
            dist_manager = get_distribution_manager()
        except Exception as e:
            show_critical_error(
                "Initialization Error",
                "Failed to initialize the distribution system.",
                f"Error: {str(e)}\n\nThis is usually caused by missing dependencies or corrupted installation.",
                exit_app=True
            )
        
        # Show distribution info
        print(f"Distribution mode: {'portable' if dist_manager.is_portable else ('development' if dist_manager.is_development else 'production')}")
        print(f"Data directory: {dist_manager.get_data_directory()}")
        print(f"Config directory: {dist_manager.get_config_directory()}")
        
        # Initialize user configuration from bundled defaults (including prompts)
        print("Initializing user configuration...")
        try:
            from blogsai.config.app_dirs import app_dirs
            app_dirs.initialize_user_config()
            print("User configuration initialized successfully")
        except Exception as e:
            # Add detailed debugging information for bundle path issues
            debug_info = []
            if hasattr(sys, '_MEIPASS'):
                debug_info.extend([
                    f"PyInstaller bundle detected: {sys._MEIPASS}",
                    f"Bundle directory exists: {Path(sys._MEIPASS).exists()}",
                ])
                
                # Check for expected directories
                bundle_dir = Path(sys._MEIPASS)
                expected_paths = [
                    bundle_dir / "_internal",
                    bundle_dir / "_internal" / "config",
                    bundle_dir / "_internal" / "defaults"
                ]
                
                for path in expected_paths:
                    debug_info.append(f"{path}: exists={path.exists()}")
                    if path.exists() and path.is_dir():
                        try:
                            contents = list(path.iterdir())[:5]  # First 5 items
                            debug_info.append(f"  Contents: {[str(p.name) for p in contents]}")
                        except Exception:
                            debug_info.append(f"  Contents: Unable to list")
            
            detailed_error = str(e)
            if debug_info:
                detailed_error += "\n\nBundle Debug Info:\n" + "\n".join(debug_info)
            
            if not show_startup_error("User Configuration", Exception(detailed_error), can_continue=True):
                show_critical_error(
                    "Configuration Error", 
                    "Failed to initialize user configuration.",
                    f"Error: {detailed_error}\n\nThe application may not function properly.",
                    exit_app=True
                )
        
        # Initialize configuration manager with distribution support
        try:
            config_manager = ConfigManager()
        except Exception as e:
            show_critical_error(
                "Configuration Manager Error",
                "Failed to initialize configuration manager.",
                f"Error: {str(e)}\n\nThis is required for the application to function.",
                exit_app=True
            )
        
        # Setup logging using distribution-aware paths
        print("Setting up logging...")
        try:
            from blogsai.utils.logging_config import setup_logging, setup_exception_logging, get_logger
            log_file = setup_logging(log_level=logging.DEBUG)
            setup_exception_logging()
            
            logger = get_logger(__name__)
            logger.info("=== BlogsAI Application Starting ===")
            logger.info(f"Python version: {sys.version}")
            logger.info(f"Platform: {sys.platform}")
            logger.info(f"Distribution mode: {dist_manager.get_distribution_info()['mode']}")
            logger.info(f"Running from: {sys.argv[0]}")
            if hasattr(sys, '_MEIPASS'):
                logger.info(f"PyInstaller bundle: {sys._MEIPASS}")
            
            # Log distribution info
            dist_info = dist_manager.get_distribution_info()
            for key, value in dist_info.items():
                logger.info(f"{key}: {value}")
                
        except Exception as e:
            print(f"Warning: Failed to set up logging: {e}")
            logger = None
        
        # Initialize database using distribution-aware paths
        print("Initializing database...")
        try:
            from blogsai.core import init_db
            init_db()
            
            # Apply database migrations if needed
            from blogsai.database.database import migrate_database
            migrate_database()
            
            # Populate initial sources if database is empty
            print("Checking database sources...")
            
            # Check if sources exist
            from blogsai.core import db_session
            from blogsai.database.models import Source
            with db_session() as db:
                source_count = db.query(Source).count()
                print(f"Found {source_count} sources in database")
                
                if source_count == 0:
                    print("No sources found, populating initial sources...")
                    
                    # Get database URL for DatabaseManager
                    config = config_manager.load_config()
                    from blogsai.database.database import DatabaseManager
                    db_manager = DatabaseManager(config.database.url)
                    db_manager.populate_initial_sources(config_manager)
                    
                    with db_session() as db2:
                        new_count = db2.query(Source).count()
                        print(f"Added {new_count} default sources to database")
                        if logger:
                            logger.info(f"Populated {new_count} initial sources in database")
            
            print("Database setup complete")
            
            if logger:
                logger.info("Database initialized successfully")
                
        except Exception as e:
            if not show_startup_error("Database", e, can_continue=True):
                show_critical_error(
                    "Database Error",
                    "Failed to initialize database.",
                    f"Error: {str(e)}\n\nThe application requires a database to function.",
                    exit_app=True
                )
            else:
                print(f"Warning: Database initialization failed: {e}")
                if logger:
                    logger.error(f"Database initialization failed: {e}")
        
        # Check for API key using secure storage
        print("Checking API key configuration...")
        api_key = config_manager.get_openai_api_key()
        if not api_key or api_key == "MISSING_API_KEY":
            print("No API key found in secure storage")
            if logger:
                logger.info("No API key found, will prompt user during GUI startup")
        else:
            print("API key found in secure storage")
            if logger:
                logger.info("API key loaded from secure storage")
        
        print("Launching GUI...")
        if logger:
            logger.info("Starting GUI components...")
        
        # Import GUI components
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
            from PyQt5.QtCore import Qt
            from PyQt5.QtGui import QPalette, QColor
            
            from blogsai.gui.main_window import MainWindow
        except ImportError as e:
            show_critical_error(
                "GUI Import Error",
                "Failed to import GUI components.",
                f"Error: {str(e)}\n\nPyQt5 may not be properly installed or available.",
                exit_app=True
            )
        
        # Create QApplication
        try:
            app = QApplication(sys.argv)
            app.setApplicationName("BlogsAI")
            app.setOrganizationName("BlogsAI")
            
            # Set error dialog parent now that we have QApplication
            set_error_dialog_parent(None)
        except Exception as e:
            show_critical_error(
                "Application Creation Error",
                "Failed to create the main application.",
                f"Error: {str(e)}\n\nThis may be due to display or Qt configuration issues.",
                exit_app=True
            )
        app.setOrganizationDomain("blogsai.com")
        
        # Set modern style
        app.setStyle('Fusion')
        
        # Apply light theme palette
        light_palette = app.palette()
        light_palette.setColor(QPalette.Window, QColor(245, 245, 245))
        light_palette.setColor(QPalette.WindowText, QColor(50, 50, 50))
        light_palette.setColor(QPalette.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.AlternateBase, QColor(235, 235, 235))
        light_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
        light_palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Text, QColor(50, 50, 50))
        light_palette.setColor(QPalette.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ButtonText, QColor(50, 50, 50))
        light_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        light_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        light_palette.setColor(QPalette.Highlight, QColor(52, 152, 219))
        light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        app.setPalette(light_palette)
        
        # Check if this is a first-time setup for production builds
        needs_first_time_setup = False
        completed_first_time_setup = False
        setup_check_results = None
        
        if not dist_manager.is_development:
            # Comprehensive setup check
            from blogsai.config.app_dirs import app_dirs
            setup_check_results = app_dirs.is_first_time_setup_needed()
            needs_first_time_setup = setup_check_results['setup_needed']
            
            if logger:
                logger.info("First-time setup check results:")
                for check_name, result in setup_check_results.items():
                    if isinstance(result, dict) and 'status' in result:
                        status = "OK" if result['status'] else "FAILED"
                        logger.info(f"  {status} {check_name}: {result['message']}")
                logger.info(f"Overall setup needed: {needs_first_time_setup}")
            
        if needs_first_time_setup:
            if logger:
                logger.info("First-time setup required...")
            
            try:
                from blogsai.gui.dialogs.first_time_setup_dialog import FirstTimeSetupDialog
                
                # Show first-time setup dialog with check results
                setup_dialog = FirstTimeSetupDialog(setup_check_results=setup_check_results)
                if setup_dialog.exec_() != QDialog.Accepted:
                    if logger:
                        logger.info("User cancelled first-time setup")
                    QMessageBox.information(
                        None,
                        "Setup Required", 
                        "BlogsAI requires initial configuration to function. "
                        "Please restart the application to complete setup."
                    )
                    sys.exit(0)
                
                # Get setup results and update configuration
                setup_results = setup_dialog.get_setup_results()
                completed_first_time_setup = True
                if logger:
                    logger.info(f"First-time setup completed: {setup_results}")
                    
                # Update distribution manager with selected paths if different
                # The directories are already created by the dialog
                
                # Refresh API key status after first-time setup
                api_key = config_manager.get_openai_api_key()
                if logger and api_key and api_key != "MISSING_API_KEY":
                    logger.info("API key configured during first-time setup")
                    
            except Exception as e:
                show_critical_error(
                    "First-Time Setup Error",
                    "Failed to complete first-time setup.",
                    f"Error: {str(e)}\n\nThe application cannot continue without proper setup.",
                    exit_app=True
                )
            
        # Create main window
        try:
            window = MainWindow()
            set_error_dialog_parent(window)  # Set main window as error dialog parent
        except Exception as e:
            show_critical_error(
                "Main Window Error",
                "Failed to create the main application window.",
                f"Error: {str(e)}\n\nThis may be due to missing resources or Qt configuration issues.",
                exit_app=True
            )
        
        # Check for API key and prompt if needed (skip if first-time setup was just completed)
        if (not api_key or api_key == "MISSING_API_KEY") and not completed_first_time_setup:
            if logger:
                logger.info("Prompting for API key...")
            
            from blogsai.gui.api_key_dialog import prompt_for_api_key
            new_api_key = prompt_for_api_key(window)
            
            if not new_api_key:
                if logger:
                    logger.info("User cancelled API key setup")
                QMessageBox.information(
                    None, 
                    "Setup Required", 
                    "BlogsAI requires an OpenAI API key to function. "
                    "Please restart the application and provide a valid API key."
                )
                sys.exit(0)
            else:
                # Store the API key securely
                if config_manager.set_openai_api_key(new_api_key):
                    print("API key stored securely")
                    if logger:
                        logger.info("API key stored in secure storage")
                else:
                    print("Warning: Failed to store API key securely")
                    if logger:
                        logger.warning("Failed to store API key in secure storage")
        
        # Show main window
        window.show()
        
        if logger:
            logger.info("Application started successfully")
        
        # Run the application
        sys.exit(app.exec_())
        
    except Exception as e:
        error_msg = f"Critical error during application startup: {e}"
        print(error_msg)
        
        # Try to log the error using distribution-aware logging
        try:
            from blogsai.config.distribution import get_distribution_manager
            from blogsai.utils.logging_config import get_logger
            
            dist_manager = get_distribution_manager()
            logger = get_logger(__name__)
            logger.critical(error_msg, exc_info=True)
            
            # Also write to crash log
            crash_log = dist_manager.get_logs_directory() / 'crash.log'
            crash_log.parent.mkdir(parents=True, exist_ok=True)
            
            from datetime import datetime
            import traceback
            
            with open(crash_log, 'a') as f:
                f.write(f"\n=== CRASH at {datetime.now()} ===\n")
                f.write(f"Error: {e}\n")
                f.write(traceback.format_exc())
                f.write(f"Distribution info: {dist_manager.get_distribution_info()}\n")
                f.write("\n" + "="*50 + "\n")
            
            print(f"Error details written to: {crash_log}")
            
        except Exception as log_error:
            print(f"Failed to write error log: {log_error}")
        
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
