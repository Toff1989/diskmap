# Packaging

Chaque système se construit **sur lui-même** (PyInstaller ne fait pas de compilation croisée).
Les sorties arrivent dans `dist/`.

| Système | Commande | Résultat |
|---|---|---|
| Windows | `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1` | `DiskMap-<v>-setup.exe` (si Inno Setup 6 est installé) et `DiskMap-<v>-windows-x64.zip` |
| Linux | `./packaging/build_linux.sh` | `DiskMap-<v>-linux-<arch>.tar.gz` et, si `dpkg-deb` existe, `diskmap_<v>_<arch>.deb` |

Prérequis : Python 3.8+ avec **tkinter**. Sous Linux : `sudo apt install python3-tk python3-venv`
(Fedora : `python3-tkinter`). Windows : Inno Setup 6 pour
l'installeur (<https://jrsoftware.org/isinfo.php>), sinon seul le `.zip` est produit.

Les scripts créent un environnement `.venv-build/` et installent `pyinstaller` + `pillow`.
Avec Anaconda, ils utilisent Python directement (PyInstaller ne détecte pas Tcl/Tk depuis un venv Conda).

## Contenu

```
packaging/
  build.py            pilote commun : PyInstaller puis paquet du système courant
  diskmap.spec        spécification PyInstaller (mode onedir, sans console)
  entry.py            point d'entrée de l'exécutable
  make_icons.py       régénère assets/icon.{png,ico} (Pillow) et copie png/ico dans diskmap/assets/
  build_windows.ps1   build_linux.sh
  windows/installer.iss   installeur Inno Setup
  linux/diskmap.desktop   entrée de menu
  assets/             icônes
```

## Particularités par système

- **Windows** : l'exécutable embarque un manifeste `requireAdministrator` : Windows affiche l'invite UAC à
  chaque lancement. Pour un exécutable de test sans invite : `DISKMAP_NO_UAC=1` avant le build, et
  lance-le avec `--no-admin` (sinon l'appli tente de se relancer en administrateur).
  L'exécutable n'est pas signé : SmartScreen peut afficher un avertissement.
- **Linux** : le `.deb` installe dans `/opt/diskmap`, la commande `diskmap` et une entrée de menu.
  Pour lire les dossiers protégés : `sudo diskmap`.

## Release automatique

`.github/workflows/tests.yml` exécute les tests à chaque push et pull request.
`.github/workflows/release.yml` lance les tests puis construit Windows et Linux. Un tag `vX.Y.Z`
publie les fichiers dans une release GitHub ; un lancement manuel (`workflow_dispatch`) ne produit que
les artefacts. La version vient de `diskmap/__init__.py` (`__version__`).
