"""Relance de l'application avec les droits administrateur (Windows, via UAC)."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence

_PACKAGE_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SW_SHOWNORMAL = 1
_SHELLEXECUTE_OK = 32  # ShellExecuteW renvoie > 32 en cas de succès


def is_admin() -> bool:
    """Vrai si le processus a les droits administrateur (root sous Unix)."""
    if os.name == "nt":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def build_command(args: Sequence[str], executable: str = "") -> "tuple[str, str]":
    """Renvoie (exécutable, paramètres) pour relancer ``python -m diskmap <args>``.

    ``pythonw.exe`` est préféré : pas de fenêtre de console noire derrière l'appli.
    """
    exe = executable or sys.executable
    if getattr(sys, "frozen", False):  # exécutable PyInstaller : il se relance directement
        return exe, subprocess.list2cmdline(list(args))
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if not executable and os.path.basename(exe).lower() == "python.exe" and os.path.exists(pythonw):
        exe = pythonw
    return exe, subprocess.list2cmdline(["-m", "diskmap", *args])


def relaunch_as_admin(args: Sequence[str]) -> bool:
    """Relance l'appli en administrateur. Renvoie False si impossible ou refusé (UAC annulé)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        exe, params = build_command(args)
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params,
                                                     _PACKAGE_PARENT, _SW_SHOWNORMAL)
        return result > _SHELLEXECUTE_OK
    except (AttributeError, OSError):
        return False
