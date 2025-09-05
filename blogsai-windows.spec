# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Windows builds of BlogsAI.
This file is specifically optimized for Windows executable creation.
"""

import sys
import platform
from pathlib import Path

# Get the project root directory
project_root = Path(__file__).parent
block_cipher = None

# Windows-specific configuration
print("PyInstaller: Building Windows executable")

# Include bundled resources (templates, defaults) - NO runtime data
data_dirs = []

# Add directories only if they exist and have content
from pathlib import Path as BuildPath

# Include assets if they exist
if BuildPath('assets').exists():
    data_dirs.append(('assets', '_internal/assets'))
    print(f"PyInstaller: Including assets directory")

# Include defaults directory structure with explicit subdirectories for Windows
if BuildPath('blogsai/config/defaults').exists():
    print(f"PyInstaller: Found blogsai/config/defaults directory")
    
    # Include the main config files
    if BuildPath('blogsai/config/defaults/settings.yaml').exists():
        data_dirs.append(('blogsai/config/defaults/settings.yaml', '_internal/defaults/settings.yaml'))
        print(f"PyInstaller: Including settings.yaml")
    if BuildPath('blogsai/config/defaults/sources.yaml').exists():
        data_dirs.append(('blogsai/config/defaults/sources.yaml', '_internal/defaults/sources.yaml'))
        print(f"PyInstaller: Including sources.yaml")
    
    # Include all prompt files individually to ensure they get bundled properly
    if BuildPath('blogsai/config/defaults/prompts').exists():
        prompts_dir = BuildPath('blogsai/config/defaults/prompts')
        prompt_files = list(prompts_dir.glob('*.txt'))
        print(f"PyInstaller: Found {len(prompt_files)} prompt files in {prompts_dir}")
        for prompt_file in prompt_files:
            print(f"PyInstaller: Adding prompt file: {prompt_file} -> _internal/defaults/prompts/{prompt_file.name}")
            data_dirs.append((str(prompt_file), f'_internal/defaults/prompts/{prompt_file.name}'))
    else:
        print(f"PyInstaller: WARNING - Prompts directory not found: blogsai/config/defaults/prompts")
else:
    print(f"PyInstaller: WARNING - Defaults directory not found: blogsai/config/defaults")

# Debug: Print all data files being included
print(f"PyInstaller: Total data files to include: {len(data_dirs)}")
for src, dest in data_dirs:
    print(f"PyInstaller: {src} -> {dest}")

# Windows-specific hidden imports
hiddenimports = [
    # PyQt5 components
    'PyQt5.QtCore',
    'PyQt5.QtGui', 
    'PyQt5.QtWidgets',
    'PyQt5.QtPrintSupport',
    
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
    
    # Windows-specific
    'win32api',
    'win32gui',
    'platformdirs',
    'keyring',
    'keyring.backends.Windows',
    
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
    
    # Potential ABI conflict modules for Windows
    '_decimal',
    '_multiprocessing',
    'multiprocessing.dummy',
]

a = Analysis(
    ['standalone_app_new.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=data_dirs,
    # Include the entire blogsai package
    packages=['blogsai'],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hooks/runtime_windows_dll.py'],
    excludes=excludes,
    win_no_prefer_redirects=False,  # Removed deprecated option
    win_private_assemblies=False,   # Removed deprecated option  
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
        # Skip unused Qt plugins but keep essential ones
        # Only keep essential Qt plugins for BlogsAI
        keep_plugins = [
            'platforms/qwindows',         # Windows platform (essential for Windows)
            'imageformats/qico',          # ICO image format
            'imageformats/qjpeg',         # JPEG image format  
            'imageformats/qpng',          # PNG image format
            'printsupport/windowsprintersupport', # Windows printing
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
            '.pdb',       # Windows debug symbols
            '/doc/',      # Documentation
            '/docs/',     # Documentation
            '/examples/', # Example files
            '/tests/',    # Test files
            '.md',        # Markdown files (except in config)
            'README',     # README files
            'LICENSE',    # License files (keep only essential ones)
            'CHANGELOG',  # Changelog files
            '.txt',       # Text files (except prompts)
        ]
        
        # Special handling for prompts - keep these text files
        if 'prompts' in dest and dest.endswith('.txt'):
            new_datas.append((dest, source, kind))
        elif not any(pattern in dest for pattern in skip_patterns):
            new_datas.append((dest, source, kind))
    
    return new_datas

# Apply optimizations
a.datas = remove_qt_translations(a.datas)
a.datas = remove_debug_and_docs(a.datas)
a.binaries = remove_qt_plugins(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Windows: Use onefile mode to avoid DLL issues
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
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
    target_arch='x86_64',  # Explicitly target 64-bit
    codesign_identity=None,
    entitlements_file=None,
)
