"""Parcours récursif d'un disque ou d'un dossier."""
from __future__ import annotations

import os
import shutil
import sys
import time
from typing import List, Optional, Set, Tuple

from .models import Node, ScanResult, SkipEntry
from .projects import project_kind
from .explain import OTHER_NOTE, SMALL_NOTE, UNREADABLE_NAME, UNREADABLE_NOTE

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

MAX_KIDS = 300         # éléments gardés par dossier pendant le scan (mémoire)
MAX_DEPTH = 12         # profondeur maximale conservée
MIN_VISIBLE = 5000.0   # un élément < taille_totale / MIN_VISIBLE est fusionné
MAX_SKIPPED = 5000     # taille maximale de la liste des dossiers ignorés

if sys.platform.startswith("linux"):
    DEFAULT_SKIP: Set[str] = {"/proc", "/sys", "/dev", "/run"}
elif IS_MAC:
    DEFAULT_SKIP = {"/Volumes", "/System/Volumes", "/dev", "/private/var/vm"}
else:
    DEFAULT_SKIP = set()

# Attributs et balises de points d'analyse Windows.
_REPARSE_POINT = 0x400
_OFFLINE = 0x1000             # fichier non disponible localement
_RECALL_ON_OPEN = 0x40000     # placeholder cloud (téléchargé à l'ouverture)
_RECALL_ON_DATA = 0x400000    # placeholder cloud (téléchargé à la lecture)
_CLOUD_ONLY = _OFFLINE | _RECALL_ON_OPEN | _RECALL_ON_DATA
_TAG_MOUNT_POINT = 0xA0000003  # jonction
_TAG_SYMLINK = 0xA000000C      # lien symbolique
# Les autres balises (OneDrive/cloud 0x9000xx1A, déduplication…) sont de VRAIS dossiers : on les suit.


class ScanCancelled(Exception):
    """Levée quand l'utilisateur annule l'analyse."""


def allocated_size(st: os.stat_result) -> int:
    """Taille réellement allouée (Unix) ou taille logique (Windows)."""
    blocks = getattr(st, "st_blocks", None)
    return blocks * 512 if blocks is not None else st.st_size


def prune(kids: List[Node]) -> List[Node]:
    """Garde les MAX_KIDS plus gros éléments et regroupe le reste."""
    if len(kids) <= MAX_KIDS:
        return kids
    kids.sort(key=lambda k: k.size, reverse=True)
    head, tail = kids[:MAX_KIDS], kids[MAX_KIDS:]
    cnt = sum(k.count for k in tail)
    head.append(Node("(%d autres)" % cnt, sum(k.size for k in tail), grouped=True, count=cnt,
                     note=OTHER_NOTE, mtime=max(k.mtime for k in tail)))
    return head


def compact(node: Node, min_size: float) -> None:
    """Fusionne les éléments trop petits pour être visibles."""
    if not node.children:
        return
    keep: List[Node] = []
    small_size = small_count = 0
    small_mtime = 0.0
    for k in node.children:
        if k.size >= min_size or k.unreadable:
            keep.append(k)
            compact(k, min_size)
        else:
            small_size += k.size
            small_count += k.count
            small_mtime = max(small_mtime, k.mtime)
    if small_count:
        keep.append(Node("(%d petits éléments)" % small_count, small_size,
                         grouped=True, count=small_count, note=SMALL_NOTE, mtime=small_mtime))
    node.children = keep


def is_cloud_only(st: os.stat_result) -> bool:
    """Vrai pour un fichier « en ligne seulement » (n'occupe pas d'espace local)."""
    return bool(getattr(st, "st_file_attributes", 0) & _CLOUD_ONLY)


class Scanner:
    """Analyse un chemin. Utilisable depuis un thread : ``cancel()`` est thread-safe."""

    def __init__(self, cross_devices: bool = False, skip: Optional[Set[str]] = None) -> None:
        self.cross_devices = cross_devices
        self.skip = DEFAULT_SKIP if skip is None else skip
        self.files = 0
        self.errors = 0
        self.cloud_files = 0
        self.cloud_bytes = 0
        self.skipped: List[SkipEntry] = []
        self.current = ""
        self._cancelled = False
        self._dev = 0

    def cancel(self) -> None:
        self._cancelled = True

    def scan(self, path: str) -> ScanResult:
        path = os.path.abspath(os.path.expanduser(path))
        t0 = time.time()
        self._dev = os.stat(path).st_dev
        if IS_MAC and path == "/":
            self.cross_devices = True
        root = self._scan_dir(path, path, 0)
        try:
            du = shutil.disk_usage(path)
            total, used, free = du.total, du.used, du.free
        except OSError:
            total = used = free = 0
        unreadable = self._add_unreadable(root, path, used)
        compact(root, max(root.size / MIN_VISIBLE, 1))
        return ScanResult(path=path, root=root, files=self.files, seconds=time.time() - t0,
                          total=total, used=used, free=free, errors=self.errors,
                          unreadable=unreadable, cloud_files=self.cloud_files,
                          cloud_bytes=self.cloud_bytes, skipped=self.skipped)

    @staticmethod
    def _add_unreadable(root: Node, path: str, used: int) -> int:
        """Ajoute l'espace « utilisé mais non lisible » (uniquement pour un disque entier)."""
        gap = used - root.size
        if not (os.path.ismount(path) and gap > 0):
            return 0
        root.children.append(Node(UNREADABLE_NAME, gap, grouped=True, count=0,
                                  unreadable=True, note=UNREADABLE_NOTE))
        root.size += gap
        return gap

    def _skip(self, path: str, reason: str, detail: str = "") -> None:
        if len(self.skipped) < MAX_SKIPPED:
            self.skipped.append(SkipEntry(path, reason, detail))

    def _scan_dir(self, path: str, name: str, depth: int) -> Node:
        if self._cancelled:
            raise ScanCancelled()
        self.current = path
        size, kids, latest, kind = 0, [], 0.0, ""
        try:
            with os.scandir(path) as it:
                for entry in it:
                    kind = project_kind(entry.name, kind)
                    try:
                        esize, emtime = self._scan_entry(entry, depth, kids)
                        size += esize
                        if emtime > latest:
                            latest = emtime
                    except PermissionError:
                        self._skip(entry.path, "denied")
                    except OSError:
                        self.errors += 1
        except PermissionError:
            self._skip(path, "denied")
        except OSError:
            self.errors += 1
        return Node(name, size, prune(kids) if depth < MAX_DEPTH else [], mtime=latest, project=kind)

    def _scan_entry(self, entry: "os.DirEntry[str]", depth: int,
                    kids: List[Node]) -> Tuple[int, float]:
        """Traite une entrée ; renvoie (taille locale, dernière modification) et l'ajoute à ``kids``."""
        if entry.is_symlink():
            self._skip(entry.path, "symlink", _readlink(entry.path))
            return 0, 0.0
        if entry.is_dir(follow_symlinks=False):
            reason, detail = self._dir_skip_reason(entry)
            if reason:
                self._skip(entry.path, reason, detail)
                return 0, 0.0
            child = self._scan_dir(entry.path, entry.name, depth + 1)
            kids.append(child)
            return child.size, child.mtime
        st = entry.stat(follow_symlinks=False)
        self.files += 1
        if is_cloud_only(st):          # placeholder OneDrive : rien sur le disque
            self.cloud_files += 1
            self.cloud_bytes += st.st_size
            return 0, 0.0
        fsize = allocated_size(st)
        if fsize:
            kids.append(Node(entry.name, fsize, mtime=st.st_mtime))
        return fsize, st.st_mtime

    def _dir_skip_reason(self, entry: "os.DirEntry[str]") -> Tuple[str, str]:
        if entry.path in self.skip:
            return "excluded", ""
        st = entry.stat(follow_symlinks=False)
        if IS_WIN:
            if getattr(st, "st_file_attributes", 0) & _REPARSE_POINT:
                tag = getattr(st, "st_reparse_tag", None)
                if tag is None or tag in (_TAG_MOUNT_POINT, _TAG_SYMLINK):
                    return "junction", _readlink(entry.path)
            return "", ""
        if not self.cross_devices and st.st_dev != self._dev:
            return "device", ""
        return "", ""


def _readlink(path: str) -> str:
    try:
        return os.readlink(path)
    except (OSError, ValueError):
        return ""
