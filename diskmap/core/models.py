"""Structures de données partagées par le scanner et l'interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


class Node:
    """Un fichier, un dossier ou un regroupement ("autres", "non lisible"…).

    ``__slots__`` : un scan complet crée plusieurs centaines de milliers de nœuds.
    """

    __slots__ = ("name", "size", "children", "grouped", "count", "unreadable", "note",
                 "mtime", "project", "delta")

    def __init__(self, name: str, size: int = 0, children: "List[Node] | None" = None,
                 grouped: bool = False, count: int = 1, unreadable: bool = False,
                 note: str = "", mtime: float = 0.0, project: str = "", delta: int = 0) -> None:
        self.name = name
        self.size = size
        self.children: List[Node] = children if children is not None else []
        self.grouped = grouped         # nœud synthétique : ne correspond à aucun chemin réel
        self.count = count             # nombre d'éléments réels représentés
        self.unreadable = unreadable   # espace occupé mais impossible à détailler
        self.note = note               # explication affichée à l'utilisateur
        self.mtime = mtime             # dernière modification (dossier : la plus récente à l'intérieur)
        self.project = project         # type de projet détecté dans ce dossier ("Node", "Python"…)
        self.delta = delta             # variation signée (arbres de comparaison uniquement)

    @property
    def is_dir(self) -> bool:
        return bool(self.children)

    def __repr__(self) -> str:  # pragma: no cover - debug
        return "Node(%r, %d, %d enfants)" % (self.name, self.size, len(self.children))


@dataclass
class SkipEntry:
    """Un dossier non analysé, avec la raison."""
    path: str
    reason: str          # "denied" | "junction" | "symlink" | "device" | "excluded"
    detail: str = ""     # ex. cible du lien


@dataclass
class ScanResult:
    path: str
    root: Node
    files: int
    seconds: float
    total: int = 0
    used: int = 0
    free: int = 0
    errors: int = 0
    unreadable: int = 0                  # octets utilisés mais non lisibles (disque entier seulement)
    cloud_files: int = 0                 # fichiers « en ligne seulement » (OneDrive…)
    cloud_bytes: int = 0                 # leur taille logique, hors espace disque
    skipped: List[SkipEntry] = field(default_factory=list)
