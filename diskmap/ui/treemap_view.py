"""Widget canvas qui dessine la treemap et gère la souris."""
from __future__ import annotations

import os
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ..core import Node, age_bucket, human_size, signed_size, squarify
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
        self._mode = "type"                      # "type" | "age" | "change"
        self._now = time.time()
        self._highlight: Dict[str, str] = {}     # chemin -> couleur (groupes de doublons)
        self._highlight_dirs: Set[str] = set()   # dossiers qui contiennent un élément surligné
        self._growth: Dict[str, int] = {}        # chemin -> octets gagnés (surveillance)

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

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_highlight(self, colors: Dict[str, str]) -> None:
        """Entoure ces chemins (couleur par chemin) ; les dossiers parents reçoivent un pointillé."""
        self._highlight = dict(colors)
        dirs: Set[str] = set()
        for p in colors:
            q = p.replace("\\", "/")
            while "/" in q.rstrip("/"):
                q = q.rstrip("/").rsplit("/", 1)[0]
                dirs.add(q)
        self._highlight_dirs = dirs
        self._draw_overlays()

    def set_growth(self, growth: Dict[str, int]) -> None:
        self._growth = dict(growth)
        self._draw_overlays()

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
        self._now = time.time()
        self._draw(self._stack[-1][0], 0, 0, self.winfo_width(), self.winfo_height(), 0, self._stack)
        self._draw_overlays()
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
            fill = self._fill(node, depth)
            self.create_rectangle(rx, ry, rx + rw, ry + rh, fill=fill, outline=theme.BG)
            shown = signed_size(node.delta) if self._mode == "change" else human_size(node.size)
            label = "%s  %s" % (node.name, shown)
            if node.is_dir and depth < _NEST_DEPTH and rw > 40 and rh > 34:
                self._label(label, rx, ry, rw)
                self._draw(node, rx + 2, ry + _HEADER, rw - 4, rh - _HEADER - 2, depth + 1, sub)
            elif rw > 46 and rh > 16:
                self._label(label, rx, ry, rw)

    def _fill(self, node: Node, depth: int) -> str:
        if self._mode == "change":
            if node.unreadable:
                return theme.UNREADABLE
            scale = self._stack[-1][0].size if self._stack else 0
            return theme.delta_color(node.delta, scale / 5.0 if node.is_dir else scale / 10.0)
        if node.unreadable:
            return theme.UNREADABLE
        if node.grouped:
            return theme.GROUPED
        if self._mode == "age":
            return theme.age_color(age_bucket(node.mtime, self._now), dim=node.is_dir)
        if node.is_dir:
            return theme.folder_color(depth)
        return theme.extension_color(node.name)

    def _label(self, text: str, x: float, y: float, w: float) -> None:
        max_chars = int((w - 8) / _CHAR_W)
        if max_chars < 3:
            return
        if len(text) > max_chars:
            text = text[:max_chars - 1] + "…"
        self.create_text(x + 4, y + 3, text=text, anchor="nw", fill="#fff", font=theme.FONT)

    def _draw_overlays(self) -> None:
        self.delete("ov")
        if not (self._highlight or self._growth):
            return
        for hit in self._hits:
            color = self._highlight.get(hit.path)
            if color:
                self.create_rectangle(hit.x + 1, hit.y + 1, hit.x + hit.w - 1, hit.y + hit.h - 1,
                                      outline=color, width=3, tags="ov")
            elif hit.node.is_dir and hit.path.replace("\\", "/") in self._highlight_dirs:
                self.create_rectangle(hit.x + 1, hit.y + 1, hit.x + hit.w - 1, hit.y + hit.h - 1,
                                      outline="#ff4fd8", width=1, dash=(3, 3), tags="ov")
            if hit.path in self._growth:
                self.create_rectangle(hit.x + 2, hit.y + 2, hit.x + hit.w - 2, hit.y + hit.h - 2,
                                      outline=theme.GROWTH_OUTLINE, width=2, tags="ov")
        self.tag_raise("sel")

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
