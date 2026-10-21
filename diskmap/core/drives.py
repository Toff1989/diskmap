"""Détection des disques (Windows) et points de montage (Linux)."""
from __future__ import annotations

import os
import string
from typing import Dict, List


def detect_drives() -> List[str]:
    """Liste les racines analysables ; repli sur le dossier personnel."""
    if os.name == "nt":
        out = [l + ":\\" for l in string.ascii_uppercase if os.path.exists(l + ":\\")]
    else:
        out = _linux_mounts()
    return out or [os.path.expanduser("~")]


def _linux_mounts() -> List[str]:
    best: Dict[str, str] = {}
    try:
        with open("/proc/mounts") as f:
            for line in f:
                dev, mp, fs = line.split()[:3]
                mp = mp.replace("\\040", " ")
                wsl = fs in ("9p", "drvfs") and mp.startswith("/mnt/")
                if not (dev.startswith("/dev/") or wsl) or dev.startswith("/dev/loop"):
                    continue
                if mp.startswith(("/boot", "/snap", "/var/snap")):
                    continue
                if dev not in best or len(mp) < len(best[dev]):
                    best[dev] = mp
    except OSError:
        pass
    return sorted(best.values())
