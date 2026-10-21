"""Parcours utilitaires de l'arbre de nœuds."""
from __future__ import annotations

import re
from typing import Iterator, List, Optional, Tuple

from .models import Node

Chain = List[Tuple[Node, str]]


def join(base: str, name: str) -> str:
    sep = "\\" if "\\" in base and "/" not in base else "/"
    if base.endswith(("\\", "/")):
        return base + name
    return base + sep + name


def walk(node: Node, path: str) -> Iterator[Tuple[Node, Node, str]]:
    """Itère (parent, nœud, chemin) sur les descendants réels (hors regroupements)."""
    stack = [(node, path)]
    while stack:
        parent, ppath = stack.pop()
        for k in parent.children:
            if k.grouped:
                continue
            kpath = join(ppath, k.name)
            yield parent, k, kpath
            if k.children:
                stack.append((k, kpath))


def find_chain(root: Node, base: str, target: str) -> Optional[Chain]:
    """Chaîne [(racine, base), …, (nœud, target)] menant à ``target``, ou None."""
    norm = lambda p: p.replace("\\", "/").rstrip("/")  # noqa: E731
    b, t = norm(base), norm(target)
    if t == b:
        return [(root, base)]
    if not t.startswith(b + "/"):
        return None
    chain: Chain = [(root, base)]
    node, path = root, base
    for part in [p for p in re.split(r"/", t[len(b) + 1:]) if p]:
        nxt = next((k for k in node.children if k.name == part and not k.grouped), None)
        if nxt is None:
            return chain if len(chain) > 1 else None
        path = join(path, part)
        chain.append((nxt, path))
        node = nxt
    return chain
