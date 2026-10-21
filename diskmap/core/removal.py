"""Suppression encadrée des éléments du catalogue « Que supprimer ? ».

Principes de sécurité :
* seuls les ``Finding`` produits par le catalogue peuvent être traités, jamais un chemin libre ;
* tout est revalidé juste avant d'agir (le disque a pu changer depuis l'analyse) : le chemin doit être
  dans le dossier analysé, ne pas être un lien ou une jonction, ne pas être un dossier protégé, et
  correspondre toujours à sa règle ;
* seules certaines règles sont exécutables ; les autres (disques de machines virtuelles, WSL, mises à
  jour Windows…) restent « manuelles » ;
* quand un outil sait nettoyer proprement (npm, pip, docker…), on l'appelle sans passer par un shell ;
* rien n'est exécuté ici sans que l'interface ait obtenu une confirmation explicite ;
* chaque suppression est consignée dans ``removals.log`` (dossier de données de DiskMap).
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .cleanup import _BY_PROJECT, Finding, classify
from .models import Node
from .scanner import allocated_size, is_windows_link

DELETE, COMMAND, NONE = "delete", "command", "none"

# Règles dont le dossier ou le fichier peut être supprimé tel quel (régénérable ou déjà inutile).
_DIRECT = frozenset({
    "node_modules", "pycache", "pytest", "mypy", "ruff", "tox", "next", "nuxt", "dart_tool", "deriveddata",
    "gpucache", "code_cache", "cachestorage", "venv", "cargo_target", "maven_target", "build_dir",
    "dist_dir", "vendor_php", "vendor_go", "vendor_ruby", "pods", "cargo_registry", "maven_repo",
    "dump", "tmp", "iso",
})
# Dossiers « conteneurs » : on les vide mais on les garde.
_CONTENTS = frozenset({"win_temp", "mac_caches", "dotcache", "trash"})
# Seuls ces sous-dossiers sont supprimés (le reste, comme gradle.properties, est conservé).
_SUBDIRS: Dict[str, Tuple[str, ...]] = {"gradle": ("caches",)}
# Règles nettoyées par l'outil officiel ; ``fallback`` : suppression directe si l'outil est absent.
_TOOLS: Dict[str, Tuple[Tuple[str, ...], bool, bool]] = {
    # id: (arguments, droits administrateur requis, repli sur la suppression du dossier)
    "npm_cache": (("npm", "cache", "clean", "--force"), False, True),
    "pip_cache": (("pip", "cache", "purge"), False, True),
    "nuget": (("dotnet", "nuget", "locals", "all", "--clear"), False, True),
    "docker": (("docker", "system", "prune", "-f"), False, False),
    "hiberfil": (("powercfg", "/h", "off"), True, False),
    "var_cache": (("apt-get", "clean"), True, False),
}
# Ce que fait réellement chaque commande : affiché dans la fenêtre de confirmation.
_TOOL_NOTES = {
    "npm_cache": "vide le cache de paquets npm (re-téléchargés au besoin)",
    "pip_cache": "vide le cache de paquets pip (re-téléchargés au besoin)",
    "nuget": "vide tous les caches NuGet (paquets restaurés au prochain build)",
    "docker": "supprime les conteneurs ARRÊTÉS, les réseaux inutilisés, les images orphelines et le cache de build",
    "hiberfil": "DÉSACTIVE l'hibernation et le démarrage rapide, puis supprime hiberfil.sys",
    "var_cache": "vide le cache des paquets apt",
}
_MANUAL_WHY ="DiskMap ne la supprime pas : un mauvais geste y est trop risqué ou doit passer par l'outil du système."

MAX_ERRORS = 50
COMMAND_TIMEOUT = 900  # secondes
_LONG_PREFIX = "\\\\?\\"


@dataclass
class Plan:
    """Ce qui sera fait pour un élément, et pourquoi il pourrait ne pas l'être."""
    finding: Finding
    kind: str
    summary: str
    targets: Tuple[Tuple[str, bool], ...] = ()      # (chemin, garder_le_dossier)
    argv: Tuple[str, ...] = ()
    needs_admin: bool = False
    blocked: str = ""                               # non vide : ne sera pas exécuté

    @property
    def runnable(self) -> bool:
        return not self.blocked and self.kind != NONE

    @property
    def command_line(self) -> str:
        return subprocess.list2cmdline(list(self.argv)) if self.argv else ""

    @property
    def detail(self) -> str:
        return self.blocked or self.summary


@dataclass
class Outcome:
    plan: Plan
    ok: bool
    freed: int = 0
    message: str = ""
    errors: List[str] = field(default_factory=list)
    skipped: int = 0                                # éléments laissés (en cours d'utilisation, refusés…)


# -- sécurité -----------------------------------------------------------------
def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _protected_paths() -> List[str]:
    found = {os.path.expanduser("~"), os.path.abspath(os.sep)}
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "USERPROFILE", "PUBLIC"):
        value = os.environ.get(var)
        if value:
            found.add(value)
    drive = os.environ.get("SystemDrive")
    if drive:
        found.add(drive + os.sep)
    if os.name != "nt":
        found.update(("/usr", "/etc", "/bin", "/sbin", "/lib", "/var", "/opt", "/home", "/Users", "/System",
                      "/Library", "/Applications", "/boot", "/root"))
    return [_norm(p) for p in found]


def _is_link(path: str) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or (os.name == "nt" and is_windows_link(st))


def _still_matches(finding: Finding, path: str, is_dir: bool) -> bool:
    """La cible correspond-elle toujours à sa règle ? (même test que le catalogue, sans l'arbre d'analyse)"""
    fake = Node(os.path.basename(path.rstrip("\\/")), 1 << 60, [Node("x", 1)] if is_dir else [])
    for project in {""} | {p for table in _BY_PROJECT.values() for p in table}:
        rule = classify(path, fake, project)
        if rule is not None and rule.id == finding.rule.id:
            return True
    return False


def check_target(path: str, scan_root: str, finding: Optional[Finding] = None, *, must_match: bool = True) -> str:
    """Raison du refus, ou « » si la cible peut être traitée."""
    if not os.path.lexists(path):
        return "introuvable (déjà supprimé ?)"
    try:
        root, target = _norm(scan_root), _norm(path)
    except (OSError, ValueError):
        return "chemin invalide : refusé"
    if target == root or not target.startswith(root.rstrip(os.sep) + os.sep):
        return "hors du dossier analysé : refusé"
    # Ni la cible ni aucun dossier entre elle et la racine analysée ne doit être un lien ou une jonction
    # (sinon on supprimerait ailleurs que prévu). On ne s'appuie pas sur realpath : noms courts 8.3, OneDrive…
    current = os.path.abspath(path)
    while _norm(current) != root:
        if _is_link(current):
            return "lien symbolique ou jonction : refusé"
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    for protected in _protected_paths():
        if target == protected or protected.startswith(target.rstrip(os.sep) + os.sep):
            return "dossier protégé du système ou de l'utilisateur : refusé"
    if must_match and finding is not None and not _still_matches(finding, path, os.path.isdir(path)):
        return "ne correspond plus à sa règle de nettoyage : refusé"
    return ""


def plan_removal(finding: Finding, scan_root: str, is_admin: bool = False) -> Plan:
    """Détermine l'action prévue pour ``finding`` (sans rien exécuter)."""
    rule, path = finding.rule, finding.path
    if rule.id in _DIRECT:
        what = "Supprimer le dossier et tout son contenu" if finding.node.is_dir else "Supprimer le fichier"
        plan = Plan(finding, DELETE, what, targets=((path, False),))
    elif rule.id in _CONTENTS:
        plan = Plan(finding, DELETE, "Vider le dossier (le dossier lui-même est conservé)",
                    targets=((path, True),))
    elif rule.id in _SUBDIRS:
        subs = tuple((os.path.join(path, s), False) for s in _SUBDIRS[rule.id])
        plan = Plan(finding, DELETE, "Supprimer le sous-dossier « %s » (le reste est conservé)"
                    % "», « ".join(_SUBDIRS[rule.id]), targets=subs)
    elif rule.id == "recycle" and os.name == "nt":
        plan = _recycle_plan(finding)
    elif rule.id in _TOOLS:
        plan = _tool_plan(finding, path)
    else:
        return Plan(finding, NONE, "Action manuelle", blocked=_MANUAL_WHY + (
            "  Conseil : " + rule.how if rule.how else ""))

    if plan.blocked:
        return plan
    if plan.needs_admin and not is_admin:
        plan.blocked = "droits administrateur requis : relance DiskMap en administrateur"
        return plan
    if plan.kind == DELETE:
        reason = check_target(path, scan_root, finding)
        for target, _keep in plan.targets:
            if target != path and not reason:        # sous-dossiers : mêmes garde-fous, sans la règle
                reason = check_target(target, scan_root, finding, must_match=False)
    else:
        reason = check_target(path, scan_root, finding)
    if reason:
        plan.blocked = reason
    return plan


def _tool_plan(finding: Finding, path: str) -> Plan:
    argv, admin, fallback = _TOOLS[finding.rule.id]
    exe = shutil.which(argv[0])
    if exe is None and argv[0] == "pip":                         # pip absent du PATH : python -m pip
        py = shutil.which("python3") or shutil.which("python")
        if py:
            exe, argv = py, ("python", "-m") + argv
    if exe is None:
        if fallback and os.path.isdir(path):
            return Plan(finding, DELETE, "Outil « %s » introuvable : suppression directe du dossier" % argv[0],
                        targets=((path, False),))
        return Plan(finding, COMMAND, "Commande : " + subprocess.list2cmdline(list(argv)), argv=argv,
                    blocked="outil introuvable : %s" % argv[0])
    full = (exe,) + tuple(argv[1:])
    return Plan(finding, COMMAND, "Exécuter : %s  (%s)" % (subprocess.list2cmdline(list(argv)),
                                                          _TOOL_NOTES[finding.rule.id]),
                argv=full, needs_admin=admin)


def _recycle_plan(finding: Finding) -> Plan:
    drive = finding.path[:1]
    exe = shutil.which("powershell")
    if exe is None or not drive.isalpha():
        return Plan(finding, COMMAND, "Vider la corbeille", blocked="PowerShell introuvable")
    script = "Clear-RecycleBin -DriveLetter %s -Force -ErrorAction Stop" % drive.upper()
    return Plan(finding, COMMAND, "Vider la corbeille du disque %s: (définitif)" % drive.upper(),
                argv=(exe, "-NoProfile", "-NonInteractive", "-Command", script))


# -- exécution ----------------------------------------------------------------
def _display(path: str) -> str:
    return path[len(_LONG_PREFIX):] if path.startswith(_LONG_PREFIX) else path


def _long(path: str) -> str:
    """Préfixe « \\\\?\\ » sous Windows : node_modules dépasse souvent les 260 caractères."""
    path = os.path.abspath(path)
    return _LONG_PREFIX + path if os.name == "nt" and not path.startswith(_LONG_PREFIX) else path


def _entry_is_link(entry: "os.DirEntry[str]") -> bool:
    """Lien symbolique OU jonction Windows. ``os.walk`` ne reconnaît pas les jonctions et les traverserait :
    on ne s'en sert donc jamais pour supprimer (un test l'a montré : il effaçait la cible de la jonction)."""
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or (os.name == "nt" and is_windows_link(st))


def tree_size(path: str) -> int:
    """Taille des fichiers sous ``path``, sans jamais entrer dans un lien ou une jonction."""
    if os.path.isfile(path) or _is_link(path):
        try:
            return allocated_size(os.lstat(path))
        except OSError:
            return 0
    total, stack = 0, [_long(path)]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for e in entries:
            if _entry_is_link(e):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                else:
                    total += allocated_size(e.stat(follow_symlinks=False))
            except OSError:
                pass
    return total


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)          # fichier en lecture seule (typique de .git, node_modules)
        os.unlink(path)


def _rmdir(path: str) -> None:
    try:
        os.rmdir(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)          # dossier en lecture seule (Windows)
        os.rmdir(path)


def _remove_link(path: str) -> None:
    """Retire un lien (ou une jonction) sans jamais toucher à sa cible."""
    if os.name == "nt":
        try:
            _rmdir(path)
        except OSError:
            _unlink(path)
    else:
        os.unlink(path)


class Remover:
    """Exécute des ``Plan`` ; utilisable depuis un thread (``cancel()`` est thread-safe)."""

    def __init__(self, plans: Sequence[Plan], scan_root: str, log: bool = True) -> None:
        self.plans = [p for p in plans if p.runnable]
        self.scan_root = scan_root
        self.current = ""
        self.freed = 0
        self.index = 0
        self._log = log
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> List[Outcome]:
        outcomes: List[Outcome] = []
        for self.index, plan in enumerate(self.plans):
            if self.cancelled:
                break
            outcome = self._run_one(plan)
            outcomes.append(outcome)
            if self._log:
                _write_log(outcome)
        return outcomes

    def _run_one(self, plan: Plan) -> Outcome:
        # Revalidation : le disque a pu changer depuis l'analyse (et depuis la fenêtre de confirmation).
        fresh = plan_removal(plan.finding, self.scan_root, is_admin=True)
        if fresh.kind == NONE or fresh.kind != plan.kind or fresh.targets != plan.targets \
                or fresh.argv != plan.argv or (fresh.blocked and "administrateur" not in fresh.blocked):
            return Outcome(plan, False, message=fresh.blocked or "le plan a changé : relance l'analyse")
        self.current = plan.finding.path
        if plan.kind == COMMAND:
            return self._run_command(plan)
        return self._run_delete(plan)

    def _run_delete(self, plan: Plan) -> Outcome:
        out = Outcome(plan, True)
        for target, keep in plan.targets:
            if self.cancelled:
                break
            if check_target(target, self.scan_root, plan.finding,
                            must_match=target == plan.finding.path):
                out.errors.append("%s : refusé à la revalidation" % target)
                continue
            self._purge(target, keep, out)
        out.ok = not out.errors and out.skipped == 0 and not self.cancelled
        out.message = "%d élément(s) laissé(s) (en cours d'utilisation ou refusés)" % out.skipped \
            if out.skipped else ("interrompu" if self.cancelled else "")
        return out

    def _purge(self, top: str, keep_top: bool, out: Outcome) -> None:
        if os.path.isfile(top):
            self._file(top, out)
            return
        longtop = _long(top)
        # Parcours maison : les fichiers d'abord, les dossiers ensuite en ordre inverse (enfants avant parents).
        # Un lien ou une jonction est retiré SANS y entrer : on ne touche jamais à sa cible.
        order, stack = [], [longtop]
        while stack:
            current = stack.pop()
            order.append(current)
            try:
                entries = list(os.scandir(current))
            except OSError as exc:
                out.skipped += 1
                self._error(out, current, exc)
                continue
            for e in entries:
                if self.cancelled:
                    return
                if _entry_is_link(e):
                    try:
                        _remove_link(e.path)
                    except OSError as exc:
                        out.skipped += 1
                        self._error(out, e.path, exc)
                elif e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                else:
                    self._file(e.path, out)
        for folder in reversed(order):
            if self.cancelled or (keep_top and folder == longtop):
                continue
            try:
                _rmdir(folder)
            except OSError as exc:
                out.skipped += 1
                self._error(out, folder, exc)

    def _file(self, path: str, out: Outcome) -> None:
        self.current = _display(path)
        try:
            size = allocated_size(os.lstat(path))
            _unlink(path)
            out.freed += size
            self.freed += size
        except OSError as exc:
            out.skipped += 1
            self._error(out, path, exc)

    @staticmethod
    def _error(out: Outcome, path: str, exc: OSError) -> None:
        if len(out.errors) < MAX_ERRORS:
            out.errors.append("%s : %s" % (_display(path), exc.strerror or exc))

    def _run_command(self, plan: Plan) -> Outcome:
        before = tree_size(plan.finding.path) if os.path.exists(plan.finding.path) else 0
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(list(plan.argv), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=COMMAND_TIMEOUT,
                                  creationflags=flags)
        except (OSError, subprocess.SubprocessError) as exc:
            return Outcome(plan, False, message=str(exc), errors=[str(exc)])
        tail = "\n".join(((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()[-6:])
        after = tree_size(plan.finding.path) if os.path.exists(plan.finding.path) else 0
        freed = max(before - after, 0)
        self.freed += freed
        ok = proc.returncode == 0
        return Outcome(plan, ok, freed=freed,
                       message=tail if ok else "code de sortie %d : %s" % (proc.returncode, tail),
                       errors=[] if ok else [tail or "échec de la commande"])


# -- journal ------------------------------------------------------------------
def log_path() -> str:
    base = os.environ.get("DISKMAP_HOME") or os.path.join(os.path.expanduser("~"), ".diskmap")
    return os.path.join(base, "removals.log")


def _write_log(outcome: Outcome) -> None:
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "path": outcome.plan.finding.path,
             "rule": outcome.plan.finding.rule.id, "action": outcome.plan.kind,
             "command": outcome.plan.command_line, "ok": outcome.ok, "freed": outcome.freed,
             "skipped": outcome.skipped, "errors": len(outcome.errors)}
    try:
        os.makedirs(os.path.dirname(log_path()), exist_ok=True)
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass                                    # un journal indisponible ne doit jamais bloquer ni masquer l'action
