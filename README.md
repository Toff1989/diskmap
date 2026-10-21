# DiskMap

[![Tests](https://github.com/Toff1989/diskmap/actions/workflows/tests.yml/badge.svg)](https://github.com/Toff1989/diskmap/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/Toff1989/diskmap?color=3b6fd4)](https://github.com/Toff1989/diskmap/releases/latest)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Plateformes](https://img.shields.io/badge/plateformes-Windows%20%7C%20Linux-555)](#télécharger)
[![Dépendances](https://img.shields.io/badge/d%C3%A9pendances-aucune-brightgreen)](#lancer-depuis-les-sources)
[![Suppression](https://img.shields.io/badge/suppression-sur%20confirmation-b3261e)](#suppression-toujours-sur-confirmation)
[![Licence](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

**Vois d'un coup d'œil ce qui remplit ton disque.** DiskMap analyse un disque ou un dossier et l'affiche
en treemap interactive : plus un rectangle est grand, plus il pèse lourd. Windows et Linux, sans
aucune dépendance (interface tkinter, incluse avec Python).

![DiskMap : treemap d'un dossier, liste triée à droite, fil d'Ariane et modes de couleur](docs/screenshot.png)

## Télécharger

Les installeurs sont dans la [dernière release](https://github.com/Toff1989/diskmap/releases/latest) :

| Système | Fichier |
|---|---|
| Windows | `DiskMap-<version>-setup.exe` (installeur) ou `…-windows-x64.zip` (portable) |
| Linux | `diskmap_<version>_amd64.deb` ou `DiskMap-<version>-linux-x64.tar.gz` |

Les exécutables ne sont pas signés : SmartScreen (Windows) peut afficher un avertissement.

## Lancer depuis les sources

Python 3.8+ avec tkinter, rien d'autre à installer :

```bash
python -m diskmap            # ouvre la fenêtre
python -m diskmap C:\        # analyse directement un disque ou un dossier
```

Ou, après `pip install .`, la commande `diskmap`.

**Windows : droits administrateur automatiques.** Au lancement, DiskMap se relance lui-même en
administrateur (invite UAC) pour lire les dossiers protégés. Si tu refuses l'invite, il s'ouvre quand
même, avec des droits normaux. `--no-admin` désactive la demande. Sous Linux, utilise `sudo`
pour inclure les dossiers protégés.

## Utilisation

| Action | Effet |
|---|---|
| Clic sur un dossier | zoom dedans |
| Échap / Retour / « Remonter » | remonter d'un niveau |
| Fil d'Ariane | revenir à n'importe quel niveau |
| Double-clic dans la liste de droite | entrer dans le dossier |
| Clic droit | ouvrir l'emplacement, copier le chemin |
| F5 | réanalyser |

## Fonctions

| Fonction | Où | Ce que ça fait |
|---|---|---|
| **Machine à remonter le temps** | Analyse › Comparer à un instantané… | Un instantané compressé est enregistré après chaque analyse (`~/.diskmap/snapshots`, 30 par chemin). La carte **Changements** montre ce qui a grossi (rouge) ou rétréci (vert) ; l'analyse précédente sert de base automatiquement. |
| **Comparer deux dossiers / disques** | Analyse › Comparer à un autre dossier… | Même carte de différences entre une source et sa sauvegarde, par exemple. |
| **Doublons** | Outils › Doublons… | Taille, empreinte partielle, puis empreinte complète ; liens physiques ignorés. Un groupe = une couleur surlignée sur la carte, avec l'espace récupérable. |
| **Que supprimer ?** | Outils › Que supprimer ? | Catalogue de caches et dossiers régénérables (`node_modules`, `__pycache__`, Docker, Windows Update…) classés par *espace × sécurité*, avec l'explication, et la possibilité de **les supprimer sur confirmation explicite** (voir ci-dessous). |
| **Fichiers froids** | même fenêtre, 2ᵉ onglet · Couleur › Ancienneté | Carte colorée par date de dernière modification ; liste des plus gros éléments intouchés depuis 1, 2 ou 5 ans. |
| **Surveillance en direct** | Analyse › Surveiller le dossier affiché | Réanalyse le dossier affiché toutes les 5 à 60 s ; ce qui grossit est entouré en orange. |
| **Projets de code** | Outils › Projets de code… | Sources / dépôt Git / dépendances et builds par projet (Node, Python, Rust, Go, Java, .NET…). |
| **Rapport HTML** | Fichier › Exporter un rapport HTML… | Page autonome avec treemap interactive (zoom, infobulles, couleur par type ou ancienneté). |

Sans fenêtre : `python -m diskmap C:\ --snapshot` et `python -m diskmap C:\ --export-html rapport.html`
(utile en tâche planifiée pour construire l'historique).

### Suppression : toujours sur confirmation

DiskMap n'efface **rien** tant que tu ne l'as pas demandé et confirmé. La suppression n'existe qu'à **un seul
endroit** : *Outils › Que supprimer ?*. Ni la carte, ni les doublons, ni les fichiers froids (tes données) ne
peuvent rien supprimer.

![Fenêtre de confirmation : liste exacte de ce qui sera supprimé, avertissement, case à cocher](docs/confirmation.png)

- **Confirmation explicite** : tu sélectionnes des lignes, puis « Supprimer… » ouvre une fenêtre qui liste
  exactement les cibles, leurs tailles et l'action (ou la commande exacte qui sera lancée). Le bouton rouge
  reste inactif tant que tu n'as pas coché « Je comprends que cette suppression est définitive ».
- **Définitif** : les éléments ne passent pas par la corbeille. Ne sont proposés que des éléments
  régénérables du catalogue (`node_modules`, `__pycache__`, caches, builds…), jamais tes documents.
- **Liste blanche** : DiskMap ne supprime que ce que son catalogue a reconnu. Les disques de machines
  virtuelles, WSL, `Windows.old` ou les mises à jour Windows restent **manuels**.
- **Les bons outils d'abord** : quand un outil sait nettoyer proprement, DiskMap le lance, sans shell, avec
  la ligne de commande affichée avant confirmation (`npm cache clean --force`, `pip cache purge`,
  `dotnet nuget locals all --clear`, `docker system prune -f`, vidage de la corbeille Windows…). Si l'outil est
  absent, il retombe sur la suppression du dossier de cache. Les commandes qui exigent les droits
  administrateur sont refusées sans eux.
- **Garde-fous revérifiés au moment d'agir** : la cible doit être dans le dossier analysé, ne pas être un
  lien symbolique ni une jonction (ni passer par l'un d'eux : leur cible n'est jamais touchée), ne pas être un
  dossier protégé (système, dossier personnel, racine de disque) et correspondre toujours à sa règle, même si
  le disque a changé entre l'analyse et la confirmation.
- **Traçabilité** : chaque action est consignée dans `~/.diskmap/removals.log` (date, cible, résultat, espace
  libéré), et l'analyse est relancée ensuite pour que la carte reflète le résultat.
- Une suppression partielle (fichiers en cours d'utilisation, accès refusé) est signalée ligne par ligne.

### Pourquoi certaines zones ne sont pas détaillées

- **Bloc rouge « 🔒 Non lisible »** : espace utilisé sur le disque mais impossible à lire (points de
  restauration, `WindowsApps`, corbeilles d'autres comptes, métadonnées NTFS…). Survole-le pour
  l'explication ; le bouton **« Zones non lisibles »** liste chaque dossier refusé avec sa raison.
- **Alias et jonctions** (`Documents and Settings`, liens symboliques) : ignorés exprès, l'espace est déjà
  compté à l'emplacement réel.
- **OneDrive** : les dossiers cloud sont suivis. Les fichiers « en ligne seulement » n'occupent pas de place
  locale : ils sont comptés à part (☁) et pas dans la carte, et ne sont jamais lus (ce qui les téléchargerait).
- **Éléments minuscules** : regroupés dans « (N petits éléments) » pour que la carte reste lisible.

## Structure

```
diskmap/
  core/              logique sans interface (testable sans tkinter)
    models.py          Node, ScanResult, SkipEntry
    scanner.py         parcours du disque, annulation, regroupement des petits éléments
    treemap.py         algorithme squarified treemap
    drives.py          détection des disques par OS
    explain.py         explications des zones non lisibles
    formatting.py      formatage des tailles
    tree.py            parcours et chemins dans l'arbre
    age.py             tranches d'ancienneté
    diff.py            carte des changements entre deux arbres
    snapshot.py        instantanés compressés (enregistrer, lister, charger)
    duplicates.py      recherche de doublons
    cleanup.py         catalogue de nettoyage (classement), fichiers froids
    removal.py         suppression encadrée : plans, garde-fous, exécution, journal
    projects.py        détection des projets de code
    export.py          rapport HTML autonome
  ui/                interface tkinter
    app.py             fenêtre principale, pilotage du scan en thread
    treemap_view.py    canvas de la treemap + souris
    entry_list.py      liste du dossier courant
    navbar.py          « Remonter » + fil d'Ariane
    toolbar.py         sélection du disque, boutons Analyser / Annuler
    modebar.py         mode de couleur (type / ancienneté / changements) + légende
    dialogs.py         fenêtres : instantanés, doublons, nettoyage, projets
    removal_dialog.py  confirmation puis exécution d'une suppression
    skipped_dialog.py  fenêtre « Zones non lisibles »
    text.py            utilitaires d'affichage (troncature au milieu des chemins)
    theme.py           couleurs et styles
    system.py          intégration explorateur de fichiers
  assets/            icône de la fenêtre
  elevation.py       relance en administrateur (Windows)
  __main__.py        point d'entrée (python -m diskmap)
packaging/           scripts de build Windows / Linux
tests/               tests du cœur et de l'interface
docs/                capture d'écran
```

## Développement

```bash
pip install -e .[dev]
pytest
```

La CI exécute les tests sur Linux (Python 3.8 et 3.12) et Windows à chaque push et pull request.
Pour construire les exécutables : [packaging/README.md](packaging/README.md). L'historique des versions est
dans le [CHANGELOG](CHANGELOG.md).

## Licence

[MIT](LICENSE)
