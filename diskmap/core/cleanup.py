"""Catalogue de nettoyage : reconnaît caches et dossiers régénérables, évalue le risque.

Ce module ne fait que classer et expliquer. La suppression elle-même, strictement encadrée et soumise à une
confirmation explicite, est dans ``removal.py``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .age import DAY, age_days
from .models import Node
from .tree import join, walk

SAFE, CAUTION, RISKY = "safe", "caution", "risky"
SAFETY_LABEL = {SAFE: "Sûr", CAUTION: "À vérifier", RISKY: "Risqué"}
_WEIGHT = {SAFE: 1.0, CAUTION: 0.5, RISKY: 0.15}


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    safety: str          # SAFE | CAUTION | RISKY
    why: str             # ce que c'est, et pourquoi on peut (ou non) le retirer
    how: str = ""        # commande ou geste recommandé
    regenerable: bool = True


@dataclass
class Finding:
    path: str
    node: Node
    rule: Rule

    @property
    def size(self) -> int:
        return self.node.size

    @property
    def score(self) -> float:
        """Espace récupérable pondéré par la sécurité."""
        return self.node.size * _WEIGHT[self.rule.safety]


def _r(id_: str, label: str, safety: str, why: str, how: str = "", regen: bool = True) -> Rule:
    return Rule(id_, label, safety, why, how, regen)


# Dossiers reconnus par leur nom (minuscules).
_BY_NAME: Dict[str, Rule] = {
    "node_modules": _r("node_modules", "Dépendances Node.js", SAFE,
                       "Paquets téléchargés par npm/yarn/pnpm ; recréés à partir de package.json.",
                       "npm install   (ou : rm -rf node_modules)"),
    "__pycache__": _r("pycache", "Cache Python", SAFE,
                      "Bytecode compilé ; Python le recrée tout seul au prochain lancement.",
                      "find . -name __pycache__ -prune -exec rm -rf {} +"),
    ".pytest_cache": _r("pytest", "Cache pytest", SAFE, "Résultats de la dernière exécution des tests."),
    ".mypy_cache": _r("mypy", "Cache mypy", SAFE, "Cache du vérificateur de types."),
    ".ruff_cache": _r("ruff", "Cache ruff", SAFE, "Cache du linter."),
    ".tox": _r("tox", "Environnements tox", SAFE, "Environnements de test recréés par tox.", "tox -r"),
    ".next": _r("next", "Build Next.js", SAFE, "Sortie de compilation régénérée par « next build »."),
    ".nuxt": _r("nuxt", "Build Nuxt", SAFE, "Sortie de compilation régénérée par « nuxt build »."),
    ".dart_tool": _r("dart_tool", "Cache Dart/Flutter", SAFE, "Régénéré par « flutter pub get »."),
    "deriveddata": _r("deriveddata", "Xcode DerivedData", SAFE,
                      "Produits de compilation et index Xcode ; recréés à la prochaine compilation.",
                      "rm -rf ~/Library/Developer/Xcode/DerivedData"),
    "_cacache": _r("npm_cache", "Cache npm", SAFE, "Archives de paquets téléchargées par npm.",
                   "npm cache clean --force"),
    "gpucache": _r("gpucache", "Cache GPU (navigateur/Electron)", SAFE, "Cache graphique recréé à la demande."),
    "code cache": _r("code_cache", "Cache de code (navigateur/Electron)", SAFE, "Code JavaScript compilé en cache."),
    "cachestorage": _r("cachestorage", "Cache web (navigateur/Electron)", CAUTION,
                       "Peut contenir des données hors-ligne de sites ou d'applications web."),
    ".venv": _r("venv", "Environnement virtuel Python", CAUTION,
                "Recréable avec « python -m venv » + « pip install -r requirements.txt », "
                "mais perd les paquets installés à la main.", "rm -rf .venv && python -m venv .venv"),
    "venv": _r("venv", "Environnement virtuel Python", CAUTION,
               "Recréable avec « python -m venv » + « pip install -r requirements.txt »."),
    ".gradle": _r("gradle", "Cache Gradle", SAFE, "Téléchargé de nouveau au prochain build.",
                  "rm -rf ~/.gradle/caches"),
    "softwaredistribution": _r("wu", "Cache Windows Update", CAUTION,
                               "Mises à jour téléchargées ; à nettoyer via l'outil Windows, pas à la main.",
                               "cleanmgr  (Nettoyage de disque › Nettoyer les fichiers système)", regen=False),
    "windows.old": _r("windows_old", "Ancienne installation de Windows", CAUTION,
                      "Permet de revenir en arrière après une mise à jour ; supprimée seule après 10 jours.",
                      "cleanmgr  (Nettoyage de disque › Nettoyer les fichiers système)", regen=False),
    "$windows.~bt": _r("windows_bt", "Préparation de mise à jour Windows", CAUTION,
                       "Fichiers temporaires d'une mise à jour.", "cleanmgr", regen=False),
    "$recycle.bin": _r("recycle", "Corbeille", SAFE,
                       "Fichiers déjà supprimés mais pas encore effacés du disque.",
                       "Vider la corbeille", regen=False),
    ".trash": _r("trash", "Corbeille", SAFE, "Fichiers déjà supprimés.", "Vider la corbeille", regen=False),
    ".trashes": _r("trash", "Corbeille", SAFE, "Fichiers déjà supprimés.", "Vider la corbeille", regen=False),
    "trash": _r("trash", "Corbeille", SAFE, "Fichiers déjà supprimés.", "Vider la corbeille", regen=False),
    ".cache": _r("dotcache", "Dossier de cache utilisateur", CAUTION,
                 "Caches d'applications (pip, thumbnails, navigateurs…) ; recréés mais parfois lentement."),
}

# Dossiers dont la signification dépend du projet parent.
_BY_PROJECT: Dict[str, Dict[str, Rule]] = {
    "target": {"Rust": _r("cargo_target", "Build Rust (target)", SAFE,
                          "Artefacts de compilation ; « cargo build » les recrée.", "cargo clean"),
               "Java": _r("maven_target", "Build Maven (target)", SAFE,
                          "Artefacts de compilation.", "mvn clean")},
    "build": {"Node": _r("build_dir", "Dossier build", CAUTION, "Sortie de compilation (à vérifier)."),
              "Python": _r("build_dir", "Dossier build", SAFE, "Sortie de compilation Python."),
              "Java": _r("build_dir", "Dossier build", SAFE, "Sortie de compilation.", "gradle clean"),
              "C/C++": _r("build_dir", "Dossier build", SAFE, "Sortie de CMake/make.")},
    "dist": {"Node": _r("dist_dir", "Dossier dist", CAUTION, "Version empaquetée, à régénérer par le build."),
             "Python": _r("dist_dir", "Dossier dist", SAFE, "Paquets construits (wheel/sdist).")},
    "vendor": {"PHP": _r("vendor_php", "Dépendances Composer", SAFE, "Recréées par composer.", "composer install"),
               "Go": _r("vendor_go", "Dépendances Go vendorisées", CAUTION, "Recréées par « go mod vendor ».",
                        "go mod vendor"),
               "Ruby": _r("vendor_ruby", "Gems vendorisés", SAFE, "Recréés par bundler.", "bundle install")},
    "pods": {"Swift": _r("pods", "CocoaPods", SAFE, "Recréés par « pod install ».", "pod install"),
             "Xcode": _r("pods", "CocoaPods", SAFE, "Recréés par « pod install ».", "pod install")},
}

# Fragments de chemin (en minuscules, séparateurs « / »).
_BY_PATH = (
    ("/pip/cache", _r("pip_cache", "Cache pip", SAFE, "Archives de paquets Python téléchargées.",
                      "pip cache purge")),
    (".cache/pip", _r("pip_cache", "Cache pip", SAFE, "Archives de paquets Python téléchargées.",
                      "pip cache purge")),
    ("/.cargo/registry", _r("cargo_registry", "Registre Cargo", SAFE,
                            "Sources de crates téléchargées ; récupérées au prochain build.")),
    ("/.nuget/packages", _r("nuget", "Paquets NuGet", SAFE, "Récupérés à la restauration du projet.",
                            "dotnet nuget locals all --clear")),
    ("/.m2/repository", _r("maven_repo", "Dépôt Maven local", CAUTION,
                           "Dépendances Java ; re-téléchargées au prochain build.")),
    ("/appdata/local/temp", _r("win_temp", "Fichiers temporaires Windows", SAFE,
                               "Fichiers temporaires des applications (ceux en cours d'usage restent).",
                               "cleanmgr", regen=False)),
    ("/library/caches", _r("mac_caches", "Caches macOS", CAUTION,
                           "Caches des applications ; recréés, mais fermez les applications avant.")),
    ("/var/cache", _r("var_cache", "Cache système (/var/cache)", CAUTION,
                      "Cache des paquets (apt, dnf…).", "sudo apt clean")),
    ("/var/log/journal", _r("journal", "Journal systemd", CAUTION, "Journaux système.",
                            "sudo journalctl --vacuum-size=200M", regen=False)),
)

_BY_FILE_NAME = {
    "hiberfil.sys": _r("hiberfil", "Fichier d'hibernation", CAUTION,
                       "Sauvegarde de la RAM pour hiberner et le démarrage rapide. Désactiver supprime le fichier.",
                       "powercfg /h off", regen=True),
    "docker.raw": _r("docker", "Disque virtuel Docker", CAUTION,
                     "Images et conteneurs Docker. Nettoyez via Docker, jamais en supprimant le fichier.",
                     "docker system prune -a", regen=False),
    "docker_data.vhdx": _r("docker", "Disque virtuel Docker", CAUTION,
                           "Images et conteneurs Docker. Nettoyez via Docker, jamais en supprimant le fichier.",
                           "docker system prune -a", regen=False),
    "ext4.vhdx": _r("wsl", "Disque virtuel WSL/Docker", RISKY,
                    "Contient tout un système Linux : ne supprimez jamais ce fichier à la main.",
                    "wsl --manage <distro> --set-sparse true", regen=False),
}
_BY_EXT = {
    ".dmp": _r("dump", "Vidage mémoire", SAFE, "Rapport de plantage, utile seulement au diagnostic."),
    ".tmp": _r("tmp", "Fichier temporaire", SAFE, "Fichier temporaire laissé par une application."),
    ".iso": _r("iso", "Image disque ISO", CAUTION, "Souvent un installateur déjà utilisé ; re-téléchargeable.",
               regen=False),
    ".vmdk": _r("vm", "Disque de machine virtuelle", RISKY, "Contient une machine virtuelle entière.", regen=False),
    ".vdi": _r("vm", "Disque de machine virtuelle", RISKY, "Contient une machine virtuelle entière.", regen=False),
    ".vhdx": _r("vm", "Disque de machine virtuelle", RISKY, "Contient une machine virtuelle entière.", regen=False),
}
MIN_FILE_FINDING = 50 * 1024 * 1024    # les règles par extension/nom ne comptent qu'au-delà


def classify(path: str, node: Node, parent_project: str = "") -> Optional[Rule]:
    """Règle de nettoyage applicable à ce nœud, ou None."""
    name = node.name.lower()
    norm = path.replace("\\", "/").lower()
    if node.is_dir:
        rule = _BY_NAME.get(name)
        if name in _BY_PROJECT and parent_project in _BY_PROJECT[name]:
            return _BY_PROJECT[name][parent_project]
        if rule:
            return rule
        for frag, prule in _BY_PATH:
            if norm.endswith(frag):
                return prule
        return None
    if node.size < MIN_FILE_FINDING:
        return None
    rule = _BY_FILE_NAME.get(name)
    if rule:
        return rule
    i = name.rfind(".")
    return _BY_EXT.get(name[i:]) if i > 0 else None


def find_cleanup(root: Node, base: str, min_size: int = 1 << 20) -> List[Finding]:
    """Candidats au nettoyage classés par espace récupérable × sécurité (meilleurs d'abord)."""
    out: List[Finding] = []

    def visit(node: Node, path: str, project: str) -> None:
        for k in node.children:
            if k.grouped:
                continue
            kpath = join(path, k.name)
            rule = classify(kpath, k, project) if k.size >= min_size else None
            if rule:
                out.append(Finding(kpath, k, rule))      # on ne descend pas : pas de double comptage
            elif k.children:
                visit(k, kpath, k.project or project)

    visit(root, base, root.project)
    out.sort(key=lambda f: f.score, reverse=True)
    return out


@dataclass
class ColdEntry:
    path: str
    node: Node
    age_days: float


def find_cold(root: Node, base: str, min_days: float = 730, min_size: int = 10 << 20,
              limit: int = 300, now: Optional[float] = None) -> List[ColdEntry]:
    """Plus gros fichiers/dossiers dont rien n'a été modifié depuis ``min_days`` jours."""
    now = time.time() if now is None else now
    out: List[ColdEntry] = []

    def visit(node: Node, path: str) -> None:
        for k in node.children:
            if k.grouped or k.size < min_size or k.mtime <= 0:
                continue
            kpath = join(path, k.name)
            if age_days(k.mtime, now) >= min_days:
                out.append(ColdEntry(kpath, k, age_days(k.mtime, now)))   # entièrement froid
            elif k.children:
                visit(k, kpath)

    visit(root, base)
    out.sort(key=lambda c: c.node.size, reverse=True)
    return out[:limit]


def reclaimable(findings: List[Finding], safety: Callable[[str], bool] = lambda s: s == SAFE) -> int:
    return sum(f.size for f in findings if safety(f.rule.safety))
