"""Barre de navigation : bouton « Remonter » + fil d'Ariane cliquable."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from ..core import human_size
from . import theme
from .treemap_view import Crumb


class NavBar(tk.Frame):
    def __init__(self, master: tk.Misc, on_up: Callable[[], None],
                 on_goto: Callable[[int], None]) -> None:
        super().__init__(master, bg=theme.BG)
        self._on_goto = on_goto
        self.up_btn = ttk.Button(self, text="⬆ Remonter", command=on_up, state="disabled")
        self.up_btn.pack(side="left", padx=6, pady=4)
        self._crumbs = tk.Frame(self, bg=theme.BG)
        self._crumbs.pack(side="left", fill="x", expand=True)
        self._size = tk.Label(self, bg=theme.BG, fg=theme.FG_DIM)
        self._size.pack(side="right", padx=10)

    def show(self, stack: Sequence[Crumb]) -> None:
        for w in self._crumbs.winfo_children():
            w.destroy()
        for i, (node, path) in enumerate(stack):
            if i:
                tk.Label(self._crumbs, text="›", bg=theme.BG, fg=theme.FG_DIM).pack(side="left")
            ttk.Button(self._crumbs, text=path if i == 0 else node.name, style="Crumb.TButton",
                       command=lambda i=i: self._on_goto(i)).pack(side="left")
        self._size.configure(text=human_size(stack[-1][0].size) if stack else "")
        self.up_btn.configure(state="normal" if len(stack) > 1 else "disabled")
