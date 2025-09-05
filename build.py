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

def ensure_build_directories():
    """Create necessary directories for PyInstaller build."""
    print("Creating necessary build directories...")
    
    # Directories that PyInstaller expects to exist
    directories_to_create = [
        'data/config',
        'assets',
        'blogsai/config/defaults',
        'hooks',
    ]
    
    for directory in directories_to_create:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
        else:
            print(f"Directory already exists: {directory}")

def create_spec_file():
    """Create PyInstaller spec file."""
    
    # Detect if we're on Windows to use onefile mode
    import platform
    is_windows = platform.system().lower() == 'windows'
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Project root
project_root = Path.cwd()

block_cipher = None

# Windows-specific configuration
IS_WINDOWS = ''' + str(is_windows) + '''

# Include bundled resources (templates, defaults) - NO runtime data
data_dirs = []

# Add directories only if they exist and have content
from pathlib import Path as BuildPath
if BuildPath('data/config').exists() and any(BuildPath('data/config').iterdir()):
    data_dirs.append(('data/config', '_internal/config'))
if BuildPath('assets').exists():
    data_dirs.append(('assets', '_internal/assets'))
if BuildPath('blogsai/config/defaults').exists():
    data_dirs.append(('blogsai/config/defaults', '_internal/defaults'))

# DO NOT include runtime data:
# - No database files (*.db)
# - No logs directory  
# - No reports directory
# - No user data
# App should create these in proper OS app data directories

# Exclude unused Python stdlib modules to reduce bundle size
# Include modules that commonly cause Windows ABI/FFI issues
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
    # WINDOWS ABI FIX: Exclude modules that commonly cause DLL/FFI issues
    # Let PyInstaller handle these automatically to avoid version conflicts
    '_decimal',     # Can have ABI issues with different builds
    '_multiprocessing',  # Complex FFI that can cause issues
    'multiprocessing.dummy',  # Threading conflicts
]

a = Analysis(
    ['standalone_app_new.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=data_dirs,
    # Include the entire blogsai package
    packages=['blogsai'],
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
        'blogsai.gui.workers.scraping_worker',
        'blogsai.gui.dialogs.first_time_setup_dialog',
        'blogsai.gui.dialogs.article_dialog',
        'blogsai.gui.dialogs.manual_article_dialog',
        'blogsai.gui.dialogs.report_dialog',
        
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
        'blogsai.scrapers.doj_scraper',
        'blogsai.scrapers.sec_scraper',
        'blogsai.scrapers.cftc_scraper',
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
        
        # Windows-specific DLL and runtime imports - MINIMAL SET
        # Only include absolutely essential modules to avoid ABI conflicts
        'encodings.utf_8',
        'encodings.ascii', 
        'encodings.cp1252',
        'msvcrt',
        'winreg',
        '_winapi',
        'nt',
    ],
    hookspath=['hooks'],
    hooksconfig={{}},
    runtime_hooks=['hooks/runtime_distribution.py', 'hooks/runtime_windows_dll.py'],
    excludes=excludes,
    win_no_prefer_redirects=True,   # WINDOWS FIX: Helps with DLL loading
    win_private_assemblies=True,    # WINDOWS FIX: Include private assemblies  
    cipher=block_cipher,
    noarchive=False,
    # Additional Windows ABI/FFI fixes
    optimize=0,                     # Don't optimize bytecode - can cause issues
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

# Windows: Use onefile mode to avoid DLL issues
# macOS/Linux: Use onedir mode for better performance
if IS_WINDOWS:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,      # Include binaries in onefile for Windows
        a.zipfiles,
        a.datas,
        [],
        name='BlogsAI',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,     # Don't strip - causes DLL issues on Windows
        upx=False,       # Don't use UPX - causes DLL issues on Windows  
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch='x86_64',  # EXPLICIT 64-bit targeting to avoid ABI issues
        codesign_identity=None,
        entitlements_file=None,
        icon='assets/icon.ico' if Path('assets/icon.ico').exists() else None,
    )
else:
    # macOS/Linux: Use traditional onedir mode
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='BlogsAI',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

# Only create COLLECT for non-Windows (onedir mode)
if not IS_WINDOWS:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='BlogsAI',
    )

# Only create BUNDLE for macOS
if not IS_WINDOWS and sys.platform == 'darwin':
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
    # Check for both onefile and onedir structures
    onefile_exe = Path('dist/BlogsAI.exe')
    onedir_folder = Path('dist/BlogsAI')
    
    if onefile_exe.exists():
        # Onefile mode - just zip the single executable
        print("Creating Windows distribution package (onefile mode)...")
        
        os.chdir('dist')
        
        # Create ZIP package with the single executable
        result = subprocess.run([
            'powershell', 'Compress-Archive', '-Path', 'BlogsAI.exe', '-DestinationPath', 'BlogsAI-Windows.zip', '-Force'
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
            
    elif onedir_folder.exists():
        # Onedir mode - zip the entire folder
        print("Creating Windows distribution package (onedir mode)...")
        
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
    else:
        print("No Windows executable found to package")
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
    
    # Ensure current directory is in Python path for build
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        print(f"Added {project_root} to Python path")
    
    # Step 1: Clean previous builds
    clean_build()
    
    # Step 2: Ensure necessary directories exist
    ensure_build_directories()
    
    # Step 3: Clean production config for first-time setup testing
    clean_production_config()
    
    # Step 4: Create spec file
    create_spec_file()
    
    # Step 5: Build application
    if not build_app():
        sys.exit(1)
    
    # Step 6: Create distribution
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
