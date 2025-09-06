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

def build_app(spec_file='blogsai.spec'):
    """Build the application using PyInstaller."""
    try:
        print(f"Running PyInstaller with {spec_file}...")
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            spec_file,
            '--clean',
            '--noconfirm'
        ], check=True, capture_output=True, text=True)
        
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
    
    # Check if we have the onefile executable
    exe_path = Path('dist/BlogsAI.exe')
    if exe_path.exists():
        # We have onefile mode - zip the executable
        zip_path = Path('dist/BlogsAI-Windows.zip')
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(exe_path, 'BlogsAI.exe')
        
        print(f"Created Windows distribution: {zip_path}")
        return True
    else:
        # Check for onedir mode
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
    
    print("ERROR: No built executable found")
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
    
    # Step 4: Use unified spec file for all platforms
    spec_file = 'blogsai.spec'
    print(f'Using unified spec file: {spec_file}')
    
    if not Path(spec_file).exists():
        print(f"ERROR: {spec_file} file not found!")
        sys.exit(1)
    
    print(f"Running PyInstaller with {spec_file}...")
    
    # Step 5: Build application
    if not build_app(spec_file):
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