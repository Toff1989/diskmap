# Changelog

Toutes les modifications notables de DiskMap sont consignées ici.
Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le projet respecte le
[versionnage sémantique](https://semver.org/lang/fr/).

## [2.0.0] - 2026-10-21

### Ajouté
- **Instantanés et carte des changements** : un instantané compressé est enregistré après chaque analyse
  (`~/.diskmap/snapshots`, 30 par chemin). La carte « Changements » montre ce qui a grossi (rouge) ou
  rétréci (vert) depuis l'analyse précédente ou un instantané choisi.
- **Comparaison de deux dossiers ou disques** (une source et sa sauvegarde, par exemple).
- **Recherche de doublons** : taille, puis empreinte partielle, puis empreinte complète ; les liens physiques
  sont ignorés. Chaque groupe est surligné sur la carte, avec l'espace récupérable.
- **« Que supprimer ? »** : catalogue de caches et de dossiers régénérables (`node_modules`, `__pycache__`,
  Docker, Windows Update…) classés par espace et par sécurité, avec explication et commande conseillée.
- **Suppression sur confirmation explicite**, uniquement depuis « Que supprimer ? » (jamais depuis la carte,
  les doublons ni les fichiers froids) : sélection multiple, fenêtre de confirmation listant les cibles et les
  commandes exactes, bouton rouge inactif tant que la case « définitive » n'est pas cochée.
  - Liste blanche : seuls les éléments reconnus du catalogue sont supprimables ; machines virtuelles, WSL,
    `Windows.old` et mises à jour Windows restent manuels.
  - Commandes officielles quand l'outil existe (`npm cache clean --force`, `pip cache purge`,
    `dotnet nuget locals all --clear`, `docker system prune -f`, corbeille Windows, `apt-get clean`…), lancées
    sans shell ; repli sur la suppression du dossier si l'outil est absent ; droits administrateur exigés quand
    il le faut.
  - Garde-fous revérifiés juste avant d'agir : dans le dossier analysé, ni lien ni jonction (leur cible n'est
    jamais touchée), ni dossier protégé, règle toujours valide. Chemins longs Windows et fichiers en
    lecture seule gérés.
  - Journal `~/.diskmap/removals.log`, résultat ligne par ligne, réanalyse automatique ensuite.
- **Fichiers froids** : carte colorée par ancienneté et liste des plus gros éléments intouchés depuis 1, 2 ou 5 ans.
- **Surveillance en direct** du dossier affiché (réanalyse toutes les 5 à 60 s, ce qui grossit est entouré).
- **Projets de code** : sources, dépôt Git, dépendances et builds par projet (Node, Python, Rust, Go, Java, .NET…).
- **Rapport HTML autonome** avec treemap interactive (zoom, infobulles, couleur par type ou ancienneté).
- **Mode sans fenêtre** : `--snapshot` et `--export-html FICHIER`, utilisables en tâche planifiée.
- Barre de menus (Fichier, Analyse, Outils, Aide), choix du mode de couleur et légende.
- Icône d'application partout : fenêtre, barre des tâches, Alt-Tab, exécutable, installeur, paquet Linux.
- Tests de l'interface (fumée) et tests du cœur v2 ; CI de tests sur chaque push et pull request
  (Linux avec Python 3.8 et 3.12, Windows).

### Modifié
- **macOS n'est plus pris en charge** : code, packaging (`.dmg`), tests et CI retirés. DiskMap cible Windows et Linux.
- DiskMap n'est plus strictement en lecture seule : la suppression existe, mais uniquement sur confirmation
  explicite depuis « Que supprimer ? » (voir ci-dessus).
- Les chemins longs sont tronqués au milieu dans « Que supprimer ? » (la fin d'un chemin est la partie utile)
  et le chemin complet de la sélection est affiché.

### Corrigé
- Windows : la recherche de doublons ne descendait pas dans les sous-dossiers et ne détectait pas les liens
  physiques (`DirEntry.stat()` renvoie `st_dev` et `st_ino` à 0).
- Les fichiers OneDrive « en ligne seulement » ne sont plus lus par la recherche de doublons : les lire les
  aurait téléchargés.

## [1.0.0] - 2026-10-20

### Ajouté
- Application de bureau **tkinter** sans dépendance : treemap interactive (zoom au clic, fil d'Ariane,
  « Remonter », liste triée du dossier courant, menu contextuel « Ouvrir l'emplacement » / « Copier le chemin »).
- Analyse dans un thread, avec progression et annulation ; détection des disques sous Windows, macOS et Linux.
- **Zones non lisibles expliquées** : bloc rouge pour l'espace utilisé mais illisible (points de restauration,
  `WindowsApps`, corbeilles d'autres comptes, métadonnées NTFS), fenêtre listant chaque dossier refusé avec sa raison.
- Prise en charge de **OneDrive** : dossiers cloud suivis, fichiers « en ligne seulement » comptés à part.
- Jonctions et liens symboliques ignorés pour éviter tout double comptage.
- **Relance automatique en administrateur** sous Windows (`--no-admin` pour l'éviter).
- Packaging PyInstaller : installeur Windows et `.zip`, `.dmg` macOS, `.tar.gz` et `.deb` Linux.
- Workflow GitHub Actions de build et de publication de release sur tag.

[2.0.0]: https://github.com/Toff1989/diskmap/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/Toff1989/diskmap/releases/tag/v1.0.0
