"""Comparaison de deux arbres : carte des changements (instantanés, deux dossiers, surveillance)."""
from __future__ import annotations

from typing import Dict, List

from .formatting import human_size, signed_size
from .models import Node

OTHER_NAME = "(autres changements)"


def _index(node: Node) -> Dict[str, Node]:
    return {k.name: k for k in node.children if not k.grouped or k.unreadable}


def _one_sided(node: Node, sign: int) -> Node:
    """Sous-arbre présent d'un seul côté : tout y est ajouté (+1) ou supprimé (-1)."""
    kids = [_one_sided(k, sign) for k in node.children if k.size > 0]
    note = ("Nouveau : " if sign > 0 else "Supprimé : ") + human_size(node.size)
    out = Node(node.name, node.size, kids, grouped=node.grouped, count=node.count,
               unreadable=node.unreadable, note=note, mtime=node.mtime, project=node.project,
               delta=sign * node.size)
    return out


def diff_trees(old: Node, new: Node) -> Node:
    """Arbre des changements ``new - old`` : taille = ampleur, ``delta`` = variation signée.

    Les éléments inchangés disparaissent ; les regroupements (« petits éléments »…) sont
    ramenés à un résidu « (autres changements) » pour ne pas dépendre de leur libellé.
    """
    root = _diff(old, new)
    if root is None:
        return Node(new.name, 0, [], delta=0, mtime=new.mtime)
    return root


def _diff(old: Node, new: Node) -> "Node | None":
    net = new.size - old.size
    oi, ni = _index(old), _index(new)
    kids: List[Node] = []
    for name in sorted(set(oi) | set(ni)):
        o, n = oi.get(name), ni.get(name)
        if o is not None and n is not None:
            d = _diff(o, n)
            if d is not None:
                kids.append(d)
        elif n is not None and n.size > 0:
            kids.append(_one_sided(n, +1))
        elif o is not None and o.size > 0:
            kids.append(_one_sided(o, -1))
    residual = net - sum(k.delta for k in kids) if (old.children or new.children) else 0
    if residual:
        kids.append(Node(OTHER_NAME, abs(residual), grouped=True, delta=residual,
                         note="Variation répartie sur des éléments trop petits pour être détaillés : "
                              + signed_size(residual)))
    if net == 0 and not kids:
        return None
    size = sum(k.size for k in kids) if kids else abs(net)
    note = "%s → %s (%s)" % (human_size(old.size), human_size(new.size), signed_size(net))
    return Node(new.name, size, kids, delta=net, note=note,
                mtime=max(old.mtime, new.mtime), project=new.project or old.project)


def growth_map(diff: Node, base: str, min_delta: int = 1) -> Dict[str, int]:
    """Chemin -> variation, pour les éléments qui ont grossi (surveillance en direct)."""
    from .tree import walk
    out: Dict[str, int] = {}
    for _parent, k, path in walk(diff, base):
        if k.delta >= min_delta:
            out[path] = k.delta
    if diff.delta >= min_delta:
        out[base] = diff.delta
    return out
