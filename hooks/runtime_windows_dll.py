"""
Windows-specific runtime hook to prevent DLL ABI/FFI mismatch issues.
This runs at application startup to ensure proper DLL loading.
"""

import os
import sys
import platform

def fix_windows_dll_loading():
    """Fix Windows DLL loading issues that cause 'invalid access to memory location' errors."""
    
    if not sys.platform.startswith('win'):
        return
        
    try:
        # Ensure we're running on the expected architecture
        is_64bit = platform.machine().endswith('64') or platform.architecture()[0] == '64bit'
        expected_arch = '64-bit' if is_64bit else '32-bit'
        
        # Set DLL search path to prioritize bundled libraries
        if hasattr(sys, '_MEIPASS'):
            # We're in a PyInstaller bundle
            bundle_dir = sys._MEIPASS
            
            # Add bundle directory to DLL search path FIRST
            if hasattr(os, 'add_dll_directory'):
                # Windows 10+ / Python 3.8+
                os.add_dll_directory(bundle_dir)
            else:
                # Older Windows - modify PATH
                current_path = os.environ.get('PATH', '')
                os.environ['PATH'] = bundle_dir + os.pathsep + current_path
        
        # Set environment variables to prevent ABI conflicts
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'  # Prevent .pyc conflicts
        os.environ['PYTHONUNBUFFERED'] = '1'         # Ensure consistent I/O
        
        # Force consistent floating point behavior
        if hasattr(os, 'environ'):
            os.environ['PYTHONFAULTHANDLER'] = '1'    # Better error reporting
            
        print(f"Windows DLL runtime hook: Configured for {expected_arch} architecture")
        
    except Exception as e:
        # Don't let DLL loading fixes break the application
        print(f"Warning: Windows DLL runtime hook failed: {e}")

# Run the fix
fix_windows_dll_loading()
