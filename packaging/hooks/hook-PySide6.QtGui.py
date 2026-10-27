"""Collect only the native Windows platform and image formats this shell uses.

The SDK also ships PDF/virtual-keyboard plugins. They are unused here and must not
pull their modules or licensing obligations into the distribution by accident.
"""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports,binaries,datas=add_qt6_dependencies(__file__)
allowed={'qwindows.dll','qjpeg.dll','qico.dll'}
binaries=[item for item in binaries if Path(item[0]).name.lower() in allowed]
