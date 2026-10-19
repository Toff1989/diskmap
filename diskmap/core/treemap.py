"""Algorithme « squarified treemap » (Bruls, Huizing, van Wijk)."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from .models import Node

Rect = Tuple[Node, float, float, float, float]  # (nœud, x, y, largeur, hauteur)


def squarify(nodes: Sequence[Node], x: float, y: float, w: float, h: float) -> List[Rect]:
    """Dispose ``nodes`` dans le rectangle (x, y, w, h) avec des aires proportionnelles aux tailles."""
    nodes = [n for n in nodes if n.size > 0]
    if w < 1 or h < 1 or not nodes:
        return []
    nodes.sort(key=lambda n: n.size, reverse=True)
    k = w * h / float(sum(n.size for n in nodes))  # pixels² par octet

    out: List[Rect] = []
    row: List[Node] = []
    rx, ry, rw, rh = x, y, w, h

    def worst(r: List[Node], side: float) -> float:
        areas = [n.size * k for n in r]
        s = sum(areas)
        return max(side * side * max(areas) / (s * s), s * s / (side * side * min(areas)))

    def place() -> None:
        nonlocal rx, ry, rw, rh, row
        s = sum(n.size * k for n in row)
        if rw >= rh:  # colonne verticale à gauche
            c = s / rh
            cy = ry
            for n in row:
                hh = n.size * k / c
                out.append((n, rx, cy, c, hh))
                cy += hh
            rx += c
            rw -= c
        else:         # rangée horizontale en haut
            c = s / rw
            cx = rx
            for n in row:
                ww = n.size * k / c
                out.append((n, cx, ry, ww, c))
                cx += ww
            ry += c
            rh -= c
        row = []

    i = 0
    while i < len(nodes):
        side = min(rw, rh)
        if side <= 0:
            break
        if not row or worst(row + [nodes[i]], side) <= worst(row, side):
            row.append(nodes[i])
            i += 1
        else:
            place()
    if row:
        place()
    return out
