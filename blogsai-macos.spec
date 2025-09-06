# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for macOS builds of BlogsAI.
This file is specifically optimized for macOS app bundle creation.
"""

import sys
import platform
from pathlib import Path

# Get the project root directory
import os
project_root = Path(os.getcwd())
block_cipher = None

# macOS-specific configuration
print("PyInstaller: Building macOS app bundle")

# Include bundled resources (templates, defaults) - NO runtime data
data_dirs = []

# Add directories only if they exist and have content
from pathlib import Path as BuildPath

# Include assets if they exist
if BuildPath('assets').exists():
    data_dirs.append(('assets', 'assets'))
    print(f"PyInstaller: Including assets directory")

# Include defaults directory for macOS
if BuildPath('blogsai/config/defaults').exists():
    data_dirs.append(('blogsai/config/defaults', 'blogsai/config/defaults'))
    print(f"PyInstaller: Including blogsai/config/defaults directory")

# Debug: Print all data files being included
print(f"PyInstaller: Total data files to include: {len(data_dirs)}")
for src, dest in data_dirs:
    print(f"PyInstaller: {src} -> {dest}")

# macOS-specific hidden imports - use detailed approach like main blogsai.spec
hiddenimports = [
    # PyQt5 components
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtPrintSupport',
    
    # GUI components - be more specific like main spec
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
    
    # Core modules
    'blogsai.core',
    'blogsai.database',
    'blogsai.analysis',
    'blogsai.reporting',
    'blogsai.scrapers',
    'blogsai.config',
    
    # Web scraping
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'webdriver_manager',
    'webdriver_manager.chrome',
    'requests',
    'urllib3',
    'bs4',
    
    # Data processing
    'pandas',
    'numpy',
    'sqlalchemy',
    'sqlalchemy.engine',
    'sqlalchemy.orm',
    'yaml',
    'jinja2',
    'reportlab',
    
    # Date/time handling
    'pytz',
    'blogsai.utils.timezone_utils',
    
    # macOS-specific
    'platformdirs',
    'keyring',
    'keyring.backends.macOS',
    
    # CLI
    'click',
]

# Modules to exclude to reduce bundle size and avoid conflicts
excludes = [
    # Unused GUI frameworks
    'tkinter',
    'matplotlib',
    'IPython',
    'jupyter',
    'notebook',
    
    # Development tools
    'pytest',
    'setuptools',
    'pip',
    'wheel',
    
    # Unused standard library modules
    'unittest',
    'doctest',
    'pdb',
    'profile',
    'cProfile',
    
    # Windows-specific modules
    'win32api',
    'win32gui',
    'winsound',
]

a = Analysis(
    ['standalone_app_new.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=data_dirs,
    # Include the entire blogsai package - don't include PyQt5 as package
    packages=['blogsai'],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

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
        # Keep essential Qt plugins for macOS
        keep_plugins = [
            'platforms/libqcocoa',        # macOS platform (essential for macOS)
            'imageformats/libqico',       # ICO image format
            'imageformats/libqjpeg',      # JPEG image format  
            'imageformats/libqpng',       # PNG image format
            'printsupport/libcocoaprintersupport', # macOS printing
        ]
        
        if any(plugin in dest for plugin in keep_plugins):
            new_binaries.append((dest, source, kind))
        elif 'Qt5' not in dest and 'qt' not in dest.lower():
            # Keep non-Qt binaries
            new_binaries.append((dest, source, kind))
    
    return new_binaries

def remove_debug_and_docs(datas):
    """Remove debug symbols, docs, and other unnecessary files."""
    new_datas = []
    for dest, source, kind in datas:
        # Skip debug symbols, docs, and examples
        skip_patterns = [
            '.dSYM/',     # macOS debug symbols  
            '/doc/',      # Documentation
            '/docs/',     # Documentation
            '/examples/', # Example files
            '/tests/',    # Test files
            '.md',        # Markdown files (except in config)
            'README',     # README files
            'LICENSE',    # License files (keep only essential ones)
            'CHANGELOG',  # Changelog files
        ]
        
        if not any(pattern in dest for pattern in skip_patterns):
            new_datas.append((dest, source, kind))
    
    return new_datas

# Apply optimizations
a.datas = remove_qt_translations(a.datas)
a.datas = remove_debug_and_docs(a.datas)
a.binaries = remove_qt_plugins(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# macOS: Use onedir mode for better performance
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
)

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

# Create macOS app bundle
app = BUNDLE(
    coll,
    name='BlogsAI.app',
    icon='assets/icon.icns',
    bundle_identifier='com.blogsai.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'BlogsAI Report',
                'CFBundleTypeIconFile': 'icon.icns',
                'LSItemContentTypes': ['public.html', 'public.json'],
                'LSHandlerRank': 'Owner'
            }
        ],
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHumanReadableCopyright': 'Copyright © 2024 BlogsAI',
        'LSMinimumSystemVersion': '10.13.0',
        
        # Privacy descriptions for macOS permissions
        'NSCameraUsageDescription': 'BlogsAI does not use the camera.',
        'NSMicrophoneUsageDescription': 'BlogsAI does not use the microphone.',
        'NSLocationUsageDescription': 'BlogsAI does not use location services.',
        'NSContactsUsageDescription': 'BlogsAI does not access contacts.',
        'NSCalendarsUsageDescription': 'BlogsAI does not access calendars.',
        'NSRemindersUsageDescription': 'BlogsAI does not access reminders.',
        'NSPhotoLibraryUsageDescription': 'BlogsAI does not access the photo library.',
        'NSAppleEventsUsageDescription': 'BlogsAI may use AppleEvents for system integration.',
        'NSNetworkVolumesUsageDescription': 'BlogsAI does not access network volumes.',
        'NSRemovableVolumesUsageDescription': 'BlogsAI does not access removable volumes.',
    },
)
