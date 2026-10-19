"""Liste triée du contenu du dossier courant (panneau de droite)."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from ..core import Node, human_size

MAX_ROWS = 500


class EntryList(ttk.Frame):
    def __init__(self, master: tk.Misc,
                 on_open: Callable[[Node], None],
                 on_select: Callable[[Node], None],
                 on_menu: Callable[[tk.Event, Node], None]) -> None:
        super().__init__(master, width=340)
        self.pack_propagate(False)
        self._on_open, self._on_select, self._on_menu = on_open, on_select, on_menu
        self._items: List[Node] = []
        self._base = ""

        self.tree = ttk.Treeview(self, columns=("size", "pct"), selectmode="browse")
        for col, text, width, anchor in (("#0", "Nom", 170, "w"), ("size", "Taille", 80, "e"),
                                         ("pct", "%", 55, "e")):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._emit(self._on_open))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._emit(self._on_select))
        self.tree.bind("<Button-3>", self._menu)

    def show(self, folder: Node, path: str) -> None:
        self._base = path
        self._items = sorted(folder.children, key=lambda k: k.size, reverse=True)[:MAX_ROWS]
        self.tree.delete(*self.tree.get_children())
        total = folder.size or 1
        for i, k in enumerate(self._items):
            icon = "📁 " if k.is_dir else "   "
            self.tree.insert("", "end", iid=str(i), text=icon + k.name,
                             values=(human_size(k.size), "%.1f%%" % (k.size / total * 100)))

    def path_of(self, node: Node) -> str:
        return os.path.join(self._base, node.name)

    def _current(self) -> Optional[Node]:
        sel = self.tree.selection()
        return self._items[int(sel[0])] if sel else None

    def _emit(self, callback: Callable[[Node], None]) -> None:
        node = self._current()
        if node is not None:
            callback(node)

    def _menu(self, e: tk.Event) -> None:
        row = self.tree.identify_row(e.y)
        if row:
            self.tree.selection_set(row)
            self._on_menu(e, self._items[int(row)])
