"""
Resource path utilities for PyInstaller compatibility.

Handles path resolution for both development and frozen (PyInstaller) modes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """
    Check if running from PyInstaller bundle.
    
    Returns:
        True if running as frozen executable, False if running from source.
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works in dev and frozen mode.
    
    In development mode, resolves relative to project root.
    In frozen mode, resolves relative to PyInstaller's temporary extraction directory.
    
    Args:
        relative_path: Path relative to project root (e.g., 'src/gui/style.qss')
    
    Returns:
        Absolute path to the resource file.
    """
    if is_frozen():
        # PyInstaller extracts bundled files to sys._MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # In development, base is project root (two levels up from this file)
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    return os.path.join(base_path, relative_path)


def get_assets_dir() -> str:
    """
    Get path to assets/cards directory.
    
    In development mode, uses project's assets/cards directory.
    In frozen mode, uses a writable location in user's data directory:
    - Windows: %LOCALAPPDATA%/AsiaPoker421/assets/cards
    - macOS: ~/Library/Application Support/AsiaPoker421/assets/cards
    - Linux: ~/.local/share/AsiaPoker421/assets/cards
    
    Returns:
        Absolute path to assets directory (may not exist yet).
    """
    if is_frozen():
        # Use platform-specific user data directory for writable assets
        if sys.platform == 'win32':
            # Windows: %LOCALAPPDATA%/AsiaPoker421/assets/cards
            base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            assets_dir = os.path.join(base, 'AsiaPoker421', 'assets', 'cards')
        elif sys.platform == 'darwin':
            # macOS: ~/Library/Application Support/AsiaPoker421/assets/cards
            base = os.path.expanduser('~/Library/Application Support')
            assets_dir = os.path.join(base, 'AsiaPoker421', 'assets', 'cards')
        else:
            # Linux: ~/.local/share/AsiaPoker421/assets/cards
            base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
            assets_dir = os.path.join(base, 'AsiaPoker421', 'assets', 'cards')
        
        # If bundled assets exist, try to copy them to user directory on first run
        bundled_assets = get_resource_path('assets/cards')
        if os.path.exists(bundled_assets) and os.path.isdir(bundled_assets):
            # Check if user assets need initialization
            if not os.path.exists(assets_dir):
                os.makedirs(assets_dir, exist_ok=True)
                # Copy bundled assets to user directory
                import shutil
                try:
                    for item in os.listdir(bundled_assets):
                        src = os.path.join(bundled_assets, item)
                        dst = os.path.join(assets_dir, item)
                        if os.path.isfile(src) and not os.path.exists(dst):
                            shutil.copy2(src, dst)
                except Exception:
                    # If copy fails, assets will be generated on demand
                    pass
        
        return assets_dir
    else:
        # In development, use project's assets/cards directory
        return get_resource_path('assets/cards')
