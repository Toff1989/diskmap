"""Petits utilitaires d'affichage de texte."""
from __future__ import annotations


def shorten_middle(text: str, limit: int = 60) -> str:
    """Raccourcit au milieu (« C:\\Users\\…\\webapp\\node_modules ») : la fin d'un chemin est la partie utile."""
    if len(text) <= limit or limit < 8:
        return text
    tail = (limit - 1) * 2 // 3
    head = limit - 1 - tail
    return text[:head] + "…" + text[-tail:]
