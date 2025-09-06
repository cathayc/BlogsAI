#!/usr/bin/env python3
"""
Build script for BlogsAI Desktop Application.
Handles cross-platform builds with PyInstaller, including Windows DLL fixes.
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

def get_data_mappings():
    """Get data file mappings for --add-data options."""
    data_dirs = []
    
    # Add directories only if they exist and have content
    if Path('data/config').exists() and any(Path('data/config').iterdir()):
        data_dirs.append(('data/config', 'config'))
    if Path('assets').exists():
        data_dirs.append(('assets', 'assets'))
    
    # Include defaults directory structure explicitly
    if Path('blogsai/config/defaults').exists():
        defaults_dir = Path('blogsai/config/defaults')
        
        # Always include settings.yaml and sources.yaml
        settings_file = defaults_dir / 'settings.yaml'
        if settings_file.exists():
            data_dirs.append((str(settings_file), 'defaults/settings.yaml'))
            print(f"PyInstaller: Adding settings.yaml")
        
        sources_file = defaults_dir / 'sources.yaml'
        if sources_file.exists():
            data_dirs.append((str(sources_file), 'defaults/sources.yaml'))
            print(f"PyInstaller: Adding sources.yaml")
        
        # Include the entire prompts directory to preserve structure
        prompts_dir = defaults_dir / 'prompts'
        if prompts_dir.exists():
            # Include the entire prompts directory to ensure proper nested structure
            # This prevents PyInstaller from creating directories instead of files
            data_dirs.append((str(prompts_dir), 'defaults/prompts'))
            print(f"PyInstaller: Adding entire prompts directory: {prompts_dir}")
        else:
            print(f"PyInstaller: WARNING - Prompts directory not found: {prompts_dir}")
    else:
        print(f"PyInstaller: WARNING - Defaults directory not found: blogsai/config/defaults")
    
    print(f"PyInstaller: Total data files to include: {len(data_dirs)}")
    return data_dirs

def get_hidden_imports():
    """Get list of hidden imports for PyInstaller."""
    return [
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
        
        # Core and configuration
        'blogsai.core',
        'blogsai.config.config',
        'blogsai.config.distribution',
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
        'blogsai.utils.error_handling',
        'blogsai.utils.database_helpers',
        'blogsai.utils.timezone_utils',
        
        # External dependencies
        'sqlite3',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'openai',
        'pydantic',
        'yaml',
        'pytz',
        'dotenv',
        
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
        
        # Platform-specific imports
        'encodings.utf_8',
        'encodings.ascii',
        'encodings.cp1252',
        'msvcrt',
        'winreg',
        '_winapi',
        'nt',
    ]

def get_platform_icon():
    """Get platform-specific icon path."""
    system = platform.system().lower()
    if system == 'windows':
        return 'assets/icon.ico' if Path('assets/icon.ico').exists() else None
    elif system == 'darwin':
        return 'assets/icon.icns' if Path('assets/icon.icns').exists() else None
    else:
        return 'assets/icon.png' if Path('assets/icon.png').exists() else None

def ensure_directories():
    """Ensure required directories exist."""
    directories = ['build', 'dist', 'hooks']
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
        else:
            print(f"Directory already exists: {directory}")

def clean_build():
    """Clean previous build artifacts."""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"Cleaned {dir_name} directory")

def build_app():
    """Build the application using PyInstaller command line with --add-data options."""
    try:
        print("Building with PyInstaller command line --add-data approach...")
        
        # Build the PyInstaller command with --add-data options
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            'standalone_app_new.py',
            '--name', 'BlogsAI',
            '--clean',
            '--noconfirm',
            '--noconsole',
        ]
        
        # Use different modes for different platforms
        if platform.system().lower() == 'windows':
            cmd.append('--onefile')  # Windows: use onefile for simpler distribution
            print("Using --onefile mode for Windows")
        else:
            cmd.append('--onedir')   # macOS/Linux: use onedir for better performance
            print("Using --onedir mode for macOS/Linux")
        
        # Add Windows-specific DLL handling options
        if platform.system().lower() == 'windows':
            cmd.extend([
                '--noupx',              # Disable UPX compression (causes DLL issues)
                '--target-arch=x86_64', # Explicit 64-bit targeting
            ])
            
            # Only collect essential DLL packages (reduced from full --collect-all)
            cmd.extend([
                '--collect-binaries', 'cryptography',   # Only binaries, not all files
                '--collect-binaries', 'keyring',        # Only binaries, not all files
                '--hidden-import', 'PyQt5.sip',        # Essential PyQt5 import
            ])
            
            # Add specific Windows runtime DLL handling (only essential DLLs)
            python_dir = os.path.dirname(sys.executable)
            python_dll = os.path.join(python_dir, 'python311.dll')
            
            # Explicitly include Python DLL if it exists
            if os.path.exists(python_dll):
                cmd.extend(['--add-binary', f'{python_dll};.'])
                print(f"Adding Python DLL: {python_dll}")
            
            # Only include the most critical Windows runtime DLLs
            critical_dlls = ['vcruntime140.dll']  # Reduced list
            for dll_name in critical_dlls:
                dll_path = os.path.join(python_dir, dll_name)
                if os.path.exists(dll_path):
                    cmd.extend(['--add-binary', f'{dll_path};.'])
                    print(f"Adding critical DLL: {dll_name}")
            
            # Add Qt optimization for Windows to reduce size
            cmd.extend([
                '--exclude-module', 'PyQt5.QtTest',        # Testing framework
                '--exclude-module', 'PyQt5.QtDesigner',    # Designer tools
                '--exclude-module', 'PyQt5.QtHelp',        # Help system
                '--exclude-module', 'PyQt5.QtMultimedia',  # Multimedia
                '--exclude-module', 'PyQt5.QtNetwork',     # Network (if not needed)
                '--exclude-module', 'PyQt5.QtOpenGL',      # OpenGL
                '--exclude-module', 'PyQt5.QtSql',         # SQL widgets
                '--exclude-module', 'PyQt5.QtSvg',         # SVG support
                '--exclude-module', 'PyQt5.QtWebKit',      # WebKit
                '--exclude-module', 'PyQt5.QtWebKitWidgets', # WebKit widgets
                '--exclude-module', 'PyQt5.QtXml',         # XML processing
            ])
            
            print("Added optimized Windows DLL handling (reduced size)")
            print("Added Qt module exclusions for size optimization")
        
        # Add data files using --add-data command line options
        data_mappings = get_data_mappings()
        for source, dest in data_mappings:
            cmd.extend(['--add-data', f'{source}{os.pathsep}{dest}'])
            print(f"Adding data: {source} -> {dest}")
        
        # Add hidden imports
        hidden_imports = get_hidden_imports()
        for import_name in hidden_imports:
            cmd.extend(['--hidden-import', import_name])
        
        # Add Windows-specific excludes to reduce size and avoid DLL conflicts
        if platform.system().lower() == 'windows':
            windows_excludes = [
                # Core modules that cause issues
                '_decimal', '_multiprocessing', 'multiprocessing.dummy',
                # GUI frameworks
                'tkinter', 'turtle', 'curses',
                # Large scientific libraries
                'numpy', 'scipy', 'matplotlib', 'pandas',
                # Development tools
                'unittest', 'doctest', 'pdb', 'profile', 'cProfile',
                # Build tools
                'distutils', 'setuptools', 'pip', 'ensurepip',
                # Unused multimedia
                'audioop', 'wave', 'chunk', 'sunau', 'aifc',
                # Alternative packaging
                'cx_Freeze', 'nuitka', 'py2exe',
                # Test frameworks
                'pytest', 'nose', 'mock',
                # Documentation
                'sphinx', 'docutils',
            ]
            for exclude in windows_excludes:
                cmd.extend(['--exclude-module', exclude])
            print(f"Added {len(windows_excludes)} Windows module excludes for size optimization")
        
        # Add runtime hooks
        cmd.extend(['--runtime-hook', 'hooks/runtime_distribution.py'])
        cmd.extend(['--runtime-hook', 'hooks/runtime_windows_dll.py'])
        
        # Add icon based on platform
        icon_path = get_platform_icon()
        if icon_path and Path(icon_path).exists():
            cmd.extend(['--icon', icon_path])
        
        print(f"Running PyInstaller command...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print("PyInstaller build completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def create_windows_distribution():
    """Create Windows distribution package."""
    print("Creating Windows distribution...")
    
    # Check for onefile executable first (Windows)
    exe_path = Path('dist/BlogsAI.exe')
    if exe_path.exists():
        # We have onefile mode - zip the executable
        zip_path = Path('dist/BlogsAI-Windows.zip')
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(exe_path, 'BlogsAI.exe')
        
        print(f"Created Windows distribution: {zip_path}")
        return True
    
    # Fallback: check for onedir mode
    dir_path = Path('dist/BlogsAI')
    if dir_path.exists():
        # We have onedir mode - zip the directory
        zip_path = Path('dist/BlogsAI-Windows.zip')
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(dir_path.parent)
                    zipf.write(file_path, arcname)
        
        print(f"Created Windows distribution: {zip_path}")
        return True
    
    print("ERROR: No built executable or directory found")
    return False

def create_macos_distribution():
    """Create macOS distribution package."""
    print("Creating macOS distribution...")
    
    app_path = Path('dist/BlogsAI.app')
    if app_path.exists():
        # Create ZIP of the .app bundle
        zip_path = Path('dist/BlogsAI-macOS.zip')
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in app_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(app_path.parent)
                    zipf.write(file_path, arcname)
        
        print(f"Created macOS distribution: {zip_path}")
        return True
    
    print("ERROR: No built .app bundle found")
    return False

def create_distribution():
    """Create platform-specific distribution."""
    system = platform.system().lower()
    
    if system == 'windows':
        return create_windows_distribution()
    elif system == 'darwin':
        return create_macos_distribution()
    else:
        print("Linux distribution not implemented yet")
        return True

def clean_production_config():
    """Remove production config to ensure first-time setup."""
    try:
        production_config = Path('data/config/settings.yaml')
        if production_config.exists():
            production_config.unlink()
            print("Removed production config - first-time setup will trigger")
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
    
    # Step 1: Ensure directories exist
    ensure_directories()
    
    # Step 2: Clean previous builds
    clean_build()
    
    # Step 3: Clean production config (force first-time setup)
    clean_production_config()
    
    # Step 4: Build application using command line approach
    print("Using PyInstaller command line with --add-data options")
    
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