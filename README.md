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

## Nouveautés de la version 2

| Fonction | Où | Ce que ça fait |
|---|---|---|
| **Machine à remonter le temps** | Analyse › Comparer à un instantané… | Un instantané compressé est enregistré après chaque analyse (`~/.diskmap/snapshots`, 30 par chemin). La carte **Changements** montre ce qui a grossi (rouge) ou rétréci (vert) ; l'analyse précédente sert de base automatiquement. |
| **Comparer deux dossiers / disques** | Analyse › Comparer à un autre dossier… | Même carte de différences entre une source et sa sauvegarde, par exemple. |
| **Doublons** | Outils › Doublons… | Taille → empreinte partielle → empreinte complète ; liens physiques ignorés. Un groupe = une couleur surlignée sur la carte, avec l'espace récupérable. |
| **Que supprimer ?** | Outils › Que supprimer ? | Catalogue de caches et dossiers régénérables (`node_modules`, `__pycache__`, DerivedData, Docker, Windows Update…) classés par *espace × sécurité*, avec l'explication et la commande conseillée. |
| **Fichiers froids** | même fenêtre, 2ᵉ onglet · Couleur › Ancienneté | Carte colorée par date de dernière modification ; liste des plus gros éléments intouchés depuis 1, 2 ou 5 ans. |
| **Surveillance en direct** | Analyse › Surveiller le dossier affiché | Réanalyse le dossier affiché toutes les 5–60 s ; ce qui grossit est entouré en orange. |
| **Projets de code** | Outils › Projets de code… | Sources / dépôt Git / dépendances et builds par projet (Node, Python, Rust, Go, Java, .NET…). |
| **Rapport HTML** | Fichier › Exporter un rapport HTML… | Page autonome avec treemap interactive (zoom, infobulles, couleur par type ou ancienneté). |
| **Icône partout** | – | Barre de titre, barre des tâches, Alt-Tab, exécutable, installeur, `.app`, paquet Linux. |

Sans fenêtre : `python -m diskmap C:\ --snapshot` et `python -m diskmap C:\ --export-html rapport.html`
(utile en tâche planifiée pour construire l'historique).

DiskMap reste en **lecture seule** : les outils expliquent et proposent, ils ne suppriment rien.

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
    diff.py          carte des changements entre deux arbres
    snapshot.py      instantanés compressés (enregistrer, lister, charger)
    duplicates.py    recherche de doublons
    cleanup.py       catalogue de nettoyage, fichiers froids
    projects.py      détection des projets de code
    age.py           tranches d'ancienneté
    export.py        rapport HTML autonome
    tree.py          parcours et chemins dans l'arbre
  ui/              interface tkinter
    app.py           fenêtre principale, pilotage du scan en thread
    treemap_view.py  canvas de la treemap + souris
    entry_list.py    liste du dossier courant
    navbar.py        « Remonter » + fil d'Ariane
    toolbar.py       sélection du disque, boutons Analyser / Annuler
    theme.py         couleurs et styles
    modebar.py       choix de la couleur (type / ancienneté / changements) + légende
    dialogs.py       fenêtres : instantanés, doublons, nettoyage, projets
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
