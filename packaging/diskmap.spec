# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller commune à Windows, macOS et Linux (mode « onedir »).

Variable d'environnement :
    DISKMAP_NO_UAC=1   Windows : n'exige pas les droits administrateur au lancement
                       (utile pour tester l'exécutable sans invite UAC).
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from diskmap import __version__  # noqa: E402

ASSETS = os.path.join(SPECPATH, "assets")
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
ICON = os.path.join(ASSETS, "icon.ico" if IS_WIN else "icon.icns" if IS_MAC else "icon.png")

if IS_WIN:
    # Python Conda : _ctypes, _tkinter, _lzma, _bz2 dépendent de DLL rangées dans Library\bin,
    # que PyInstaller ne trouve que si ce dossier est dans le PATH. Sans effet avec python.org.
    _conda_bin = os.path.join(sys.base_prefix, "Library", "bin")
    if os.path.isdir(_conda_bin):
        os.environ["PATH"] = _conda_bin + os.pathsep + os.environ.get("PATH", "")

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=["numpy", "scipy", "matplotlib", "pandas", "PIL", "IPython", "pytest", "setuptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DiskMap",
    console=False,
    icon=ICON,
    uac_admin=IS_WIN and not os.environ.get("DISKMAP_NO_UAC"),
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="DiskMap", upx=False)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="DiskMap.app",
        icon=ICON,
        bundle_identifier="io.github.diskmap",
        version=__version__,
        info_plist={
            "CFBundleName": "DiskMap",
            "CFBundleDisplayName": "DiskMap",
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.13",
            "NSDesktopFolderUsageDescription": "DiskMap analyse l'espace occupé par vos dossiers.",
            "NSDocumentsFolderUsageDescription": "DiskMap analyse l'espace occupé par vos dossiers.",
            "NSDownloadsFolderUsageDescription": "DiskMap analyse l'espace occupé par vos dossiers.",
        },
    )
