"""Widget canvas qui dessine la treemap et gère la souris."""
from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from ..core import Node, human_size, squarify
from . import theme

Crumb = Tuple[Node, str]  # (nœud, chemin complet)

_NEST_DEPTH = 2     # niveaux de dossiers dessinés imbriqués
_HEADER = 16        # hauteur de l'en-tête d'un dossier imbriqué
_CHAR_W = 6.2       # largeur approximative d'un caractère de la police des étiquettes


@dataclass
class Hit:
    node: Node
    x: float
    y: float
    w: float
    h: float
    path: str
    chain: List[Crumb]

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


class TreemapView(tk.Canvas):
    def __init__(self, master: tk.Misc,
                 on_zoom: Callable[[List[Crumb]], None],
                 on_select: Callable[[Optional[Hit]], None],
                 on_hover: Callable[[Optional[Hit]], None],
                 on_menu: Callable[[tk.Event, Optional[Hit]], None]) -> None:
        super().__init__(master, bg=theme.BG, highlightthickness=0)
        self._on_zoom, self._on_select = on_zoom, on_select
        self._on_hover, self._on_menu = on_hover, on_menu
        self._stack: List[Crumb] = []
        self._selected: Optional[str] = None
        self._hits: List[Hit] = []
        self._job: Optional[str] = None

        self.bind("<Configure>", lambda e: self._schedule())
        self.bind("<Motion>", lambda e: self._on_hover(self._find(e.x, e.y)))
        self.bind("<Leave>", lambda e: self._on_hover(None))
        self.bind("<Button-1>", self._click)
        self.bind("<Button-2>", lambda e: self._on_menu(e, self._find(e.x, e.y)))
        self.bind("<Button-3>", lambda e: self._on_menu(e, self._find(e.x, e.y)))
        self._placeholder()

    # -- API publique --
    def show(self, stack: Sequence[Crumb], selected: Optional[str] = None) -> None:
        self._stack = list(stack)
        self._selected = selected
        self.redraw()

    def select(self, path: Optional[str]) -> None:
        """Met en évidence un chemin sans tout redessiner."""
        self._selected = path
        self._draw_selection()

    def clear(self) -> None:
        self._stack, self._hits = [], []
        self._placeholder()

    # -- dessin --
    def _schedule(self) -> None:
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(80, self.redraw)

    def redraw(self) -> None:
        self._job = None
        self.delete("all")
        self._hits = []
        if not self._stack:
            self._placeholder()
            return
        self._draw(self._stack[-1][0], 0, 0, self.winfo_width(), self.winfo_height(), 0, self._stack)
        self._draw_selection()

    def _placeholder(self) -> None:
        self.delete("all")
        self.create_text(self.winfo_width() // 2 or 400, self.winfo_height() // 2 or 250,
                         text="Aucune analyse", fill=theme.FG_DIM, font=("Segoe UI", 14))

    def _draw(self, parent: Node, x: float, y: float, w: float, h: float,
              depth: int, chain: List[Crumb]) -> None:
        if w < 3 or h < 3:
            return
        base = chain[-1][1]
        for node, rx, ry, rw, rh in squarify(parent.children, x, y, w, h):
            if rw < 1.5 or rh < 1.5:
                continue
            path = node.name if node.grouped else os.path.join(base, node.name)
            sub = chain + [(node, path)]
            self._hits.append(Hit(node, rx, ry, rw, rh, path, sub))
            if node.unreadable:
                fill = theme.UNREADABLE
            elif node.grouped:
                fill = theme.GROUPED
            elif node.is_dir:
                fill = theme.folder_color(depth)
            else:
                fill = theme.extension_color(node.name)
            self.create_rectangle(rx, ry, rx + rw, ry + rh, fill=fill, outline=theme.BG)
            label = "%s  %s" % (node.name, human_size(node.size))
            if node.is_dir and depth < _NEST_DEPTH and rw > 40 and rh > 34:
                self._label(label, rx, ry, rw)
                self._draw(node, rx + 2, ry + _HEADER, rw - 4, rh - _HEADER - 2, depth + 1, sub)
            elif rw > 46 and rh > 16:
                self._label(label, rx, ry, rw)

    def _label(self, text: str, x: float, y: float, w: float) -> None:
        max_chars = int((w - 8) / _CHAR_W)
        if max_chars < 3:
            return
        if len(text) > max_chars:
            text = text[:max_chars - 1] + "…"
        self.create_text(x + 4, y + 3, text=text, anchor="nw", fill="#fff", font=theme.FONT)

    def _draw_selection(self) -> None:
        self.delete("sel")
        if not self._selected:
            return
        for hit in self._hits:
            if hit.path == self._selected:
                self.create_rectangle(hit.x + 1, hit.y + 1, hit.x + hit.w - 1, hit.y + hit.h - 1,
                                      outline=theme.SELECTION, width=2, tags="sel")
                return

    # -- souris --
    def _find(self, px: float, py: float) -> Optional[Hit]:
        for hit in reversed(self._hits):  # le plus profond est dessiné en dernier
            if hit.contains(px, py):
                return hit
        return None

    def _click(self, e: tk.Event) -> None:
        hit = self._find(e.x, e.y)
        if hit is None:
            return
        if hit.node.is_dir:
            self._on_zoom(hit.chain)
        else:
            self._on_select(hit)
