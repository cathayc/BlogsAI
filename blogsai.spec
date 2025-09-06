# -*- mode: python ; coding: utf-8 -*-
# 
# SIMPLIFIED SPEC FILE - FOR REFERENCE ONLY
# The main build process now uses command line --add-data options in build.py
# This file is kept for reference and potential fallback usage
#

import sys
import platform
from pathlib import Path

# Project root
project_root = Path.cwd()

block_cipher = None

# NOTE: Data files are now handled via command line --add-data options in build.py
# This spec file no longer includes complex data handling logic

# Exclude unused Python stdlib modules to reduce bundle size
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
    # Modules that can cause ABI issues
    '_decimal',
    '_multiprocessing',
    'multiprocessing.dummy',
]

# Basic Analysis configuration - data files handled by build.py
a = Analysis(
    ['standalone_app_new.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],  # Data files handled by command line --add-data
    packages=['blogsai'],
    hiddenimports=[
        # Core PyQt5 components
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'PyQt5.QtPrintSupport',
        
        # Essential blogsai modules
        'blogsai.gui.main_window',
        'blogsai.config.config',
        'blogsai.config.distribution',
        'blogsai.database.database',
        'blogsai.scrapers.manager',
        'blogsai.analysis.analyzer',
        'blogsai.reporting.generator',
        
        # External dependencies
        'sqlite3',
        'sqlalchemy',
        'openai',
        'yaml',
        'keyring',
        'cryptography',
        'requests',
        'beautifulsoup4',
        'selenium',
        'jinja2',
        'reportlab',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['hooks/runtime_distribution.py', 'hooks/runtime_windows_dll.py'],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use onedir mode for all platforms (as per new approach)
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

# macOS app bundle
if sys.platform == 'darwin':
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
            'NSRequiresAquaSystemAppearance': True,
        },
    )