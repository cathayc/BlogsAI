"""
PyInstaller hook for Windows DLL handling.
Helps resolve "failed to load python dll" issues on Windows.
"""

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
import os
import sys

# Collect all encodings to prevent import errors
datas, binaries, hiddenimports = collect_all('encodings')

# Add Windows-specific runtime libraries
if sys.platform.startswith('win'):
    # Include Windows runtime DLLs
    binaries.extend(collect_dynamic_libs('_ctypes'))
    binaries.extend(collect_dynamic_libs('_socket'))
    binaries.extend(collect_dynamic_libs('_ssl'))
    binaries.extend(collect_dynamic_libs('_hashlib'))
    
    # Add essential Windows modules
    hiddenimports.extend([
        '_ctypes',
        'ctypes',
        'ctypes.wintypes',
        'ctypes.util',
        'msvcrt',
        'winreg',
        '_winapi',
        'nt',
        '_overlapped',
        '_multiprocessing',
    ])
    
    # Include Visual C++ runtime libraries if available
    try:
        import _ctypes
        ctypes_path = os.path.dirname(_ctypes.__file__)
        for dll_name in ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']:
            dll_path = os.path.join(ctypes_path, dll_name)
            if os.path.exists(dll_path):
                binaries.append((dll_path, '.'))
    except (ImportError, AttributeError):
        pass
