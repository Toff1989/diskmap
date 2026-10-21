"""Détection des projets de code : combien pèsent les sources, le dépôt Git et les dépendances ?"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from .models import Node

# Fichier ou dossier marqueur -> type de projet.
_MARKERS = {
    "package.json": "Node", "pyproject.toml": "Python", "setup.py": "Python",
    "requirements.txt": "Python", "cargo.toml": "Rust", "go.mod": "Go", "pom.xml": "Java",
    "build.gradle": "Java", "build.gradle.kts": "Java", "composer.json": "PHP", "gemfile": "Ruby",
    "cmakelists.txt": "C/C++", "pubspec.yaml": "Dart", "package.swift": "Swift", ".git": "Git",
}
_SUFFIX_MARKERS = {".csproj": ".NET", ".sln": ".NET", ".xcodeproj": "Xcode"}

# Dossiers de dépendances ou de produits de compilation (régénérables).
DEPS_DIRS = {
    "node_modules", ".venv", "venv", "env", ".env", "vendor", "target", "build", "dist", ".gradle",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "pods", ".next", ".nuxt",
    ".dart_tool", "bin", "obj", ".cache", "site-packages", ".eggs", "out",
}


def project_kind(name: str, current: str) -> str:
    """Met à jour le type de projet d'un dossier en voyant une entrée de nom ``name``."""
    low = name.lower()
    kind = _MARKERS.get(low)
    if kind is None:
        i = low.rfind(".")
        kind = _SUFFIX_MARKERS.get(low[i:]) if i > 0 else None
    if kind is None:
        return current
    if not current or current == "Git":   # un langage l'emporte sur « Git » seul
        return kind
    return current


@dataclass
class ProjectInfo:
    path: str
    kind: str
    total: int
    deps: int
    vcs: int
    source: int
    node: Node
    deps_names: List[str] = field(default_factory=list)

    @property
    def deps_ratio(self) -> float:
        return self.deps / self.total if self.total else 0.0


def find_projects(root: Node, base: str, min_size: int = 0) -> List[ProjectInfo]:
    """Liste les projets sous ``root`` (triés par taille). Un projet n'est pas exploré plus loin."""
    out: List[ProjectInfo] = []
    sep = "\\" if "\\" in base and "/" not in base else "/"

    def walk(node: Node, path: str) -> None:
        if node.project and node.size >= min_size:
            deps = vcs = 0
            names: List[str] = []
            for k in node.children:
                if k.grouped:
                    continue
                low = k.name.lower()
                if low == ".git":
                    vcs += k.size
                elif low in DEPS_DIRS and k.is_dir:
                    deps += k.size
                    names.append(k.name)
            out.append(ProjectInfo(path, node.project, node.size, deps, vcs,
                                   max(node.size - deps - vcs, 0), node, names))
            return
        for k in node.children:
            if k.is_dir and not k.grouped and k.name.lower() not in DEPS_DIRS:
                walk(k, path.rstrip("\\/") + sep + k.name)

    walk(root, base)
    out.sort(key=lambda p: p.total, reverse=True)
    return out


def summarize(projects: List[ProjectInfo]) -> Tuple[int, int, int, int]:
    """(total, dépendances, dépôt Git, sources) cumulés."""
    return (sum(p.total for p in projects), sum(p.deps for p in projects),
            sum(p.vcs for p in projects), sum(p.source for p in projects))
