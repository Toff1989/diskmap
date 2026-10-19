#!/usr/bin/env bash
# Construit DiskMap pour macOS : dist/DiskMap.app et un .dmg.
# Usage :  ./packaging/build_macos.sh
# Optionnel : CODESIGN_IDENTITY="Developer ID Application: Nom (TEAMID)" pour signer.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null || { echo "Python 3.8+ requis (brew install python-tk)"; exit 1; }
python3 -c "import tkinter" 2>/dev/null || { echo "tkinter manque : brew install python-tk"; exit 1; }

# Avec Anaconda, PyInstaller ne détecte pas Tcl/Tk depuis un venv : on utilise alors Python directement.
if python3 -c "import os,sys; sys.exit(0 if os.path.isdir(os.path.join(sys.base_prefix,'conda-meta')) else 1)"; then
  PY=python3
else
  [ -d .venv-build ] || python3 -m venv .venv-build
  PY=.venv-build/bin/python
fi

$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet pyinstaller pillow
$PY packaging/make_icons.py
$PY packaging/build.py "$@"

ls -lh dist
