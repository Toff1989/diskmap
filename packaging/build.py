"""Construit DiskMap pour le système courant : exécutable PyInstaller + paquet de distribution.

    python packaging/build.py                # build + paquet
    python packaging/build.py --no-package   # uniquement l'exécutable (dist/DiskMap)

Sorties dans dist/ :
    Windows : DiskMap-<v>-windows-<arch>.zip  (+ DiskMap-<v>-setup.exe si Inno Setup est installé)
    Linux   : DiskMap-<v>-linux-<arch>.tar.gz (+ diskmap_<v>_<arch>.deb si dpkg-deb est présent)
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, ROOT)

from diskmap import __version__  # noqa: E402

_ARCH = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}
ARCH = _ARCH.get(platform.machine().lower(), platform.machine().lower())
DEB_ARCH = {"x64": "amd64", "arm64": "arm64"}.get(ARCH, ARCH)


def run(cmd, **kw) -> None:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def remove_tree(path: str, attempts: int = 5) -> None:
    """Supprime un dossier en réessayant : antivirus / OneDrive verrouillent parfois les fichiers un instant."""
    for i in range(attempts):
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return
        time.sleep(1 + i)
    sys.exit("Impossible de supprimer %s (fichier verrouillé ? ferme DiskMap et réessaie)" % path)


def build_executable() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller manque : pip install pyinstaller pillow")
    for d in (DIST, BUILD):
        remove_tree(d)
    run([sys.executable, "-m", "PyInstaller", "--noconfirm",
         "--distpath", DIST, "--workpath", BUILD, os.path.join(HERE, "diskmap.spec")])


# -- Windows -----------------------------------------------------------------
def package_windows() -> None:
    src = os.path.join(DIST, "DiskMap")
    zip_path = os.path.join(DIST, "DiskMap-%s-windows-%s.zip" % (__version__, ARCH))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(src):
            for f in files:
                full = os.path.join(folder, f)
                z.write(full, os.path.join("DiskMap", os.path.relpath(full, src)))
    print("->", zip_path)

    iscc = shutil.which("iscc") or next(
        (p for p in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                     r"C:\Program Files\Inno Setup 6\ISCC.exe") if os.path.exists(p)), None)
    if not iscc:
        print("Inno Setup introuvable : installeur .exe ignoré (https://jrsoftware.org/isinfo.php)")
        return
    run([iscc, "/Qp", "/DAppVersion=" + __version__, "/DAppArch=" + ARCH,
         os.path.join(HERE, "windows", "installer.iss")])


# -- Linux -------------------------------------------------------------------
def package_linux() -> None:
    src = os.path.join(DIST, "DiskMap")
    tar_path = os.path.join(DIST, "DiskMap-%s-linux-%s.tar.gz" % (__version__, ARCH))
    with tarfile.open(tar_path, "w:gz") as t:
        t.add(src, arcname="DiskMap")
    print("->", tar_path)
    if shutil.which("dpkg-deb"):
        build_deb(src)
    else:
        print("dpkg-deb introuvable : .deb ignoré")


def build_deb(src: str) -> None:
    root = os.path.join(BUILD, "deb")
    shutil.rmtree(root, ignore_errors=True)
    opt = os.path.join(root, "opt", "diskmap")
    shutil.copytree(src, opt, symlinks=True)
    for sub in ("usr/bin", "usr/share/applications", "usr/share/icons/hicolor/512x512/apps", "DEBIAN"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    os.symlink("/opt/diskmap/DiskMap", os.path.join(root, "usr", "bin", "diskmap"))
    shutil.copy(os.path.join(HERE, "linux", "diskmap.desktop"),
                os.path.join(root, "usr", "share", "applications", "diskmap.desktop"))
    shutil.copy(os.path.join(HERE, "assets", "icon.png"),
                os.path.join(root, "usr", "share", "icons", "hicolor", "512x512", "apps", "diskmap.png"))
    size_kb = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(opt) for f in fs) // 1024
    with open(os.path.join(root, "DEBIAN", "control"), "w", encoding="utf-8") as f:
        f.write("Package: diskmap\nVersion: %s\nSection: utils\nPriority: optional\n"
                "Architecture: %s\nInstalled-Size: %d\nMaintainer: DiskMap <noreply@example.com>\n"
                "Description: Analyseur d'espace disque avec treemap interactive\n"
                " Visualise ce qui occupe l'espace de vos disques.\n" % (__version__, DEB_ARCH, size_kb))
    deb = os.path.join(DIST, "diskmap_%s_%s.deb" % (__version__, DEB_ARCH))
    run(["dpkg-deb", "--build", "--root-owner-group", root, deb])
    print("->", deb)


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit DiskMap pour ce système")
    parser.add_argument("--no-package", action="store_true", help="ne produit que dist/DiskMap")
    args = parser.parse_args()

    build_executable()
    if args.no_package:
        return
    if sys.platform == "win32":
        package_windows()
    else:
        package_linux()
    print("\nTerminé. Fichiers dans", DIST)


if __name__ == "__main__":
    main()
