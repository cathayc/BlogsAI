#!/usr/bin/env python3
"""
Standalone entry point for BlogsAI desktop application.
Uses proper platform-specific directories for all user data.
"""

import os
import sys
from pathlib import Path

def main():
    """Main application entry point."""
    print("Starting BlogsAI Desktop Application...")
    
    try:
        # Ensure blogsai package is available
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Import our platform-aware app directories
        from blogsai.config.app_dirs import app_dirs
        
        # Initialize platform-specific directories
        print("Setting up application directories...")
        app_dirs.ensure_directories()
        app_dirs.setup_environment_variables()
        app_dirs.print_setup_info()
        
        # Setup logging early using the proper logs directory
        try:
            from blogsai.utils.logging_config import setup_logging, setup_exception_logging, get_logger
            log_file = setup_logging()
            setup_exception_logging()
            
            # Get the actual logger instance
            logger = get_logger(__name__)
            logger.info("=== BlogsAI Application Starting ===")
            logger.info(f"Python version: {sys.version}")
            logger.info(f"Platform: {sys.platform}")
            logger.info(f"Running from: {sys.argv[0]}")
            if hasattr(sys, '_MEIPASS'):
                logger.info(f"PyInstaller bundle: {sys._MEIPASS}")
            logger.info(f"App data directory: {app_dirs.app_data_dir}")
            logger.info(f"App config directory: {app_dirs.app_config_dir}")
            logger.info(f"Database path: {app_dirs.database_path}")
        except Exception as e:
            print(f"Warning: Failed to set up logging: {e}")
            logger = None
        
        # Initialize user configuration from bundled defaults
        print("Initializing user configuration...")
        try:
            app_dirs.initialize_user_config()
        except Exception as e:
            print(f"Warning: Failed to initialize config: {e}")
            if logger:
                logger.warning(f"Config initialization failed: {e}")
        
        # Initialize database
        print("Initializing database...")
        try:
            app_dirs.initialize_database()
            
            # Apply database migrations if needed
            from blogsai.database.database import migrate_database
            migrate_database()
            print("Database setup complete")
        except Exception as e:
            print(f"Warning: Database initialization failed: {e}")
            if logger:
                logger.error(f"Database initialization failed: {e}")
            
            # If database initialization failed, try to create basic schema
            print("Attempting to create database schema...")
            try:
                app_dirs._create_database_schema()
                print("Database schema created successfully")
            except Exception as schema_error:
                print(f"Failed to create database schema: {schema_error}")
                if logger:
                    logger.error(f"Database schema creation failed: {schema_error}")
        
        print("Environment variables set:")
        print(f"  BLOGSAI_DATA_DIR: {os.getenv('BLOGSAI_DATA_DIR')}")
        print(f"  BLOGSAI_DB_PATH: {os.getenv('BLOGSAI_DB_PATH')}")
        print(f"  BLOGSAI_CONFIG_DIR: {os.getenv('BLOGSAI_CONFIG_DIR')}")
        print(f"  BLOGSAI_PROMPTS_DIR: {os.getenv('BLOGSAI_PROMPTS_DIR')}")
        print(f"  BLOGSAI_LOGS_DIR: {os.getenv('BLOGSAI_LOGS_DIR')}")
        
        print("Launching application...")
        
        if logger:
            logger.info("Starting GUI components import...")
        
        # Import GUI components
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPalette, QColor
        
        if logger:
            logger.info("PyQt5 imported successfully")
            logger.info("Importing MainWindow...")
        
        from blogsai.gui.main_window import MainWindow
        
        if logger:
            logger.info("MainWindow imported successfully")
            logger.info("Creating QApplication...")
        
        # Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("BlogsAI")
        app.setOrganizationName("BlogsAI")
        app.setOrganizationDomain("blogsai.com")
        
        if logger:
            logger.info("QApplication created successfully")
            logger.info("Setting up application style...")
        
        # Set a modern style
        app.setStyle('Fusion')
        
        # Custom color palette
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
        
        if logger:
            logger.info("Creating main window...")
        
        # Create and show main window
        window = MainWindow()
        
        if logger:
            logger.info("Main window created, checking API key...")
        
        # Check for API key before showing main window
        from blogsai.config.env_manager import EnvironmentManager
        env_manager = EnvironmentManager(str(app_dirs.app_data_dir))
        
        if not env_manager.has_valid_api_key():
            if logger:
                logger.info("No valid API key found, showing setup dialog...")
            
            from blogsai.gui.api_key_dialog import prompt_for_api_key
            api_key = prompt_for_api_key(window)
            
            if not api_key:
                if logger:
                    logger.info("User cancelled API key setup, exiting...")
                QMessageBox.information(
                    None, 
                    "Setup Required", 
                    "BlogsAI requires an OpenAI API key to function. "
                    "Please restart the application and provide a valid API key."
                )
                sys.exit(0)
            else:
                if logger:
                    logger.info("API key configured successfully")
        
        if logger:
            logger.info("Showing main window...")
        
        window.show()
        
        if logger:
            logger.info("Starting application event loop...")
        
        # Run the application
        sys.exit(app.exec_())
        
    except Exception as e:
        error_msg = f"Critical error during application startup: {e}"
        print(error_msg)
        
        # Try to log the error
        try:
            from blogsai.utils.logging_config import get_logger
            logger = get_logger(__name__)
            logger.critical(error_msg, exc_info=True)
        except:
            pass
        
        import traceback
        traceback.print_exc()
        
        # Write error to a file as fallback
        try:
            from datetime import datetime
            error_file = app_dirs.app_logs_dir / 'crash.log'
            error_file.parent.mkdir(parents=True, exist_ok=True)
            with open(error_file, 'a') as f:
                f.write(f"\n=== CRASH at {datetime.now()} ===\n")
                f.write(f"Error: {e}\n")
                f.write(traceback.format_exc())
                f.write("\n" + "="*50 + "\n")
            print(f"Error details written to: {error_file}")
        except Exception as write_error:
            print(f"Failed to write error log: {write_error}")
        
        sys.exit(1)


def get_platform_data_dir():
    """Get the platform-specific default data directory."""
    import platformdirs
    return platformdirs.user_data_dir("BlogsAI", "BlogsAI")


def change_data_directory(new_path):
    """Change the data directory location by moving all data to the new location."""
    import shutil
    import os
    from pathlib import Path
    
    # Get current data directory
    current_path = os.getenv('BLOGSAI_DATA_DIR')
    if not current_path:
        raise Exception("Current data directory not found in environment variables")
    
    current_path = Path(current_path)
    new_path = Path(new_path)
    
    # Ensure new directory exists
    new_path.mkdir(parents=True, exist_ok=True)
    
    # If current path exists and is different from new path, move the data
    if current_path.exists() and current_path != new_path:
        # Copy all contents from current to new location
        for item in current_path.iterdir():
            if item.is_file():
                shutil.copy2(item, new_path / item.name)
            elif item.is_dir():
                shutil.copytree(item, new_path / item.name, dirs_exist_ok=True)
        
        print(f"Data moved from {current_path} to {new_path}")
    
    # Update environment variables for current session
    os.environ['BLOGSAI_DATA_DIR'] = str(new_path)
    os.environ['BLOGSAI_DB_PATH'] = str(new_path / "blogsai.db")
    os.environ['BLOGSAI_CONFIG_DIR'] = str(new_path)
    os.environ['BLOGSAI_PROMPTS_DIR'] = str(new_path / "prompts")
    os.environ['BLOGSAI_LOGS_DIR'] = str(new_path / "logs")
    
    # Create configuration files to persist the new location for future runs
    # Only write to essential locations (not the old default location)
    config_locations = [
        new_path / ".blogsai_config",  # In the data directory itself
        Path.home() / ".blogsai_config",  # In user home directory (global pointer)
    ]
    
    for config_file in config_locations:
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                f.write(f"data_dir={new_path}\n")
            print(f"Config saved to: {config_file}")
        except Exception as e:
            print(f"Warning: Could not save config to {config_file}: {e}")
    
    # Clean up old config files in the previous default location to avoid confusion
    import platformdirs
    old_default_location = Path(platformdirs.user_data_dir("BlogsAI", "BlogsAI"))
    if old_default_location != new_path:
        old_config_file = old_default_location / ".blogsai_config"
        if old_config_file.exists():
            try:
                old_config_file.unlink()
                print(f"Cleaned up old config: {old_config_file}")
            except Exception as e:
                print(f"Warning: Could not remove old config {old_config_file}: {e}")
    
    print(f"Data directory changed to: {new_path}")


if __name__ == '__main__':
    main()
