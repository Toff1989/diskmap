"""Barre du haut : choix du disque, lancement et annulation du scan."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence


class Toolbar(ttk.Frame):
    def __init__(self, master: tk.Misc, drives: Sequence[str], show_cross: bool,
                 on_browse: Callable[[], None], on_scan: Callable[[], None],
                 on_cancel: Callable[[], None], on_skipped: Callable[[], None]) -> None:
        super().__init__(master, padding=8)
        ttk.Label(self, text="Disque / dossier :").pack(side="left")
        self.path_var = tk.StringVar(value=drives[0] if drives else "")
        ttk.Combobox(self, textvariable=self.path_var, values=list(drives), width=34).pack(side="left", padx=6)
        ttk.Button(self, text="Parcourir…", command=on_browse).pack(side="left")
        self._scan = ttk.Button(self, text="Analyser", style="Accent.TButton", command=on_scan)
        self._scan.pack(side="left", padx=(6, 0))
        self._cancel = ttk.Button(self, text="Annuler", command=on_cancel, state="disabled")
        self._cancel.pack(side="left", padx=6)
        self._skipped = ttk.Button(self, text="Zones non lisibles", command=on_skipped, state="disabled")
        self._skipped.pack(side="left", padx=(0, 6))
        self.cross_var = tk.BooleanVar(value=False)
        if show_cross:
            ttk.Checkbutton(self, text="Traverser les autres montages",
                            variable=self.cross_var).pack(side="left", padx=6)
        self._info = ttk.Label(self, style="Dim.TLabel")
        self._info.pack(side="right")

    def set_busy(self, busy: bool) -> None:
        self._scan.configure(state="disabled" if busy else "normal")
        self._cancel.configure(state="normal" if busy else "disabled")

    def set_skipped_count(self, count: int) -> None:
        self._skipped.configure(text="Zones non lisibles (%d)" % count if count else "Zones non lisibles",
                                state="normal" if count else "disabled")

    def set_info(self, text: str) -> None:
        self._info.configure(text=text)
