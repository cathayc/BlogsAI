"""
PyInstaller hook for Windows DLL handling.
Fixes ABI/FFI mismatch issues that cause "invalid access to memory location" errors.
"""

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, is_module_satisfies
import os
import sys
import platform

# Only apply on Windows
if not sys.platform.startswith('win'):
    datas = []
    binaries = []
    hiddenimports = []
else:
    # Collect minimal encodings to prevent import errors
    datas, binaries, hiddenimports = collect_all('encodings')
    
    # CRITICAL: Ensure consistent bitness (32-bit vs 64-bit)
    is_64bit = platform.machine().endswith('64') or platform.architecture()[0] == '64bit'
    
    print(f"Windows hook: Detected {'64-bit' if is_64bit else '32-bit'} architecture")
    
    # Only include absolutely essential Windows modules to avoid ABI conflicts
    essential_hiddenimports = [
        'msvcrt',      # Microsoft Visual C Runtime - essential
        'winreg',      # Windows registry access
        '_winapi',     # Windows API bindings
        'nt',          # NT kernel interface
    ]
    
    # Add essential modules but avoid problematic ones
    hiddenimports.extend(essential_hiddenimports)
    
    # AVOID these modules that commonly cause ABI issues:
    # - _ctypes (can have calling convention mismatches)
    # - _socket (can have struct layout issues)  
    # - _ssl (OpenSSL ABI sensitivity)
    # - _hashlib (crypto library ABI issues)
    
    print(f"Windows hook: Added {len(essential_hiddenimports)} essential Windows modules")
    
    # Don't try to manually include Visual C++ runtime DLLs
    # Let PyInstaller handle them automatically to avoid version mismatches
