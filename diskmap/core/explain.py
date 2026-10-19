"""Explications en français des zones qui ne peuvent pas être détaillées."""
from __future__ import annotations

import re

# Noms de dossiers connus (insensible à la casse) -> explication.
_KNOWN = {
    "system volume information": "Points de restauration et clichés instantanés (VSS) : réservé au système.",
    "windowsapps": "Applications du Microsoft Store et jeux Xbox : protégé par Windows.",
    "$recycle.bin": "Corbeille d'autres comptes utilisateurs : accès réservé à leur propriétaire.",
    "recycler": "Corbeille d'autres comptes utilisateurs : accès réservé à leur propriétaire.",
    "perflogs": "Journaux de performances Windows : accès réservé aux administrateurs.",
    "prefetch": "Cache de lancement des programmes : réservé au système.",
    "appcompat": "Données de compatibilité des applications : réservé au système.",
    "serviceprofiles": "Profils des comptes de service Windows : réservé au système.",
    "servicestate": "État des services Windows : réservé au système.",
    "livekernelreports": "Rapports de plantage du noyau : réservé au système.",
    "config.msi": "Fichiers temporaires d'installation Windows Installer.",
    "$windows.~bt": "Fichiers de mise à jour de Windows (préparation).",
    "$windows.~ws": "Fichiers de mise à jour de Windows (sources).",
    "windows.old": "Ancienne installation de Windows conservée après une mise à jour.",
    "recovery": "Partition ou dossier de récupération Windows.",
    "documents and settings": "Alias de compatibilité vers « Users » : l'espace est déjà compté.",
    "diagnosis": "Données de diagnostic Windows : accès réservé au système.",
    "packages": "Paquets d'applications Windows : accès réservé au système.",
}

_BY_REASON = {
    "denied": "Accès refusé : ouvre DiskMap en administrateur pour analyser ce dossier.",
    "junction": "Jonction Windows (alias vers un autre dossier) : l'espace est déjà compté ailleurs.",
    "symlink": "Lien symbolique : l'espace est déjà compté à l'emplacement réel.",
    "device": "Autre disque ou système de fichiers monté ici : non traversé (option « Traverser »).",
    "excluded": "Dossier virtuel du système (pas de vrai espace disque).",
}

REASON_LABEL = {
    "denied": "Accès refusé",
    "junction": "Jonction (alias)",
    "symlink": "Lien symbolique",
    "device": "Autre montage",
    "excluded": "Dossier virtuel",
}

UNREADABLE_NAME = "🔒 Non lisible : système et zones protégées"
UNREADABLE_NOTE = (
    "Espace utilisé sur le disque mais impossible à détailler : dossiers protégés "
    "(points de restauration, applications du Store, corbeilles d'autres comptes…), "
    "métadonnées du système de fichiers (MFT, journal NTFS) et écarts de calcul "
    "(fichiers compressés ou liés). Clique sur « Zones non lisibles » pour la liste."
)
SMALL_NOTE = "Éléments trop petits pour être dessinés, regroupés ici (moins de 0,02 % du total)."
OTHER_NOTE = "Éléments les plus petits du dossier, regroupés pour limiter la mémoire."


def explain(path: str, reason: str, detail: str = "") -> str:
    name = re.split(r"[\\/]", path.rstrip("\\/"))[-1]  # sans os.path : valable pour tout style de chemin
    known = _KNOWN.get(name.lower())
    if reason in ("junction", "symlink") and detail:
        return _BY_REASON[reason] + " Cible : " + detail
    return known or _BY_REASON.get(reason, "")
