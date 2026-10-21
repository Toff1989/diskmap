"""Annulation des callbacks ``after()`` en attente quand une fenêtre est détruite.

Sans cela, un minuteur planifié par une fenêtre déjà détruite tire plus tard avec une commande Tcl supprimée
(« invalid command name … ("after" script) »). Sous macOS cette erreur de fond fait planter Tk, souvent pendant
l'``update()`` d'une AUTRE fenêtre, car la file des minuteurs est partagée par le thread.
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional, Set


class SafeAfter:
    """À placer AVANT la classe Tk : ``class MaFenetre(SafeAfter, tk.Toplevel)``."""

    def _jobs(self) -> Set[str]:
        return self.__dict__.setdefault("_safe_after_jobs", set())

    def after(self, ms: Any, func: Optional[Callable[..., Any]] = None, *args: Any) -> str:  # type: ignore[override]
        if func is None:                                   # after(ms) : simple pause, rien à suivre
            return super().after(ms)                       # type: ignore[misc]
        holder: list = []

        def run() -> None:
            self._jobs().discard(holder[0])
            func(*args)

        job = super().after(ms, run)                       # type: ignore[misc]
        holder.append(job)
        self._jobs().add(job)
        return job

    def after_cancel(self, job: str) -> None:              # type: ignore[override]
        self._jobs().discard(job)
        super().after_cancel(job)                          # type: ignore[misc]

    def destroy(self) -> None:
        for job in list(self._jobs()):
            try:
                super().after_cancel(job)                  # type: ignore[misc]
            except tk.TclError:
                pass
        self._jobs().clear()
        super().destroy()                                  # type: ignore[misc]


def cancel_all_after(widget: tk.Misc) -> None:
    """Annule TOUS les ``after`` en attente de l'interpréteur de ``widget`` (à la fermeture de l'appli)."""
    try:
        for job in widget.tk.splitlist(widget.tk.call("after", "info")):
            try:
                widget.tk.call("after", "cancel", job)
            except tk.TclError:
                pass
    except tk.TclError:
        pass
