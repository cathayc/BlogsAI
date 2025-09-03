"""
PyInstaller runtime hook for BlogsAI distribution system.
Ensures proper initialization of platform-specific directories.
"""

import os
import sys
from pathlib import Path

def initialize_distribution():
    """Initialize the distribution system early in the application lifecycle."""
    try:
        # Detect if we're running from a PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            # We're in a PyInstaller bundle
            bundle_dir = Path(sys._MEIPASS)
            
            # Set up environment to indicate we're in a bundle
            os.environ['BLOGSAI_BUNDLE'] = '1'
            os.environ['BLOGSAI_BUNDLE_DIR'] = str(bundle_dir)
            
            # Check for portable mode marker in the bundle directory or executable directory
            executable_dir = Path(sys.executable).parent
            portable_markers = [
                executable_dir / 'PORTABLE',
                executable_dir.parent / 'PORTABLE',  # For .app bundles
                bundle_dir / 'PORTABLE',
            ]
            
            for marker in portable_markers:
                if marker.exists():
                    os.environ['BLOGSAI_PORTABLE'] = '1'
                    break
            
            # Ensure the distribution manager can find bundled resources
            bundled_config = bundle_dir / '_internal' / 'config'
            if bundled_config.exists():
                os.environ['BLOGSAI_BUNDLED_CONFIG'] = str(bundled_config)
            
            bundled_assets = bundle_dir / '_internal' / 'assets'
            if bundled_assets.exists():
                os.environ['BLOGSAI_BUNDLED_ASSETS'] = str(bundled_assets)
                
            bundled_defaults = bundle_dir / '_internal' / 'defaults'
            if bundled_defaults.exists():
                os.environ['BLOGSAI_BUNDLED_DEFAULTS'] = str(bundled_defaults)
        
        # Import and initialize the distribution manager early
        # This ensures platform-specific directories are set up before any other imports
        try:
            from blogsai.config.distribution import get_distribution_manager
            dist_manager = get_distribution_manager()
            
            # Ensure all directories exist
            dist_manager.get_data_directory()
            dist_manager.get_config_directory()
            dist_manager.get_cache_directory()
            dist_manager.get_logs_directory()
            
        except ImportError:
            # Distribution manager not available yet, that's OK
            pass
            
    except Exception as e:
        # Don't let initialization errors break the app
        print(f"Warning: Distribution initialization failed: {e}")

# Run initialization
initialize_distribution()
