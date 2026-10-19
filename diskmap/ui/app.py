"""Fenêtre principale : assemble les widgets et pilote le scan."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from ..core import Node, ScanCancelled, Scanner, ScanResult, detect_drives, human_size
from . import theme
from .entry_list import EntryList
from .navbar import NavBar
from .skipped_dialog import SkippedDialog
from .system import reveal_in_file_manager
from .toolbar import Toolbar
from .treemap_view import Crumb, Hit, TreemapView

HELP = ("Clic : zoom · Échap / Retour / Remonter : remonter · "
        "Clic droit : menu · Couleur = extension · F5 : réanalyser")
POLL_MS = 100


class App(tk.Tk):
    def __init__(self, start_path: Optional[str] = None, admin: bool = False) -> None:
        super().__init__()
        self.title("DiskMap (administrateur)" if admin else "DiskMap")
        self.geometry("1280x800")
        self.minsize(800, 500)
        theme.apply(self)

        self.result: Optional[ScanResult] = None
        self.stack: List[Crumb] = []
        self._selected: Optional[str] = None
        self._scanner: Optional[Scanner] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: "queue.Queue[tuple]" = queue.Queue()

        self._build()
        self.bind("<Escape>", lambda e: self.up())
        self.bind("<BackSpace>", lambda e: self.up())
        self.bind("<F5>", lambda e: self.start_scan())
        self.after(POLL_MS, self._poll)
        if start_path:
            self.toolbar.path_var.set(start_path)
            self.after(200, self.start_scan)

    # -- construction --
    def _build(self) -> None:
        self.toolbar = Toolbar(self, detect_drives(), show_cross=os.name != "nt",
                               on_browse=self.browse, on_scan=self.start_scan,
                               on_cancel=self.cancel_scan, on_skipped=self.show_skipped)
        self.toolbar.pack(fill="x")
        self.navbar = NavBar(self, on_up=self.up, on_goto=self.goto)
        self.navbar.pack(fill="x")

        self.status = tk.Label(self, anchor="w", justify="left", bg=theme.BG2, fg=theme.FG_DIM,
                               padx=8, pady=3, text="Choisis un disque puis clique sur « Analyser ».")
        self.status.pack(fill="x", side="bottom")
        self.progress = ttk.Progressbar(self, mode="indeterminate")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.entries = EntryList(body, on_open=self._open_entry, on_select=self._select_entry,
                                 on_menu=self._entry_menu)
        self.entries.pack(side="right", fill="y")
        self.view = TreemapView(body, on_zoom=self._zoom, on_select=self._select_hit,
                                on_hover=self._hover, on_menu=self._view_menu)
        self.view.pack(side="left", fill="both", expand=True)

        self.menu = tk.Menu(self, tearoff=0, bg=theme.BG3, fg=theme.FG,
                            activebackground=theme.ACCENT, activeforeground="#fff")

    # -- scan --
    def browse(self) -> None:
        folder = filedialog.askdirectory(title="Choisir un dossier à analyser")
        if folder:
            self.toolbar.path_var.set(os.path.normpath(folder))
            self.start_scan()

    def start_scan(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        path = os.path.abspath(os.path.expanduser(self.toolbar.path_var.get().strip()))
        if not os.path.isdir(path):
            messagebox.showerror("DiskMap", "Dossier inaccessible :\n%s" % path)
            return
        self._scanner = Scanner(cross_devices=self.toolbar.cross_var.get())
        self.toolbar.set_busy(True)
        self.progress.pack(fill="x", side="bottom", before=self.status)
        self.progress.start(12)
        self._thread = threading.Thread(target=self._run_scan, args=(self._scanner, path), daemon=True)
        self._thread.start()

    def _run_scan(self, scanner: Scanner, path: str) -> None:
        try:
            self._queue.put(("done", scanner.scan(path)))
        except ScanCancelled:
            self._queue.put(("cancel", None))
        except Exception as exc:  # noqa: BLE001 - remonté à l'UI
            self._queue.put(("error", exc))

    def cancel_scan(self) -> None:
        if self._scanner:
            self._scanner.cancel()

    def _poll(self) -> None:
        try:
            kind, value = self._queue.get_nowait()
        except queue.Empty:
            kind = value = None
        if kind:
            self.progress.stop()
            self.progress.pack_forget()
            self.toolbar.set_busy(False)
            if kind == "done":
                self._show_result(value)
            elif kind == "cancel":
                self._set_status("Analyse annulée.")
            else:
                messagebox.showerror("DiskMap", "Erreur pendant l'analyse :\n%s" % value)
        elif self._thread and self._thread.is_alive() and self._scanner:
            cur = self._scanner.current
            if len(cur) > 90:
                cur = cur[:40] + "…" + cur[-48:]
            self._set_status("Analyse… %s fichiers · %s" % (format(self._scanner.files, ","), cur))
        self.after(POLL_MS, self._poll)

    def _show_result(self, r: ScanResult) -> None:
        self.result = r
        self.stack = [(r.root, r.path)]
        self._selected = None
        parts = []
        if r.total:
            parts.append("Total %s · Utilisé %s · Libre %s" % (human_size(r.total), human_size(r.used),
                                                                human_size(r.free)))
        parts.append("%s fichiers · %.0f s" % (format(r.files, ","), r.seconds))
        if r.cloud_files:
            parts.append("☁ %s en ligne seulement (hors disque)" % human_size(r.cloud_bytes))
        self.toolbar.set_info(" · ".join(parts))
        self.toolbar.set_skipped_count(len(r.skipped) + (1 if r.unreadable else 0))
        self._set_status(HELP)
        self._refresh()

    # -- navigation --
    def _refresh(self) -> None:
        self.view.show(self.stack, self._selected)
        self.navbar.show(self.stack)
        self.entries.show(*self.stack[-1])

    def _zoom(self, chain: List[Crumb]) -> None:
        self.stack = list(chain)
        self._selected = None
        self._refresh()

    def goto(self, index: int) -> None:
        del self.stack[index + 1:]
        self._selected = None
        self._refresh()

    def up(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()
            self._selected = None
            self._refresh()

    # -- événements des widgets --
    def _select_hit(self, hit: Hit) -> None:
        self._selected = hit.path
        self.view.select(hit.path)

    def _hover(self, hit: Optional[Hit]) -> None:
        if self._thread and self._thread.is_alive():
            return
        if hit is None or not self.stack:
            self._set_status(HELP if self.stack else "")
            return
        total = self.stack[-1][0].size or 1
        text = "%s   —   %s  (%.2f %% du dossier affiché)" % (
            hit.path, human_size(hit.node.size), hit.node.size / total * 100)
        if hit.node.note:
            text += "\nℹ " + hit.node.note
        self._set_status(text)

    def _open_entry(self, node: Node) -> None:
        if node.is_dir:
            self._zoom(self.stack + [(node, self.entries.path_of(node))])

    def show_skipped(self) -> None:
        if self.result:
            SkippedDialog(self, self.result.skipped, self.result.unreadable,
                          self.result.cloud_files, self.result.cloud_bytes)

    def _select_entry(self, node: Node) -> None:
        if node.grouped:
            self._set_status("%s   —   %s\nℹ %s" % (node.name, human_size(node.size), node.note))
            return
        path = self.entries.path_of(node)
        self._selected = path
        self.view.select(path)
        self._set_status("%s   —   %s" % (path, human_size(node.size)))

    # -- menus contextuels --
    def _view_menu(self, e: tk.Event, hit: Optional[Hit]) -> None:
        self._popup(e, hit.path if hit and not hit.node.grouped else None)

    def _entry_menu(self, e: tk.Event, node: Node) -> None:
        self._popup(e, None if node.grouped else self.entries.path_of(node))

    def _popup(self, e: tk.Event, path: Optional[str]) -> None:
        self.menu.delete(0, "end")
        if path:
            self.menu.add_command(label="Ouvrir l'emplacement", command=lambda: self._reveal(path))
            self.menu.add_command(label="Copier le chemin", command=lambda: self._copy(path))
            self.menu.add_separator()
        self.menu.add_command(label="Remonter", command=self.up,
                              state="normal" if len(self.stack) > 1 else "disabled")
        self.menu.tk_popup(e.x_root, e.y_root)

    def _reveal(self, path: str) -> None:
        try:
            reveal_in_file_manager(path)
        except OSError as exc:
            messagebox.showerror("DiskMap", str(exc))

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Chemin copié : " + text)

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)
