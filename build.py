#!/usr/bin/env python3
"""
Simple build script for BlogsAI desktop application.
Creates a standalone desktop app with light theme enforced.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def create_spec_file():
    """Create PyInstaller spec file."""
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Project root
project_root = Path.cwd()

block_cipher = None

# Include bundled resources (templates, defaults) - NO runtime data
data_dirs = [
    ('data/config', '_internal/config'),  # Bundled config templates
    ('assets', '_internal/assets'),       # Icons, themes, etc.
    ('blogsai/config/defaults', '_internal/defaults'),  # Default configurations
]

# DO NOT include runtime data:
# - No database files (*.db)
# - No logs directory  
# - No reports directory
# - No user data
# App should create these in proper OS app data directories

# Exclude unused Python stdlib modules to reduce bundle size
# Ultra-conservative - only exclude the safest modules
excludes = [
    # Unused GUI frameworks
    'tkinter', 'turtle', 'curses',
    # Development/testing modules  
    'unittest', 'doctest', 'pdb', 'profile', 'cProfile', 'pstats',
    # Build/packaging tools
    'distutils', 'setuptools', 'pip', 'ensurepip',
    # Unused audio/multimedia
    'audioop', 'wave', 'chunk', 'sunau', 'aifc',
    # Large scientific libraries (if not used)
    'numpy', 'scipy', 'matplotlib', 'pandas',
    # Removed unused dependencies
    'feedparser', 'schedule', 'sgmllib3k',
    # Alternative build tools (not needed at runtime)
    'cx_Freeze', 'nuitka', 'dmgbuild', 'ds_store', 'mac_alias',
    # Additional unused modules
    'antigravity', 'this', '__hello__', '__phello__',
    'idlelib', 'lib2to3', 'turtledemo',
]

a = Analysis(
    ['standalone_app_new.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=data_dirs,
    hiddenimports=[
        # PyQt5 components
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtPrintSupport',
        
        # GUI components
        'blogsai.gui.main_window',
        'blogsai.gui.setup_dialog',
        'blogsai.gui.api_key_dialog',
        'blogsai.gui.tabs.analysis_tab',
        'blogsai.gui.tabs.dashboard_tab',
        'blogsai.gui.tabs.collection_tab',
        'blogsai.gui.tabs.reports_tab',
        'blogsai.gui.workers.analysis_worker',
        'blogsai.gui.workers.base_worker',
        
        # Core and configuration (NEW DISTRIBUTION SYSTEM)
        'blogsai.core',
        'blogsai.config.config',
        'blogsai.config.distribution',      # NEW: Distribution manager
        'blogsai.config.env_manager',
        'blogsai.config.credential_manager',
        'blogsai.config.app_dirs',
        
        # Data processing
        'blogsai.scrapers.manager',
        'blogsai.scrapers.base',
        'blogsai.scrapers.government',
        'blogsai.scrapers.url_scraper',
        'blogsai.analysis.analyzer',
        'blogsai.analysis.openai_client',
        'blogsai.analysis.verifier',
        'blogsai.database.models',
        'blogsai.database.database',
        'blogsai.reporting.generator',
        
        # Utilities
        'blogsai.utils.logging_config',
        'blogsai.utils.error_handling',     # NEW: Error handling utilities
        'blogsai.utils.database_helpers',   # NEW: Database helpers
        'blogsai.utils.timezone_utils',     # NEW: Timezone utilities
        
        # External dependencies
        'sqlite3',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'openai',
        'pydantic',
        'yaml',
        'pytz',  # Timezone handling
        'dotenv',  # Environment variables
        
        # Secure storage dependencies
        'keyring',
        'keyring.backends',
        'keyring.backends.macOS',
        'keyring.backends.Windows', 
        'keyring.backends.SecretService',
        'keyring.backends.chainer',
        'keyring.backends.fail',
        'keyrings.alt',
        'keyrings.alt.file',
        'keyrings.alt.Gnome',
        'keyrings.alt.Google',
        'keyrings.alt.pyfs',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.hashes',
        
        # Platform utilities
        'platformdirs',
        'requests',
        'beautifulsoup4',
        'pathlib',
        'json',
        'base64',
        'hashlib',
        'getpass',
        
        # Web scraping dependencies
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common.exceptions',
        'webdriver_manager',
        'webdriver_manager.chrome',
        
        # Report generation dependencies
        'jinja2',
        'reportlab',
        'reportlab.lib',
        'reportlab.platypus',
        
        # Markdown extensions for HTML report generation
        'markdown.extensions',
        'markdown.extensions.tables',
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.extra',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hooks/runtime_distribution.py'],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove unnecessary Qt translations (keep English only)
def remove_qt_translations(datas):
    """Remove Qt translation files except English."""
    new_datas = []
    for dest, source, kind in datas:
        # Skip non-English Qt translations
        if 'translations' in dest and dest.endswith('.qm'):
            # Keep only English translations
            if any(lang in dest for lang in ['_en.qm', '_en_']):
                new_datas.append((dest, source, kind))
            # Skip all other language translations
        else:
            new_datas.append((dest, source, kind))
    return new_datas

# Remove unnecessary Qt plugins  
def remove_qt_plugins(binaries):
    """Remove unnecessary Qt plugins."""
    new_binaries = []
    for dest, source, kind in binaries:
        # Skip unused Qt plugins but keep essential ones
        # Only keep essential Qt plugins for BlogsAI
        keep_plugins = [
            'platforms/libqcocoa',        # macOS platform (essential for macOS)
            'platforms/libqwindows',      # Windows platform (essential for Windows)
            'imageformats/libqjpeg',      # JPEG support (common)
            'imageformats/libqpng',       # PNG support (common)
            'imageformats/libqgif',       # GIF support (common)
            'styles/libqfusion',          # Fusion style (cross-platform)
        ]
        
        # For Qt plugins, only keep the essential ones
        if any(plugin_type in dest for plugin_type in ['platforms/', 'imageformats/', 'styles/', 'generic/', 'iconengines/', 'printsupport/']):
            # This is a Qt plugin - only keep if it's in our keep list
            should_keep = any(keep_pattern in dest for keep_pattern in keep_plugins)
            if should_keep:
                new_binaries.append((dest, source, kind))
        else:
            # Not a Qt plugin - keep it
            new_binaries.append((dest, source, kind))
    
    return new_binaries

# Remove debug symbols and unnecessary files
def remove_debug_and_docs(datas):
    """Remove debug symbols, docs, and other unnecessary files."""
    new_datas = []
    for dest, source, kind in datas:
        # Skip debug symbols, docs, and examples
        skip_patterns = [
            '.pdb',       # Windows debug symbols
            '.dSYM/',     # macOS debug symbols  
            '/doc/',      # Documentation
            '/docs/',     # Documentation
            '/examples/', # Example files
            '/tests/',    # Test files
            '.md',        # Markdown files (except in config)
            'README',     # README files
            'CHANGELOG',  # Changelog files
            'LICENSE',    # License files (except main)
            '.txt',       # Text files (except prompts)
        ]
        
        should_skip = False
        for pattern in skip_patterns:
            if pattern in dest and 'config' not in dest:  # Keep config files
                should_skip = True
                break
        
        if not should_skip:
            new_datas.append((dest, source, kind))
    
    return new_datas

# Apply optimizations
a.datas = remove_qt_translations(a.datas)
a.datas = remove_debug_and_docs(a.datas)
a.binaries = remove_qt_plugins(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlogsAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,        # Strip debug symbols to reduce size
    upx=True,          # Compress with UPX  
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,       # Strip debug symbols
    upx=True,         # Compress with UPX
    upx_exclude=[
        # Exclude certain files from UPX compression if they cause issues
        'BlogsAI',    # Main executable
    ],
    name='BlogsAI',
)

app = BUNDLE(
    coll,
    name='BlogsAI.app',
    icon='assets/icon.icns',
    bundle_identifier='com.blogsai.app',
    info_plist={
        'CFBundleName': 'BlogsAI',
        'CFBundleDisplayName': 'BlogsAI',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIdentifier': 'com.blogsai.app',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': True,  # Force light mode
        # Privacy usage descriptions for macOS security
        'NSAppleEventsUsageDescription': 'BlogsAI needs access to system events for proper functionality.',
        'NSSystemAdministrationUsageDescription': 'BlogsAI needs to create application support directories.',
        # File system access
        'NSDocumentsFolderUsageDescription': 'BlogsAI may save reports to your Documents folder.',
        'NSDesktopFolderUsageDescription': 'BlogsAI may save reports to your Desktop.',
    },
)
'''
    
    with open('blogsai.spec', 'w') as f:
        f.write(spec_content)
    print("Created PyInstaller spec file")

def clean_build():
    """Clean previous build artifacts."""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"Cleaned {dir_name} directory")

def build_app():
    """Build the application using PyInstaller."""
    print("Building BlogsAI application...")
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller', 
            '--clean', 'blogsai.spec'
        ], check=True, capture_output=True, text=True)
        
        print("Build completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def create_distribution():
    """Create platform-specific distribution packages."""
    import platform
    
    system = platform.system().lower()
    
    if system == 'darwin':
        return create_macos_distribution()
    elif system == 'windows':
        return create_windows_distribution()
    elif system == 'linux':
        return create_linux_distribution()
    else:
        print(f"Unsupported platform: {system}")
        return False

def create_macos_distribution():
    """Create macOS distribution package."""
    if not Path('dist/BlogsAI.app').exists():
        print("No app bundle found to package")
        return False
    
    print("Creating macOS distribution package...")
    
    os.chdir('dist')
    
    # Create ZIP package
    result = subprocess.run([
        'zip', '-r', 'BlogsAI-macOS.zip', 'BlogsAI.app'
    ], capture_output=True, text=True)
    
    os.chdir('..')
    
    if result.returncode == 0:
        zip_path = Path('dist/BlogsAI-macOS.zip')
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"macOS distribution created: {zip_path} ({size_mb:.1f}MB)")
        return True
    else:
        print(f"Failed to create macOS ZIP: {result.stderr}")
        return False

def create_windows_distribution():
    """Create Windows distribution package."""
    if not Path('dist/BlogsAI').exists():
        print("No Windows executable found to package")
        return False
    
    print("Creating Windows distribution package...")
    
    os.chdir('dist')
    
    # Create ZIP package
    result = subprocess.run([
        'powershell', 'Compress-Archive', '-Path', 'BlogsAI', '-DestinationPath', 'BlogsAI-Windows.zip', '-Force'
    ], capture_output=True, text=True)
    
    os.chdir('..')
    
    if result.returncode == 0:
        zip_path = Path('dist/BlogsAI-Windows.zip')
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Windows distribution created: {zip_path} ({size_mb:.1f}MB)")
        return True
    else:
        print(f"Failed to create Windows ZIP: {result.stderr}")
        return False

def create_linux_distribution():
    """Create Linux distribution package."""
    if not Path('dist/BlogsAI').exists():
        print("No Linux executable found to package")
        return False
    
    print("Creating Linux distribution package...")
    
    os.chdir('dist')
    
    # Create tar.gz package
    result = subprocess.run([
        'tar', '-czf', 'BlogsAI-Linux.tar.gz', 'BlogsAI'
    ], capture_output=True, text=True)
    
    os.chdir('..')
    
    if result.returncode == 0:
        tar_path = Path('dist/BlogsAI-Linux.tar.gz')
        size_mb = tar_path.stat().st_size / (1024 * 1024)
        print(f"Linux distribution created: {tar_path} ({size_mb:.1f}MB)")
        return True
    else:
        print(f"Failed to create Linux tar.gz: {result.stderr}")
        return False

def clean_production_config():
    """Clean production config and credentials for first-time setup testing."""
    print("Cleaning production configuration for first-time setup testing...")
    
    try:
        # Clean macOS production config directory
        if sys.platform == 'darwin':
            config_dir = Path.home() / 'Library' / 'Preferences' / 'BlogsAI'
            if config_dir.exists():
                shutil.rmtree(config_dir)
                print(f"Removed production config: {config_dir}")
        
        # Clean Windows production config
        elif sys.platform == 'win32':
            config_dir = Path(os.getenv('APPDATA', '')) / 'BlogsAI'
            if config_dir.exists():
                shutil.rmtree(config_dir)
                print(f"Removed production config: {config_dir}")
        
        # Clean Linux production config  
        else:
            xdg_config = os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')
            config_dir = Path(xdg_config) / 'blogsai'
            if config_dir.exists():
                shutil.rmtree(config_dir)
                print(f"Removed production config: {config_dir}")
                
        # Clean API key from system keyring
        try:
            import keyring
            try:
                keyring.delete_password('BlogsAI', 'openai_api_key')
                print("Removed API key from system keyring")
            except keyring.errors.PasswordDeleteError:
                pass  # Key doesn't exist, that's fine
        except ImportError:
            print("Keyring not available - skipping API key cleanup")
            
    except Exception as e:
        print(f"Warning: Failed to clean production config: {e}")
        print("This won't affect the build, but first-time setup may not trigger")

def main():
    """Main build process."""
    print("Building BlogsAI Desktop Application")
    print("=" * 50)
    
    # Step 1: Clean previous builds
    clean_build()
    
    # Step 2: Clean production config for first-time setup testing
    clean_production_config()
    
    # Step 3: Create spec file
    create_spec_file()
    
    # Step 4: Build application
    if not build_app():
        sys.exit(1)
    
    # Step 5: Create distribution
    if not create_distribution():
        sys.exit(1)
    
    print("\n" + "="*50)
    print("BUILD COMPLETE!")
    print("="*50)
    print("Distribution package created in 'dist/' directory")
    print("\nThe application includes:")
    print("- Platform-specific data directories")
    print("- Secure credential storage")
    print("- Automatic configuration setup")
    print("- Professional desktop application experience")

if __name__ == "__main__":
    main()
