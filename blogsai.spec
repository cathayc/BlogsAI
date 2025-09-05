# -*- mode: python ; coding: utf-8 -*-

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
