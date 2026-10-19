# Construit DiskMap pour Windows : dist\DiskMap\DiskMap.exe, un .zip et (si Inno Setup est installé) un installeur.
# Usage :  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.8+ introuvable dans le PATH." }

# Avec Anaconda, PyInstaller ne détecte pas Tcl/Tk depuis un venv : on utilise alors Python directement.
$isConda = (python -c "import os,sys;print(os.path.isdir(os.path.join(sys.base_prefix,'conda-meta')))") -eq "True"
if ($isConda) {
    $py = "python"
} else {
    $venv = Join-Path $root ".venv-build"
    if (-not (Test-Path $venv)) { python -m venv $venv }
    $py = Join-Path $venv "Scripts\python.exe"
}

& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet pyinstaller pillow
& $py packaging\make_icons.py
& $py packaging\build.py @args
if ($LASTEXITCODE -ne 0) { throw "Le build a échoué." }

Get-ChildItem (Join-Path $root "dist") -File | Select-Object Name, @{n="Taille (Mo)"; e={[math]::Round($_.Length / 1MB, 1)}}
