"""Fenêtre de confirmation puis d'exécution d'une suppression (ouverte uniquement depuis « Que supprimer ? »)."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from ..core import Outcome, Plan, Remover, human_size
from . import theme
from .safe_after import SafeAfter
from .text import shorten_middle

POLL_MS = 150


def action_label(plan: Plan) -> str:
    """« Supprimer », « Vider », « Commande » ou « Manuel »."""
    if plan.kind == "delete":
        return "Vider" if any(keep for _path, keep in plan.targets) else "Supprimer"
    return "Commande" if plan.kind == "command" else "Manuel"


def _work(remover: Remover, results: "queue.Queue[tuple]") -> None:
    try:
        results.put(("done", remover.run()))
    except Exception as exc:  # noqa: BLE001 - remonté à l'interface
        results.put(("error", exc))


class RemovalDialog(SafeAfter, tk.Toplevel):
    """Rien n'est exécuté tant que la case de confirmation n'est pas cochée ET le bouton rouge cliqué."""

    def __init__(self, master: tk.Misc, plans: List[Plan], scan_root: str,
                 on_finished: Callable[[bool], None],
                 on_closed: Optional[Callable[[], None]] = None) -> None:
        super().__init__(master, bg=theme.BG2)
        self.title("Confirmer la suppression")
        self.geometry("940x620")
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._close_request)
        self._plans = sorted(plans, key=lambda p: (not p.runnable, -p.finding.size))
        self._todo = [p for p in self._plans if p.runnable]
        self._root, self._on_finished, self._on_closed = scan_root, on_finished, on_closed
        self._remover: Optional[Remover] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._outcomes: List[Outcome] = []
        self._finished = False

        self.banner = tk.Label(
            self, bg=theme.DANGER, fg="#fff", justify="left", anchor="w", padx=14, pady=10, wraplength=900,
            text="⚠  Suppression DÉFINITIVE : les éléments ne passent PAS par la corbeille et ne pourront pas "
                 "être restaurés. Vérifie bien la liste ci-dessous.")
        self.banner.pack(fill="x")

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.tree = ttk.Treeview(frame, columns=("action", "size", "detail"), selectmode="browse")
        for col, title, width, anchor in (("#0", "Cible", 400, "w"), ("action", "Action", 85, "w"),
                                          ("size", "Taille", 80, "e"), ("detail", "Détail", 330, "w")):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor=anchor, stretch=col in ("#0", "detail"))
        self.tree.tag_configure("blocked", foreground=theme.FG_DIM)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for i, p in enumerate(self._plans):
            detail = p.detail
            self.tree.insert("", "end", iid=str(i), text=shorten_middle(p.finding.path, 56),
                             tags=("" if p.runnable else "blocked",),
                             values=(action_label(p) if p.runnable else "Ignoré",
                                     human_size(p.finding.size), detail))
        self.tree.bind("<<TreeviewSelect>>", self._show_full_path)
        self.full_path = ttk.Label(self, style="Dim.TLabel", padding=(10, 6, 10, 0), wraplength=900, justify="left",
                                   text="Sélectionne une ligne pour voir son chemin complet.")
        self.full_path.pack(fill="x")

        total = sum(p.finding.size for p in self._todo)
        ignored = len(self._plans) - len(self._todo)
        self.summary = ttk.Label(self, padding=(10, 8, 10, 0), justify="left", text=(
            "%d élément(s) seront traités · espace libéré estimé : %s%s"
            % (len(self._todo), human_size(total),
               " · %d ignoré(s) (grisés, voir « Détail »)" % ignored if ignored else "")))
        self.summary.pack(fill="x")

        self.confirm_var = tk.BooleanVar(value=False)
        self.check = ttk.Checkbutton(
            self, variable=self.confirm_var, command=self._sync, padding=(10, 8, 10, 4),
            text="Je comprends que cette suppression est définitive (sans corbeille) et je la confirme.")
        self.check.pack(anchor="w")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.status = ttk.Label(self, style="Dim.TLabel", padding=(10, 0, 10, 0))
        self.errors = tk.Text(self, height=6, bg=theme.BG3, fg=theme.FG, relief="flat", wrap="word",
                              state="disabled")

        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.cancel_btn = ttk.Button(bar, text="Annuler", command=self._cancel_clicked)
        self.cancel_btn.pack(side="right")
        self.go_btn = ttk.Button(bar, text="Supprimer définitivement", style="Danger.TButton",
                                 command=self._start, state="disabled")
        self.go_btn.pack(side="right", padx=8)
        self.bar = bar
        self.cancel_btn.focus_set()               # le bouton par défaut est le plus sûr
        self.bind("<Escape>", lambda e: self._cancel_clicked())
        self._grab_job: Optional[str] = self.after(60, self._grab)
        self._poll_job: Optional[str] = None

    def _show_full_path(self, _event: Optional[tk.Event] = None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        items = [o.plan for o in self._outcomes] if self._finished else self._plans
        index = int(sel[0])
        if index < len(items):
            plan = items[index]
            text = "Chemin complet : " + plan.finding.path
            if plan.runnable and plan.kind == "command":        # la ligne EXACTE qui sera lancée
                text += "\nCommande lancée : " + plan.command_line
            self.full_path.configure(text=text)

    def _grab(self) -> None:
        self._grab_job = None
        if not self.winfo_exists():
            return
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _sync(self) -> None:
        ok = self.confirm_var.get() and bool(self._todo) and self._thread is None
        self.go_btn.configure(state="normal" if ok else "disabled")

    # -- exécution --
    def _start(self) -> None:
        if not (self.confirm_var.get() and self._todo) or self._thread is not None:
            return
        self._remover = Remover(self._todo, self._root)
        # Le thread ne doit pas référencer la fenêtre (sinon Tk serait libéré depuis le thread de travail).
        self._thread = threading.Thread(target=_work, args=(self._remover, self._queue), daemon=True)
        self.go_btn.configure(state="disabled")
        self.check.configure(state="disabled")
        self.cancel_btn.configure(text="Interrompre")
        self.progress.pack(fill="x", padx=10, before=self.bar)
        self.status.pack(fill="x", before=self.bar)
        self._thread.start()
        self._poll_job = self.after(POLL_MS, self._poll)

    def _poll(self) -> None:
        try:
            kind, value = self._queue.get_nowait()
        except queue.Empty:
            # Pas manuel plutôt que Progressbar.start() : l'animation automatique laisse un minuteur Tcl actif.
            self.progress.step(4)
            if self._remover:
                cur = self._remover.current
                cur = cur if len(cur) <= 90 else cur[:40] + "…" + cur[-48:]
                self.status.configure(text="%s libérés · %s" % (human_size(self._remover.freed), cur))
            self._poll_job = self.after(POLL_MS, self._poll)
            return
        self._poll_job = None
        self.progress.pack_forget()
        if kind == "error":
            self.status.configure(text="Erreur inattendue : %s" % value)
            self._outcomes = []
        else:
            self._outcomes = value
        self._show_results()

    def _show_results(self) -> None:
        self._finished = True
        self.tree.delete(*self.tree.get_children())
        self.tree.heading("action", text="Résultat")
        self.tree.heading("size", text="Libéré")
        lines: List[str] = []
        for i, o in enumerate(self._outcomes):
            label = "✔ Fait" if o.ok else ("⚠ Partiel" if o.freed or o.skipped else "✖ Échec")
            self.tree.insert("", "end", iid=str(i), text=shorten_middle(o.plan.finding.path, 56),
                             values=(label, human_size(o.freed), o.message.splitlines()[0] if o.message else ""))
            lines += o.errors[:10]
        freed = sum(o.freed for o in self._outcomes)
        bad = sum(1 for o in self._outcomes if not o.ok)
        left = len(self._todo) - len(self._outcomes)
        self.banner.configure(bg=theme.ACCENT if not bad else "#8a5a00", text=(
            "Terminé : %s libérés · %d réussi(s)%s%s" % (
                human_size(freed), len(self._outcomes) - bad,
                " · %d avec erreur(s) ou partiel(s)" % bad if bad else "",
                " · %d non traité(s) (interrompu)" % left if left > 0 else "")))
        self.summary.configure(text="Les détails sont consignés dans removals.log. "
                                    "Ferme cette fenêtre pour réanalyser et voir le résultat sur la carte.")
        self.check.pack_forget()
        if lines:
            self.errors.pack(fill="x", padx=10, pady=(6, 0), before=self.bar)
            self.errors.configure(state="normal")
            self.errors.insert("1.0", "\n".join(lines[:40]))
            self.errors.configure(state="disabled")
        self.go_btn.pack_forget()
        self.cancel_btn.configure(text="Fermer", state="normal")

    # -- fermeture --
    def _cancel_clicked(self) -> None:
        if self._finished:
            self._close()
        elif self._thread is not None:
            if self._remover:
                self._remover.cancel()
            self.cancel_btn.configure(state="disabled", text="Interruption…")
        else:
            self._destroy_safely()

    def _close_request(self) -> None:
        self._cancel_clicked()

    def _close(self) -> None:
        changed = any(o.freed or o.ok for o in self._outcomes)
        self._destroy_safely()
        self._on_finished(changed)

    def _destroy_safely(self) -> None:
        """Libère la prise de focus modale et annule les callbacks différées AVANT de détruire la fenêtre :
        détruire une fenêtre qui détient un grab (ou laisser un « after » partir ensuite) peut faire
        faire planter Tk."""
        for job in (self._grab_job, self._poll_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._grab_job = self._poll_job = None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        if self._on_closed:
            self._on_closed()
