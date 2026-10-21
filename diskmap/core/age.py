"""Ancienneté des fichiers (carte « froid / chaud »)."""
from __future__ import annotations

import time
from typing import Optional, Tuple

DAY = 86400
# (limite en jours, libellé) ; la dernière tranche n'a pas de limite.
BUCKETS: Tuple[Tuple[Optional[int], str], ...] = (
    (30, "< 1 mois"), (180, "< 6 mois"), (365, "< 1 an"),
    (730, "< 2 ans"), (1825, "< 5 ans"), (None, "≥ 5 ans"),
)


def age_days(mtime: float, now: Optional[float] = None) -> float:
    return ((time.time() if now is None else now) - mtime) / DAY


def age_bucket(mtime: float, now: Optional[float] = None) -> int:
    """Indice de tranche d'âge ; -1 si la date est inconnue (nœud synthétique)."""
    if mtime <= 0:
        return -1
    days = age_days(mtime, now)
    for i, (limit, _) in enumerate(BUCKETS):
        if limit is None or days < limit:
            return i
    return len(BUCKETS) - 1
