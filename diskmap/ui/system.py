"""Interactions avec le système (explorateur de fichiers)."""
from __future__ import annotations

import os
import subprocess


def reveal_in_file_manager(path: str) -> None:
    """Ouvre l'explorateur de fichiers sur ``path`` (sélectionné si possible)."""
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        subprocess.Popen(["xdg-open", path if os.path.isdir(path) else os.path.dirname(path)])
