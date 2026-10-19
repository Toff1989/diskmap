# DiskMap

Analyseur d'espace disque avec une treemap interactive. Windows, macOS et Linux.
Python 3.8+, interface **tkinter** (incluse avec Python) : aucune dépendance.

## Lancer

```bash
python -m diskmap            # ouvre la fenêtre
python -m diskmap C:\        # analyse directement un disque ou un dossier
```

Ou, après `pip install .`, la commande `diskmap`.

**Windows : droits administrateur automatiques.** Au lancement, DiskMap se relance lui-même en
administrateur (invite UAC) pour lire les dossiers protégés. Si tu refuses l'invite, il s'ouvre quand
même, avec des droits normaux. `--no-admin` désactive la demande.

## Utilisation

| Action | Effet |
|---|---|
| Clic sur un dossier | zoom dedans |
| Échap / Retour / « Remonter » | remonter d'un niveau |
| Fil d'Ariane | revenir à n'importe quel niveau |
| Double-clic dans la liste de droite | entrer dans le dossier |
| Clic droit | ouvrir l'emplacement, copier le chemin |
| F5 | réanalyser |

### Pourquoi certaines zones ne sont pas détaillées

- **Bloc rouge « 🔒 Non lisible »** : espace utilisé sur le disque mais impossible à lire (points de
  restauration, `WindowsApps`, corbeilles d'autres comptes, métadonnées NTFS…). Survole-le pour
  l'explication ; le bouton **« Zones non lisibles »** liste chaque dossier refusé avec sa raison.
- **Alias et jonctions** (`Documents and Settings`, liens symboliques) : ignorés exprès, l'espace est déjà
  compté à l'emplacement réel.
- **OneDrive** : les dossiers cloud sont suivis. Les fichiers « en ligne seulement » n'occupent pas de place
  locale : ils sont comptés à part (☁) et pas dans la carte.
- **Éléments minuscules** : regroupés dans « (N petits éléments) » pour que la carte reste lisible.

DiskMap ne supprime ni ne modifie jamais aucun fichier.
Lance-le en administrateur (ou `sudo`) pour inclure les dossiers protégés.

## Structure

```
diskmap/
  core/            logique sans interface (testable sans tkinter)
    models.py        Node, ScanResult
    scanner.py       parcours du disque, annulation, regroupement des petits éléments
    treemap.py       algorithme squarified treemap
    drives.py        détection des disques par OS
    formatting.py    formatage des tailles
  ui/              interface tkinter
    app.py           fenêtre principale, pilotage du scan en thread
    treemap_view.py  canvas de la treemap + souris
    entry_list.py    liste du dossier courant
    navbar.py        « Remonter » + fil d'Ariane
    toolbar.py       sélection du disque, boutons Analyser / Annuler
    theme.py         couleurs et styles
    system.py        intégration explorateur de fichiers
  __main__.py      point d'entrée (python -m diskmap)
tests/             tests unitaires du cœur
```

## Construire un exécutable

Installeur Windows, `.dmg` macOS, `.tar.gz` / `.deb` Linux : voir [packaging/README.md](packaging/README.md).

## Développement

```bash
pip install -e .[dev]
pytest
```
