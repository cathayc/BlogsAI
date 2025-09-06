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

# macOS-specific hidden imports with comprehensive PyQt5 coverage
hiddenimports = [
    # PyQt5 - comprehensive manual approach
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui', 
    'PyQt5.QtWidgets',
    'PyQt5.QtPrintSupport',
    'PyQt5.sip',
    
    # Force include all PyQt5.QtWidgets classes used in the app
    'PyQt5.QtWidgets.QWidget',
    'PyQt5.QtWidgets.QMainWindow',
    'PyQt5.QtWidgets.QApplication',
    'PyQt5.QtWidgets.QVBoxLayout',
    'PyQt5.QtWidgets.QHBoxLayout',
    'PyQt5.QtWidgets.QGridLayout',
    'PyQt5.QtWidgets.QTabWidget',
    'PyQt5.QtWidgets.QLabel',
    'PyQt5.QtWidgets.QPushButton',
    'PyQt5.QtWidgets.QTextEdit',
    'PyQt5.QtWidgets.QLineEdit',
    'PyQt5.QtWidgets.QComboBox',
    'PyQt5.QtWidgets.QCheckBox',
    'PyQt5.QtWidgets.QProgressBar',
    'PyQt5.QtWidgets.QMessageBox',
    'PyQt5.QtWidgets.QDialog',
    'PyQt5.QtWidgets.QFileDialog',
    'PyQt5.QtWidgets.QTableWidget',
    'PyQt5.QtWidgets.QTableWidgetItem',
    'PyQt5.QtWidgets.QHeaderView',
    'PyQt5.QtWidgets.QSplitter',
    'PyQt5.QtWidgets.QScrollArea',
    'PyQt5.QtWidgets.QFrame',
    'PyQt5.QtWidgets.QGroupBox',
    'PyQt5.QtWidgets.QSpacerItem',
    'PyQt5.QtWidgets.QSizePolicy',
    
    # PyQt5 Core classes
    'PyQt5.QtCore.QObject',
    'PyQt5.QtCore.QThread',
    'PyQt5.QtCore.QTimer',
    'PyQt5.QtCore.pyqtSignal',
    'PyQt5.QtCore.pyqtSlot',
    'PyQt5.QtCore.Qt',
    
    # PyQt5 GUI classes
    'PyQt5.QtGui.QIcon',
    'PyQt5.QtGui.QPixmap',
    'PyQt5.QtGui.QFont',
    'PyQt5.QtGui.QPalette',
    'PyQt5.QtGui.QColor',
    
    # GUI components
    'blogsai.gui.main_window',
    'blogsai.gui.tabs',
    'blogsai.gui.dialogs',
    'blogsai.gui.workers',
    
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
    # Include the entire blogsai package and PyQt5
    packages=['blogsai', 'PyQt5'],
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
