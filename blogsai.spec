# -*- mode: python ; coding: utf-8 -*-

import sys
import platform
from pathlib import Path

# Project root
project_root = Path.cwd()

block_cipher = None

# Windows-specific configuration
IS_WINDOWS = platform.system().lower() == 'windows'

# Include bundled resources (templates, defaults) - NO runtime data
data_dirs = []

# Add directories only if they exist and have content
from pathlib import Path as BuildPath
if BuildPath('data/config').exists() and any(BuildPath('data/config').iterdir()):
    data_dirs.append(('data/config', '_internal/config'))
if BuildPath('assets').exists():
    data_dirs.append(('assets', '_internal/assets'))
# Include defaults directory structure with explicit subdirectories
if BuildPath('blogsai/config/defaults').exists():
    # Include the main config files
    if BuildPath('blogsai/config/defaults/settings.yaml').exists():
        data_dirs.append(('blogsai/config/defaults/settings.yaml', '_internal/defaults/settings.yaml'))
    if BuildPath('blogsai/config/defaults/sources.yaml').exists():
        data_dirs.append(('blogsai/config/defaults/sources.yaml', '_internal/defaults/sources.yaml'))
    # we need to put prompts directory here too if it doesn't exist
    
    # Include all prompt files individually to ensure they get bundled properly
    if BuildPath('blogsai/config/defaults/prompts').exists():
        prompts_dir = BuildPath('blogsai/config/defaults/prompts')
        prompt_files = list(prompts_dir.glob('*.txt'))
        print(f"PyInstaller: Found {len(prompt_files)} prompt files in {prompts_dir}")
        for prompt_file in prompt_files:
            # Fix: Use relative path from project root to avoid Windows path issues
            relative_source = f'blogsai/config/defaults/prompts/{prompt_file.name}'
            destination = f'_internal/defaults/prompts/{prompt_file.name}'
            print(f"PyInstaller: Adding prompt file: {relative_source} -> {destination}")
            data_dirs.append((relative_source, destination))
    else:
        print(f"PyInstaller: WARNING - Prompts directory not found: blogsai/config/defaults/prompts")

# DO NOT include runtime data:
# - No database files (*.db)
# - No logs directory  
# - No reports directory

# Debug: Print all data files being included
print(f"PyInstaller: Total data files to include: {len(data_dirs)}")
for src, dest in data_dirs:
    print(f"PyInstaller: {src} -> {dest}")
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
    hooksconfig={},
    runtime_hooks=['hooks/runtime_distribution.py', 'hooks/runtime_windows_dll.py'],
    excludes=excludes,
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