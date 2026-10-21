"""Fenêtre principale : assemble les widgets et pilote le scan."""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from .. import __version__
from ..core import (Node, ScanCancelled, Scanner, ScanResult, SnapshotInfo, detect_drives, diff_trees,
                    export_html, find_chain, find_cleanup, find_cold, find_projects, growth_map,
                    human_size, list_snapshots, load_snapshot, save_snapshot, signed_size)
from . import theme
from .dialogs import CleanupDialog, DuplicatesDialog, ProjectsDialog, SnapshotDialog
from .entry_list import EntryList
from .modebar import ModeBar
from .navbar import NavBar
from .safe_after import cancel_all_after
from .skipped_dialog import SkippedDialog
from .system import reveal_in_file_manager
from .toolbar import Toolbar
from .treemap_view import Crumb, Hit, TreemapView

HELP = ("Clic : zoom · Échap / Retour / Remonter : remonter · "
        "Clic droit : menu · F5 : réanalyser")
POLL_MS = 100
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class App(tk.Tk):
    def __init__(self, start_path: Optional[str] = None, admin: bool = False) -> None:
        super().__init__()
        self.admin = admin
        self.title("DiskMap (administrateur)" if admin else "DiskMap")
        self.geometry("1280x800")
        self.minsize(800, 500)
        theme.apply(self)
        self._set_icon()

        self.result: Optional[ScanResult] = None
        self.mode = "type"                                   # "type" | "age" | "change"
        self.baseline: Optional[Tuple[str, Node]] = None     # (libellé, arbre) de la comparaison
        self.diff_root: Optional[Node] = None
        self._stacks: Dict[str, List[Crumb]] = {"normal": [], "change": []}
        self._selected: Optional[str] = None
        self._scanner: Optional[Scanner] = None
        self._thread: Optional[threading.Thread] = None
        self._purpose = "main"                               # "main" | "compare" | "live"
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._live_job: Optional[str] = None
        self.auto_snap = tk.BooleanVar(value=True)
        self.live_var = tk.BooleanVar(value=False)
        self.live_secs = tk.IntVar(value=10)

        self._build()
        self.bind("<Escape>", lambda e: self.up())
        self.bind("<BackSpace>", lambda e: self.up())
        self.bind("<F5>", lambda e: self.start_scan())
        self.after(POLL_MS, self._poll)
        if start_path:
            self.toolbar.path_var.set(start_path)
            self.after(200, self.start_scan)

    # -- pile de navigation (une par mode d'affichage) --
    @property
    def stack(self) -> List[Crumb]:
        return self._stacks["change" if self.mode == "change" else "normal"]

    @stack.setter
    def stack(self, value: List[Crumb]) -> None:
        self._stacks["change" if self.mode == "change" else "normal"] = value

    def destroy(self) -> None:
        cancel_all_after(self)       # voir safe_after : des minuteurs orphelins peuvent faire planter Tk
        super().destroy()

    # -- construction --
    def _set_icon(self) -> None:
        """Icône de la fenêtre, de la barre des tâches et d'Alt-Tab (aussi hors exécutable packagé)."""
        try:
            big = tk.PhotoImage(file=os.path.join(ASSETS, "icon.png"))   # 512 px
            self._icons = [big.subsample(8), big.subsample(4), big.subsample(2)]   # 64, 128, 256
            self.iconphoto(True, *self._icons)
        except tk.TclError:
            pass
        if os.name == "nt":
            try:
                self.iconbitmap(os.path.join(ASSETS, "icon.ico"))
            except tk.TclError:
                pass

    def _build(self) -> None:
        self._build_menu()
        self.toolbar = Toolbar(self, detect_drives(), show_cross=os.name != "nt",
                               on_browse=self.browse, on_scan=self.start_scan,
                               on_cancel=self.cancel_scan, on_skipped=self.show_skipped)
        self.toolbar.pack(fill="x")
        self.navbar = NavBar(self, on_up=self.up, on_goto=self.goto)
        self.navbar.pack(fill="x")
        self.modebar = ModeBar(self, on_change=self._set_mode)
        self.modebar.pack(fill="x")
        self.modebar.set_mode("type")

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

    def _build_menu(self) -> None:
        bar = tk.Menu(self)
        f = tk.Menu(bar, tearoff=0)
        f.add_command(label="Exporter un rapport HTML…", command=self.export_report)
        f.add_command(label="Enregistrer un instantané maintenant", command=self.save_snapshot_now)
        f.add_checkbutton(label="Instantané automatique après chaque analyse", variable=self.auto_snap)
        f.add_separator()
        f.add_command(label="Quitter", command=self.destroy)
        bar.add_cascade(label="Fichier", menu=f)

        a = tk.Menu(bar, tearoff=0)
        a.add_command(label="Analyser", accelerator="F5", command=self.start_scan)
        a.add_separator()
        a.add_command(label="Comparer à un instantané…", command=self.compare_snapshot)
        a.add_command(label="Comparer à un autre dossier ou disque…", command=self.compare_folder)
        a.add_command(label="Terminer la comparaison", command=self.clear_baseline)
        a.add_separator()
        a.add_checkbutton(label="Surveiller le dossier affiché (croissance en direct)",
                          variable=self.live_var, command=self._live_toggle)
        for secs in (5, 10, 30, 60):
            a.add_radiobutton(label="    toutes les %d s" % secs, variable=self.live_secs, value=secs)
        bar.add_cascade(label="Analyse", menu=a)

        t = tk.Menu(bar, tearoff=0)
        t.add_command(label="Doublons…", command=self.show_duplicates)
        t.add_command(label="Que supprimer ? (gains rapides, suppression sur confirmation)…",
                      command=self.show_cleanup)
        t.add_command(label="Projets de code…", command=self.show_projects)
        bar.add_cascade(label="Outils", menu=t)

        h = tk.Menu(bar, tearoff=0)
        h.add_command(label="À propos de DiskMap", command=lambda: messagebox.showinfo(
            "DiskMap", "DiskMap %s\nAnalyseur d'espace disque avec treemap.\n"
                       "Ne supprime jamais rien sans ta confirmation explicite : la suppression n'existe que "
                       "dans « Outils › Que supprimer ? »." % __version__))
        bar.add_cascade(label="Aide", menu=h)
        self.configure(menu=bar)

    # -- scan --
    def browse(self) -> None:
        folder = filedialog.askdirectory(title="Choisir un dossier à analyser")
        if folder:
            self.toolbar.path_var.set(os.path.normpath(folder))
            self.start_scan()

    def _scanning(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _scanning_visible(self) -> bool:
        return self._scanning() and self._purpose != "live"

    def start_scan(self, path: Optional[str] = None, purpose: str = "main") -> None:
        if self._scanning():
            return
        path = os.path.abspath(os.path.expanduser(path or self.toolbar.path_var.get().strip()))
        if not os.path.isdir(path):
            messagebox.showerror("DiskMap", "Dossier inaccessible :\n%s" % path)
            return
        self._launch(path, purpose, None)

    def _launch(self, path: str, purpose: str, target: Optional[Node]) -> None:
        self._scanner = Scanner(cross_devices=self.toolbar.cross_var.get())
        self._purpose = purpose
        if purpose != "live":
            self.toolbar.set_busy(True)
            self.progress.pack(fill="x", side="bottom", before=self.status)
        auto = bool(self.auto_snap.get())
        self._thread = threading.Thread(target=self._run_scan, daemon=True,
                                        args=(self._scanner, path, purpose, target, auto))
        self._thread.start()

    def _run_scan(self, scanner: Scanner, path: str, purpose: str, target: Optional[Node],
                  auto: bool) -> None:
        try:
            result = scanner.scan(path)
            payload: tuple = (result, target)
            if purpose == "main":     # instantané précédent (base de comparaison) puis nouveau
                prev = None
                try:
                    snaps = list_snapshots(result.path)
                    prev = (snaps[0], load_snapshot(snaps[0].file)) if snaps else None
                except (OSError, ValueError, KeyError):
                    prev = None
                if auto:
                    try:
                        save_snapshot(result)
                    except OSError:
                        pass
                payload = (result, prev)
            self._queue.put(("done", purpose, payload))
        except ScanCancelled:
            self._queue.put(("cancel", purpose, None))
        except Exception as exc:  # noqa: BLE001 - remonté à l'UI
            self._queue.put(("error", purpose, exc))

    def cancel_scan(self) -> None:
        if self._scanner:
            self._scanner.cancel()

    def _poll(self) -> None:
        try:
            kind, purpose, value = self._queue.get_nowait()
        except queue.Empty:
            kind = purpose = value = None
        if kind:
            if purpose != "live":
                self.progress.pack_forget()
                self.toolbar.set_busy(False)
            if kind == "done":
                {"main": self._show_result, "compare": self._compare_done,
                 "live": self._live_done}[purpose](*value)
            elif kind == "cancel":
                if purpose != "live":
                    self._set_status("Analyse annulée.")
            elif purpose != "live":
                messagebox.showerror("DiskMap", "Erreur pendant l'analyse :\n%s" % value)
        elif self._scanning_visible() and self._scanner:
            # Pas manuel plutôt que Progressbar.start() : l'animation automatique laisse un minuteur Tcl actif.
            self.progress.step(4)
            cur = self._scanner.current
            if len(cur) > 90:
                cur = cur[:40] + "…" + cur[-48:]
            self._set_status("Analyse… %s fichiers · %s" % (format(self._scanner.files, ","), cur))
        self.after(POLL_MS, self._poll)

    def _show_result(self, r: ScanResult, prev: Optional[Tuple[SnapshotInfo, ScanResult]]) -> None:
        self.result = r
        self._stacks = {"normal": [(r.root, r.path)], "change": []}
        self._selected = None
        self.view.set_highlight({})
        self.view.set_growth({})
        self.baseline = None
        if prev:
            self.baseline = ("l'instantané du " + prev[0].label, prev[1].root)
        self._rebuild_diff()
        if self.mode == "change" and self.diff_root is None:
            self.mode = "type"
            self.view.set_mode("type")
        self.modebar.set_mode(self.mode, self.baseline[0] if self.baseline else "")
        self._update_info()
        self.toolbar.set_skipped_count(len(r.skipped) + (1 if r.unreadable else 0))
        self._set_status(HELP + (" · « Changements » : ce qui a bougé depuis l'analyse précédente"
                                 if self.diff_root else ""))
        self._refresh()
        if self.live_var.get():
            self._live_toggle()

    def _update_info(self) -> None:
        r = self.result
        if not r:
            return
        parts = []
        if r.total:
            parts.append("Total %s · Utilisé %s · Libre %s" % (human_size(r.total), human_size(r.used),
                                                                human_size(r.free)))
        parts.append("%s fichiers · %.0f s" % (format(r.files, ","), r.seconds))
        if r.cloud_files:
            parts.append("☁ %s en ligne seulement (hors disque)" % human_size(r.cloud_bytes))
        if self.diff_root is not None and self.baseline:
            parts.append("Δ %s depuis %s" % (signed_size(self.diff_root.delta), self.baseline[0]))
        self.toolbar.set_info(" · ".join(parts))

    # -- comparaison (instantané, autre dossier) --
    def _rebuild_diff(self) -> None:
        if self.result and self.baseline:
            self.diff_root = diff_trees(self.baseline[1], self.result.root)
            self._stacks["change"] = [(self.diff_root, self.result.path)]
        else:
            self.diff_root = None
            self._stacks["change"] = []

    def _set_baseline(self, label: str, root: Node, switch: bool = True) -> None:
        self.baseline = (label, root)
        self._rebuild_diff()
        self._update_info()
        if switch:
            self._set_mode("change")
        else:
            self.modebar.set_mode(self.mode, label)

    def clear_baseline(self) -> None:
        self.baseline = None
        self._rebuild_diff()
        self._update_info()
        self._set_mode("type" if self.mode == "change" else self.mode)

    def compare_snapshot(self) -> None:
        if not self._need_result():
            return
        snaps = list_snapshots(self.result.path)
        if not snaps:
            messagebox.showinfo("DiskMap", "Aucun instantané pour %s.\nIl en est enregistré un après chaque "
                                           "analyse (menu Fichier › Instantané automatique)." % self.result.path)
            return

        def pick(info: SnapshotInfo) -> None:
            self.config(cursor="watch")
            self.update_idletasks()
            try:
                snap = load_snapshot(info.file)
            except (OSError, ValueError, KeyError) as exc:
                messagebox.showerror("DiskMap", "Instantané illisible :\n%s" % exc)
                return
            finally:
                self.config(cursor="")
            self._set_baseline("l'instantané du " + info.label, snap.root)

        SnapshotDialog(self, snaps, pick, self.result.root.size)

    def compare_folder(self) -> None:
        if not self._need_result():
            return
        folder = filedialog.askdirectory(title="Dossier ou disque à comparer à l'analyse actuelle")
        if folder:
            self.start_scan(folder, purpose="compare")

    def _compare_done(self, other: ScanResult, _unused: object) -> None:
        self._set_baseline(other.path, other.root)

    def _set_mode(self, mode: str) -> None:
        if mode == "change" and self.diff_root is None:
            messagebox.showinfo("DiskMap", "Aucune comparaison active.\nMenu Analyse › Comparer à un "
                                           "instantané… ou à un autre dossier…")
            mode = "type" if self.mode == "change" else self.mode
        self.mode = mode
        self._selected = None
        self.view.set_mode(mode)
        self.modebar.set_mode(mode, self.baseline[0] if self.baseline else "")
        if self.result:
            self._refresh()

    def _need_result(self) -> bool:
        if self.result is None:
            messagebox.showinfo("DiskMap", "Lance d'abord une analyse.")
        return self.result is not None

    # -- surveillance en direct --
    def _live_toggle(self) -> None:
        if self._live_job:
            self.after_cancel(self._live_job)
            self._live_job = None
        if self.live_var.get():
            self._live_job = self.after(self.live_secs.get() * 1000, self._live_tick)
        else:
            self.view.set_growth({})
            if self.result:
                self._set_status(HELP)

    def _live_tick(self) -> None:
        self._live_job = None
        if not self.live_var.get():
            return
        normal = self._stacks["normal"]
        if self.result and normal and not self._scanning() and self.mode != "change":
            node, path = normal[-1]
            if os.path.isdir(path):
                self._launch(path, "live", node)
                return
        self._live_job = self.after(self.live_secs.get() * 1000, self._live_tick)

    def _live_done(self, fresh: ScanResult, node: Node) -> None:
        """Remplace le sous-arbre surveillé par sa nouvelle analyse et signale ce qui a grossi."""
        chain = find_chain(self.result.root, self.result.path, fresh.path) if self.result else None
        if chain and chain[-1][0] is node:
            change = diff_trees(node, fresh.root)
            delta = fresh.root.size - node.size
            for anc, _p in chain[:-1]:
                anc.size += delta
            node.children, node.size = fresh.root.children, fresh.root.size
            node.mtime, node.project = fresh.root.mtime, fresh.root.project
            growth = growth_map(change, fresh.path)
            self.view.set_growth(growth)
            self._rebuild_diff()
            self._update_info()
            self._refresh()
            top = max(growth.items(), key=lambda kv: kv[1], default=None)
            if delta or top:
                self._set_status("👁 Surveillance : %s en %d s%s" % (
                    signed_size(delta), self.live_secs.get(),
                    "  ·  plus forte hausse : %s (%s)" % (top[0], signed_size(top[1])) if top else ""))
            else:
                self._set_status("👁 Surveillance : aucun changement.")
        if self.live_var.get():
            self._live_job = self.after(self.live_secs.get() * 1000, self._live_tick)

    # -- navigation --
    def _refresh(self) -> None:
        if not self.stack:
            return
        self.view.show(self.stack, self._selected)
        self.navbar.show(self.stack)
        node, path = self.stack[-1]
        self.entries.show(node, path, change=self.mode == "change")

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

    def goto_path(self, path: str) -> None:
        """Montre ``path`` sur la carte normale (utilisé par les fenêtres d'outils)."""
        if not self.result:
            return
        chain = find_chain(self.result.root, self.result.path, path)
        if not chain:
            self._set_status("Introuvable dans la carte actuelle : " + path)
            return
        if self.mode == "change":
            self._set_mode("type")
        selected = None
        if not chain[-1][0].is_dir and len(chain) > 1:
            chain, selected = chain[:-1], path
        self._stacks["normal"] = chain
        self._selected = selected
        self._refresh()
        self.focus_set()

    # -- outils --
    def show_duplicates(self) -> None:
        if not self._need_result():
            return
        path = self._stacks["normal"][-1][1]
        DuplicatesDialog(self, path, self.view.set_highlight)

    def show_cleanup(self) -> None:
        if not self._need_result():
            return
        r = self.result
        CleanupDialog(self, find_cleanup(r.root, r.path),
                      lambda days, size: find_cold(r.root, r.path, days, size), self.goto_path,
                      scan_root=r.path, on_removed=lambda: self.start_scan(r.path), is_admin=self.admin)

    def show_projects(self) -> None:
        if not self._need_result():
            return
        r = self.result
        ProjectsDialog(self, find_projects(r.root, r.path), self.goto_path)

    def save_snapshot_now(self) -> None:
        if not self._need_result():
            return
        try:
            file = save_snapshot(self.result)
        except OSError as exc:
            messagebox.showerror("DiskMap", str(exc))
            return
        self._set_status("Instantané enregistré : " + file)

    def export_report(self) -> None:
        if not self._need_result():
            return
        node, path = self._stacks["normal"][-1]
        default = "diskmap-%s.html" % time.strftime("%Y%m%d-%H%M")
        file = filedialog.asksaveasfilename(title="Exporter un rapport HTML", defaultextension=".html",
                                            initialfile=default, filetypes=[("Page HTML", "*.html")])
        if not file:
            return
        r = self.result
        page = export_html(node, path, find_cleanup(r.root, r.path), r.used, r.total)
        try:
            with open(file, "w", encoding="utf-8") as f:
                f.write(page)
        except OSError as exc:
            messagebox.showerror("DiskMap", str(exc))
            return
        self._set_status("Rapport exporté : " + file)
        webbrowser.open("file://" + os.path.abspath(file).replace("\\", "/"))

    # -- événements des widgets --
    def _select_hit(self, hit: Hit) -> None:
        self._selected = hit.path
        self.view.select(hit.path)

    def _hover(self, hit: Optional[Hit]) -> None:
        if self._scanning_visible():
            return
        if hit is None or not self.stack:
            self._set_status(HELP if self.stack else "")
            return
        total = self.stack[-1][0].size or 1
        if self.mode == "change":
            text = "%s   —   %s" % (hit.path, signed_size(hit.node.delta))
            if hit.node.note:
                text += "\nℹ " + hit.node.note
            self._set_status(text)
            return
        text = "%s   —   %s  (%.2f %% du dossier affiché)" % (
            hit.path, human_size(hit.node.size), hit.node.size / total * 100)
        if self.mode == "age" and hit.node.mtime > 0:
            text += "  ·  dernière modification : " + time.strftime("%d/%m/%Y", time.localtime(hit.node.mtime))
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
        shown = signed_size(node.delta) if self.mode == "change" else human_size(node.size)
        if node.grouped:
            self._set_status("%s   —   %s\nℹ %s" % (node.name, shown, node.note))
            return
        path = self.entries.path_of(node)
        self._selected = path
        self.view.select(path)
        self._set_status("%s   —   %s" % (path, shown) + ("\nℹ " + node.note if node.note else ""))

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
