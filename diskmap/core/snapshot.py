"""Instantanés : sauvegarde compressée d'une analyse pour la comparer plus tard."""
from __future__ import annotations

import gzip
import json
import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional

from .models import Node, ScanResult

FORMAT = 1
KEEP_PER_PATH = 30        # instantanés conservés par chemin (les plus anciens sont supprimés)


def snapshot_dir() -> str:
    """Dossier des instantanés (``DISKMAP_HOME`` pour le changer)."""
    base = os.environ.get("DISKMAP_HOME") or os.path.join(os.path.expanduser("~"), ".diskmap")
    return os.path.join(base, "snapshots")


@dataclass
class SnapshotInfo:
    file: str
    path: str
    created: float
    size: int          # taille de l'arbre analysé
    files: int
    used: int = 0
    total: int = 0

    @property
    def label(self) -> str:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(self.created))


def _encode(n: Node) -> list:
    flags = (1 if n.grouped else 0) | (2 if n.unreadable else 0)
    return [n.name, n.size, round(n.mtime), flags, n.count, n.project, n.note if flags else "",
            [_encode(k) for k in n.children]]


def _decode(a: list) -> Node:
    name, size, mtime, flags, count, project, note, kids = a
    return Node(name, size, [_decode(k) for k in kids], grouped=bool(flags & 1), count=count,
                unreadable=bool(flags & 2), note=note, mtime=float(mtime), project=project)


def _slug(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")[-60:] or "root"


def save_snapshot(result: ScanResult, directory: Optional[str] = None,
                  created: Optional[float] = None) -> str:
    directory = directory or snapshot_dir()
    os.makedirs(directory, exist_ok=True)
    created = time.time() if created is None else created
    meta = {"format": FORMAT, "path": result.path, "created": created, "size": result.root.size,
            "files": result.files, "used": result.used, "total": result.total}
    name = "%s__%d.json.gz" % (_slug(result.path), int(created * 1000))
    file = os.path.join(directory, name)
    tmp = file + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
        f.write(json.dumps(meta) + "\n")
        f.write(json.dumps(_encode(result.root), separators=(",", ":")))
    os.replace(tmp, file)
    _rotate(directory, result.path)
    return file


def _read_meta(file: str) -> Optional[SnapshotInfo]:
    try:
        with gzip.open(file, "rt", encoding="utf-8") as f:
            meta = json.loads(f.readline())
        return SnapshotInfo(file, meta["path"], meta["created"], meta["size"], meta["files"],
                            meta.get("used", 0), meta.get("total", 0))
    except (OSError, ValueError, KeyError, EOFError):
        return None


def list_snapshots(path: Optional[str] = None, directory: Optional[str] = None) -> List[SnapshotInfo]:
    """Instantanés (récents d'abord), éventuellement limités à un chemin analysé."""
    directory = directory or snapshot_dir()
    try:
        names = [n for n in os.listdir(directory) if n.endswith(".json.gz")]
    except OSError:
        return []
    out = [i for i in (_read_meta(os.path.join(directory, n)) for n in names) if i]
    if path is not None:
        out = [i for i in out if os.path.normcase(i.path) == os.path.normcase(path)]
    out.sort(key=lambda i: i.created, reverse=True)
    return out


def load_snapshot(file: str) -> ScanResult:
    with gzip.open(file, "rt", encoding="utf-8") as f:
        meta = json.loads(f.readline())
        root = _decode(json.loads(f.readline()))
    return ScanResult(path=meta["path"], root=root, files=meta["files"], seconds=0.0,
                      total=meta.get("total", 0), used=meta.get("used", 0))


def _rotate(directory: str, path: str) -> None:
    for old in list_snapshots(path, directory)[KEEP_PER_PATH:]:
        try:
            os.remove(old.file)
        except OSError:
            pass
