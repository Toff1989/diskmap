"""Barre « Couleur » : type de fichier, ancienneté ou changements, avec sa légende."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..core.age import BUCKETS
from . import theme

MODES = (("type", "Type"), ("age", "Ancienneté"), ("change", "Changements"))


class ModeBar(tk.Frame):
    def __init__(self, master: tk.Misc, on_change: Callable[[str], None]) -> None:
        super().__init__(master, bg=theme.BG2)
        self.var = tk.StringVar(value="type")
        self._on_change = on_change
        tk.Label(self, text="Couleur :", bg=theme.BG2, fg=theme.FG_DIM).pack(side="left", padx=(8, 4))
        for value, text in MODES:
            ttk.Radiobutton(self, text=text, value=value, variable=self.var,
                            command=lambda: self._on_change(self.var.get())).pack(side="left", padx=2)
        self._legend = tk.Frame(self, bg=theme.BG2)
        self._legend.pack(side="left", padx=14)

    def set_mode(self, mode: str, baseline_label: str = "") -> None:
        self.var.set(mode)
        for w in self._legend.winfo_children():
            w.destroy()
        if mode == "age":
            for i, (_limit, text) in enumerate(BUCKETS):
                self._swatch(theme.age_color(i), text)
        elif mode == "change":
            self._swatch(theme.hsl(4, 0.55, 0.38), "a grossi")
            self._swatch(theme.hsl(150, 0.55, 0.38), "a rétréci")
            if baseline_label:
                tk.Label(self._legend, text="  · Δ = actuel − " + baseline_label, bg=theme.BG2,
                         fg=theme.FG_DIM).pack(side="left")
        else:
            tk.Label(self._legend, text="une couleur par extension de fichier", bg=theme.BG2,
                     fg=theme.FG_DIM).pack(side="left")

    def _swatch(self, color: str, text: str) -> None:
        tk.Label(self._legend, text="  ", bg=color).pack(side="left", padx=(6, 2))
        tk.Label(self._legend, text=text, bg=theme.BG2, fg=theme.FG_DIM).pack(side="left")
