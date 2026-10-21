"""Détection de fichiers en double (taille, puis empreinte partielle, puis empreinte complète)."""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .scanner import DEFAULT_SKIP, ScanCancelled

PARTIAL = 64 * 1024
CHUNK = 1024 * 1024


@dataclass
class DupGroup:
    size: int
    paths: List[str]

    @property
    def reclaimable(self) -> int:
        """Espace libéré en ne gardant qu'un exemplaire."""
        return self.size * (len(self.paths) - 1)


@dataclass
class DupResult:
    groups: List[DupGroup] = field(default_factory=list)
    scanned: int = 0
    seconds: float = 0.0

    @property
    def reclaimable(self) -> int:
        return sum(g.reclaimable for g in self.groups)


def _hash(path: str, limit: Optional[int] = None) -> Optional[bytes]:
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            if limit is not None:
                h.update(f.read(limit))
            else:
                while True:
                    block = f.read(CHUNK)
                    if not block:
                        break
                    h.update(block)
    except OSError:
        return None
    return h.digest()


class DuplicateFinder:
    """Utilisable depuis un thread : ``cancel()`` est thread-safe, ``current``/``files`` informent."""

    def __init__(self, min_size: int = 1 << 20, skip: Optional[Set[str]] = None,
                 cross_devices: bool = False) -> None:
        self.min_size = max(min_size, 1)
        self.skip = DEFAULT_SKIP if skip is None else skip
        self.cross_devices = cross_devices
        self.files = 0
        self.current = ""
        self.phase = "Parcours"
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _check(self) -> None:
        if self._cancelled:
            raise ScanCancelled()

    def find(self, path: str) -> DupResult:
        t0 = time.time()
        path = os.path.abspath(os.path.expanduser(path))
        by_size: Dict[int, List[str]] = {}
        seen: Set[Tuple[int, int]] = set()      # (périphérique, inode) : ignore les liens physiques
        dev = os.stat(path).st_dev
        stack = [path]
        while stack:
            self._check()
            d = stack.pop()
            self.current = d
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_symlink() or e.path in self.skip:
                                continue
                            if e.is_dir(follow_symlinks=False):
                                if self.cross_devices or e.stat(follow_symlinks=False).st_dev == dev:
                                    stack.append(e.path)
                                continue
                            st = e.stat(follow_symlinks=False)
                        except OSError:
                            continue
                        self.files += 1
                        if st.st_size < self.min_size:
                            continue
                        if st.st_ino:
                            key = (st.st_dev, st.st_ino)
                            if key in seen:
                                continue
                            seen.add(key)
                        by_size.setdefault(st.st_size, []).append(e.path)
            except OSError:
                continue

        self.phase = "Empreintes"
        groups: List[DupGroup] = []
        for size, paths in by_size.items():
            if len(paths) < 2:
                continue
            for same in self._split(paths, PARTIAL if size > PARTIAL else None):
                if size > PARTIAL:
                    for full in self._split(same, None):
                        groups.append(DupGroup(size, sorted(full)))
                else:
                    groups.append(DupGroup(size, sorted(same)))
        groups.sort(key=lambda g: g.reclaimable, reverse=True)
        return DupResult(groups, self.files, time.time() - t0)

    def _split(self, paths: List[str], limit: Optional[int]) -> List[List[str]]:
        buckets: Dict[bytes, List[str]] = {}
        for p in paths:
            self._check()
            self.current = p
            digest = _hash(p, limit)
            if digest is not None:
                buckets.setdefault(digest, []).append(p)
        return [b for b in buckets.values() if len(b) > 1]
