"""Fenêtre listant les dossiers non analysés et pourquoi."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List

from ..core import REASON_LABEL, SkipEntry, explain, human_size
from ..elevation import is_admin
from . import theme
from .system import reveal_in_file_manager

_ORDER = {"denied": 0, "junction": 1, "symlink": 2, "device": 3, "excluded": 4}


class SkippedDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, skipped: List[SkipEntry], unreadable: int,
                 cloud_files: int, cloud_bytes: int) -> None:
        super().__init__(master, bg=theme.BG2)
        self.title("Zones non lisibles")
        self.geometry("1000x560")
        self.transient(master)

        lines = []
        if unreadable:
            lines.append("• %s occupés mais impossibles à détailler (bloc rouge dans la carte)."
                         % human_size(unreadable))
        denied = sum(1 for s in skipped if s.reason == "denied")
        if denied:
            hint = ("même en administrateur, Windows les réserve au système."
                    if is_admin() else "relance DiskMap en administrateur pour en lire davantage.")
            lines.append("• %d dossier(s) protégé(s) : %s" % (denied, hint))
        links = sum(1 for s in skipped if s.reason in ("junction", "symlink"))
        if links:
            lines.append("• %d alias/lien(s) ignorés : ils redirigent vers un dossier déjà compté (pas de double comptage)." % links)
        if cloud_files:
            lines.append("• %d fichier(s) « en ligne seulement » (%s) : visibles dans OneDrive mais sans espace local."
                         % (cloud_files, human_size(cloud_bytes)))
        ttk.Label(self, text="\n".join(lines) or "Rien n'a été ignoré.", justify="left",
                  padding=10).pack(fill="x")

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = ttk.Treeview(frame, columns=("reason", "why"), selectmode="browse")
        self.tree.heading("#0", text="Dossier")
        self.tree.heading("reason", text="Raison")
        self.tree.heading("why", text="Explication")
        self.tree.column("#0", width=360)
        self.tree.column("reason", width=120, stretch=False)
        self.tree.column("why", width=480)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for i, s in enumerate(sorted(skipped, key=lambda s: (_ORDER.get(s.reason, 9), s.path.lower()))):
            self.tree.insert("", "end", iid=str(i), text=s.path,
                             values=(REASON_LABEL.get(s.reason, s.reason), explain(s.path, s.reason, s.detail)))
        self.tree.bind("<Double-1>", self._reveal)
        ttk.Label(self, text="Double-clic : ouvrir l'emplacement dans l'Explorateur.",
                  style="Dim.TLabel", padding=(10, 0, 10, 8)).pack(anchor="w")

    def _reveal(self, _event: tk.Event) -> None:
        sel = self.tree.selection()
        if sel:
            try:
                reveal_in_file_manager(self.tree.item(sel[0], "text"))
            except OSError:
                pass
