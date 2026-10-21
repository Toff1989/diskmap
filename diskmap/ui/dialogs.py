"""Fenêtres des outils : instantanés, doublons, gains rapides / fichiers froids, projets."""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ..core import (ColdEntry, DupResult, DuplicateFinder, Finding, ProjectInfo, ScanCancelled,
                    SnapshotInfo, human_size)
from ..core.cleanup import SAFE, SAFETY_LABEL
from ..core.projects import summarize
from . import theme
from .system import reveal_in_file_manager


def _tree(parent: tk.Misc, columns: Sequence[Tuple[str, str, int, str]], first: Tuple[str, int]) -> ttk.Treeview:
    """Treeview + barre de défilement. ``columns`` : (id, titre, largeur, ancrage)."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], selectmode="browse")
    tree.heading("#0", text=first[0])
    tree.column("#0", width=first[1])
    for cid, title, width, anchor in columns:
        tree.heading(cid, text=title)
        tree.column(cid, width=width, anchor=anchor, stretch=False)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def _window(master: tk.Misc, title: str, size: str) -> tk.Toplevel:
    win = tk.Toplevel(master, bg=theme.BG2)
    win.title(title)
    win.geometry(size)
    win.transient(master)
    return win


def _reveal(path: str) -> None:
    try:
        reveal_in_file_manager(path)
    except OSError:
        pass


class SnapshotDialog(tk.Toplevel):
    """Choix d'un instantané à comparer à l'analyse courante."""

    def __init__(self, master: tk.Misc, snapshots: List[SnapshotInfo],
                 on_pick: Callable[[SnapshotInfo], None], current_size: int) -> None:
        super().__init__(master, bg=theme.BG2)
        self.title("Comparer à un instantané")
        self.geometry("720x380")
        self.transient(master)
        self._snaps, self._on_pick = snapshots, on_pick
        ttk.Label(self, padding=10, justify="left",
                  text="Choisis l'état passé à comparer à l'analyse actuelle (%s).\n"
                       "La carte « Changements » montrera ce qui a grossi ou rétréci depuis."
                  % human_size(current_size)).pack(fill="x")
        self.tree = _tree(self, [("size", "Taille", 90, "e"), ("files", "Fichiers", 90, "e"),
                                 ("delta", "Δ vs actuel", 100, "e")], ("Date", 180))
        for i, s in enumerate(snapshots):
            d = current_size - s.size
            self.tree.insert("", "end", iid=str(i), text=s.label,
                             values=(human_size(s.size), format(s.files, ","),
                                     ("+" if d > 0 else "-" if d < 0 else "") + human_size(abs(d))))
        if snapshots:
            self.tree.selection_set("0")
        self.tree.bind("<Double-1>", lambda e: self._pick())
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="Comparer", style="Accent.TButton", command=self._pick).pack(side="right")
        ttk.Button(bar, text="Fermer", command=self.destroy).pack(side="right", padx=6)

    def _pick(self) -> None:
        sel = self.tree.selection()
        if sel:
            self._on_pick(self._snaps[int(sel[0])])
            self.destroy()


class DuplicatesDialog(tk.Toplevel):
    SIZES = (("100 Ko", 100 << 10), ("1 Mo", 1 << 20), ("10 Mo", 10 << 20), ("100 Mo", 100 << 20))

    def __init__(self, master: tk.Misc, path: str, on_highlight: Callable[[Dict[str, str]], None]) -> None:
        super().__init__(master, bg=theme.BG2)
        self.title("Doublons — " + path)
        self.geometry("980x600")
        self.transient(master)
        self._path, self._on_highlight = path, on_highlight
        self._finder: Optional[DuplicateFinder] = None
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._result: Optional[DupResult] = None

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Taille minimale :").pack(side="left")
        self.size_var = tk.StringVar(value=self.SIZES[1][0])
        ttk.Combobox(top, textvariable=self.size_var, values=[s[0] for s in self.SIZES], width=8,
                     state="readonly").pack(side="left", padx=6)
        self.go = ttk.Button(top, text="Chercher", style="Accent.TButton", command=self._start)
        self.go.pack(side="left")
        self.stop = ttk.Button(top, text="Annuler", command=self._cancel, state="disabled")
        self.stop.pack(side="left", padx=6)
        self.status = ttk.Label(top, style="Dim.TLabel")
        self.status.pack(side="left", padx=10)

        self.tree = _tree(self, [("size", "Taille", 90, "e"), ("gain", "Récupérable", 100, "e")],
                          ("Groupe / fichier", 700))
        self.tree.bind("<Double-1>", self._open)
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")
        self.light = ttk.Button(bar, text="Surligner sur la carte", command=self._highlight, state="disabled")
        self.light.pack(side="left")
        ttk.Button(bar, text="Effacer le surlignage", command=lambda: on_highlight({})).pack(side="left", padx=6)
        ttk.Label(bar, text="Double-clic : ouvrir l'emplacement · DiskMap ne supprime rien.",
                  style="Dim.TLabel").pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(120, self._poll)
        self._start()

    def _start(self) -> None:
        if self._finder:
            return
        size = dict(self.SIZES)[self.size_var.get()]
        self._finder = DuplicateFinder(min_size=size)
        self.go.configure(state="disabled")
        self.stop.configure(state="normal")
        self.light.configure(state="disabled")
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._run, args=(self._finder,), daemon=True).start()

    def _run(self, finder: DuplicateFinder) -> None:
        try:
            self._queue.put(("done", finder.find(self._path)))
        except ScanCancelled:
            self._queue.put(("cancel", None))
        except OSError as exc:
            self._queue.put(("error", exc))

    def _cancel(self) -> None:
        if self._finder:
            self._finder.cancel()

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        try:
            kind, value = self._queue.get_nowait()
        except queue.Empty:
            if self._finder:
                cur = self._finder.current
                cur = cur if len(cur) < 70 else cur[:30] + "…" + cur[-38:]
                self.status.configure(text="%s… %s fichiers · %s" % (
                    self._finder.phase, format(self._finder.files, ","), cur))
            self.after(120, self._poll)
            return
        self._finder = None
        self.go.configure(state="normal")
        self.stop.configure(state="disabled")
        if kind == "done":
            self._fill(value)
        else:
            self.status.configure(text="Annulé." if kind == "cancel" else "Erreur : %s" % value)
        self.after(120, self._poll)

    def _fill(self, res: DupResult) -> None:
        self._result = res
        for i, g in enumerate(res.groups[:2000]):
            gid = self.tree.insert("", "end", iid="g%d" % i, text="%d copies × %s" % (len(g.paths), human_size(g.size)),
                                   values=(human_size(g.size), human_size(g.reclaimable)))
            for j, p in enumerate(g.paths):
                self.tree.insert(gid, "end", iid="g%d_%d" % (i, j), text=p, values=("", ""))
        self.status.configure(text="%d groupes · %s récupérables · %s fichiers · %.0f s" % (
            len(res.groups), human_size(res.reclaimable), format(res.scanned, ","), res.seconds))
        self.light.configure(state="normal" if res.groups else "disabled")

    def _highlight(self) -> None:
        if not self._result:
            return
        colors: Dict[str, str] = {}
        for i, g in enumerate(self._result.groups[:200]):    # les plus rentables
            for p in g.paths:
                colors[p] = theme.group_color(i)
        self._on_highlight(colors)

    def _open(self, _e: tk.Event) -> None:
        sel = self.tree.selection()
        if sel and "_" in sel[0]:
            _reveal(self.tree.item(sel[0], "text"))

    def _close(self) -> None:
        self._cancel()
        self.destroy()


class CleanupDialog(tk.Toplevel):
    """Gains rapides (catalogue) et fichiers froids. Aucune suppression : conseils seulement."""

    AGES = (("1 an", 365), ("2 ans", 730), ("5 ans", 1825))
    SIZES = (("1 Mo", 1 << 20), ("10 Mo", 10 << 20), ("100 Mo", 100 << 20))

    def __init__(self, master: tk.Misc, findings: List[Finding],
                 cold_fn: Callable[[int, int], List[ColdEntry]],
                 on_goto: Callable[[str], None]) -> None:
        super().__init__(master, bg=theme.BG2)
        self.title("Que supprimer ?")
        self.geometry("1020x640")
        self.transient(master)
        self._findings, self._cold_fn, self._on_goto = findings, cold_fn, on_goto
        self._cold: List[ColdEntry] = []

        safe = sum(f.size for f in findings if f.rule.safety == SAFE)
        total = sum(f.size for f in findings)
        ttk.Label(self, padding=10, justify="left", text=(
            "Récupérable sans risque : %s  ·  Total des candidats : %s.\n"
            "DiskMap ne supprime rien : il t'explique et te donne la commande ou le geste recommandé."
            % (human_size(safe), human_size(total)))).pack(fill="x")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10)

        tab1 = ttk.Frame(nb)
        nb.add(tab1, text="Gains rapides (%d)" % len(findings))
        self.tree = _tree(tab1, [("kind", "Nature", 220, "w"), ("size", "Taille", 80, "e"),
                                 ("risk", "Risque", 90, "w"), ("regen", "Régénérable", 90, "w")],
                          ("Dossier", 430))
        for i, f in enumerate(findings):
            self.tree.insert("", "end", iid=str(i), text=f.path,
                             values=(f.rule.label, human_size(f.size), SAFETY_LABEL[f.rule.safety],
                                     "oui" if f.rule.regenerable else "non"))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._detail())
        self.tree.bind("<Double-1>", lambda e: self._goto(self.tree, lambda i: findings[i].path))
        self.detail = tk.Label(tab1, bg=theme.BG3, fg=theme.FG, justify="left", anchor="nw", wraplength=940,
                               padx=10, pady=8, height=5, text="Sélectionne une ligne pour l'explication.")
        self.detail.pack(fill="x", pady=(6, 0))
        bar1 = ttk.Frame(tab1)
        bar1.pack(fill="x", pady=6)
        ttk.Button(bar1, text="Voir sur la carte", command=lambda: self._goto(self.tree, lambda i: findings[i].path)
                   ).pack(side="left")
        ttk.Button(bar1, text="Copier la commande", command=self._copy_cmd).pack(side="left", padx=6)
        ttk.Button(bar1, text="Ouvrir l'emplacement",
                   command=lambda: self._with(self.tree, lambda i: _reveal(findings[i].path))).pack(side="left")

        tab2 = ttk.Frame(nb)
        nb.add(tab2, text="Fichiers froids")
        top = ttk.Frame(tab2)
        top.pack(fill="x", pady=6)
        ttk.Label(top, text="Rien modifié depuis :").pack(side="left")
        self.age_var = tk.StringVar(value=self.AGES[1][0])
        ttk.Combobox(top, textvariable=self.age_var, values=[a[0] for a in self.AGES], width=6,
                     state="readonly").pack(side="left", padx=6)
        ttk.Label(top, text="Taille min :").pack(side="left")
        self.csize_var = tk.StringVar(value=self.SIZES[1][0])
        ttk.Combobox(top, textvariable=self.csize_var, values=[s[0] for s in self.SIZES], width=7,
                     state="readonly").pack(side="left", padx=6)
        self.cold_info = ttk.Label(top, style="Dim.TLabel")
        self.cold_info.pack(side="left", padx=10)
        self.ctree = _tree(tab2, [("size", "Taille", 80, "e"), ("age", "Dernière modif.", 130, "w")],
                           ("Fichier / dossier", 700))
        self.ctree.bind("<Double-1>", lambda e: self._goto(self.ctree, lambda i: self._cold[i].path))
        for var in (self.age_var, self.csize_var):
            var.trace_add("write", lambda *a: self._fill_cold())
        ttk.Label(self, text="Double-clic : montrer sur la carte. Seuls les éléments visibles dans la carte "
                             "(après regroupement des petits éléments) sont analysés.",
                  style="Dim.TLabel", padding=10).pack(anchor="w")
        self._fill_cold()

    # -- gains rapides --
    def _detail(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        f = self._findings[int(sel[0])]
        text = "%s — %s\n%s" % (f.rule.label, SAFETY_LABEL[f.rule.safety], f.rule.why)
        if f.rule.how:
            text += "\nCommande / geste conseillé :  " + f.rule.how
        self.detail.configure(text=text)

    def _copy_cmd(self) -> None:
        def go(i: int) -> None:
            how = self._findings[i].rule.how
            if how:
                self.clipboard_clear()
                self.clipboard_append(how)
        self._with(self.tree, go)

    # -- fichiers froids --
    def _fill_cold(self) -> None:
        days = dict(self.AGES)[self.age_var.get()]
        size = dict(self.SIZES)[self.csize_var.get()]
        self._cold = self._cold_fn(days, size)
        self.ctree.delete(*self.ctree.get_children())
        for i, c in enumerate(self._cold):
            self.ctree.insert("", "end", iid=str(i), text=("📁 " if c.node.is_dir else "") + c.path,
                              values=(human_size(c.node.size),
                                      time.strftime("%d/%m/%Y", time.localtime(c.node.mtime))
                                      + " (%.1f an%s)" % (c.age_days / 365, "s" if c.age_days >= 730 else "")))
        self.cold_info.configure(text="%d éléments · %s" % (len(self._cold),
                                                            human_size(sum(c.node.size for c in self._cold))))

    # -- utilitaires --
    @staticmethod
    def _with(tree: ttk.Treeview, fn: Callable[[int], None]) -> None:
        sel = tree.selection()
        if sel:
            fn(int(sel[0]))

    def _goto(self, tree: ttk.Treeview, path_of: Callable[[int], str]) -> None:
        self._with(tree, lambda i: self._on_goto(path_of(i)))


class ProjectsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, projects: List[ProjectInfo], on_goto: Callable[[str], None]) -> None:
        super().__init__(master, bg=theme.BG2)
        self.title("Projets de code")
        self.geometry("1020x560")
        self.transient(master)
        self._projects, self._on_goto = projects, on_goto
        total, deps, vcs, src = summarize(projects)
        pct = lambda a: "%.0f %%" % (a / total * 100 if total else 0)  # noqa: E731
        ttk.Label(self, padding=10, justify="left", text=(
            "%d projets pèsent %s : %s de dépendances et builds (%s), %s de dépôts Git (%s), %s de sources (%s)."
            % (len(projects), human_size(total), human_size(deps), pct(deps), human_size(vcs), pct(vcs),
               human_size(src), pct(src)) if projects else "Aucun projet détecté dans cette analyse.")
                  ).pack(fill="x")
        self.tree = _tree(self, [("kind", "Type", 70, "w"), ("total", "Total", 85, "e"),
                                 ("deps", "Dépendances", 95, "e"), ("pct", "% dép.", 60, "e"),
                                 ("vcs", "Git", 80, "e"), ("src", "Sources", 85, "e"),
                                 ("what", "Dossiers de dépendances", 170, "w")], ("Projet", 330))
        for i, p in enumerate(projects):
            self.tree.insert("", "end", iid=str(i), text=p.path,
                             values=(p.kind, human_size(p.total), human_size(p.deps),
                                     "%.0f %%" % (p.deps_ratio * 100), human_size(p.vcs), human_size(p.source),
                                     ", ".join(p.deps_names)))
        self.tree.bind("<Double-1>", self._goto)
        ttk.Label(self, text="Double-clic : montrer le projet sur la carte.", style="Dim.TLabel",
                  padding=10).pack(anchor="w")

    def _goto(self, _e: tk.Event) -> None:
        sel = self.tree.selection()
        if sel:
            self._on_goto(self._projects[int(sel[0])].path)
