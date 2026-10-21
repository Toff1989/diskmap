"""Point d'entrée : ``python -m diskmap [dossier]``."""
from __future__ import annotations

import argparse
import os
from typing import Optional, Sequence

from . import __version__
from .elevation import is_admin, relaunch_as_admin


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="diskmap", description="Analyseur d'espace disque (treemap)")
    parser.add_argument("path", nargs="?", help="disque ou dossier à analyser dès l'ouverture")
    parser.add_argument("--no-admin", action="store_true",
                        help="ne pas demander les droits administrateur (Windows)")
    parser.add_argument("--export-html", metavar="FICHIER",
                        help="sans fenêtre : analyse PATH et écrit un rapport HTML interactif")
    parser.add_argument("--snapshot", action="store_true",
                        help="sans fenêtre : analyse PATH et enregistre un instantané (comparable ensuite)")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    if args.export_html or args.snapshot:
        if not args.path:
            parser.error("PATH est requis avec --export-html / --snapshot")
        return _headless(args)

    if os.name == "nt" and not args.no_admin and not is_admin():
        forward = [os.path.abspath(args.path)] if args.path else []
        if relaunch_as_admin(forward):
            return  # la nouvelle instance (administrateur) prend le relais
        # UAC refusé ou échec : on continue sans droits élevés (zones protégées non lisibles)

    if os.name == "nt":
        try:  # rendu net sur écrans HiDPI + identité propre dans la barre des tâches (icône DiskMap)
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("diskmap.DiskMap")
        except (AttributeError, OSError):
            pass

    from .ui.app import App  # import tardif : --help / --version sans tkinter
    App(args.path, admin=is_admin()).mainloop()


def _headless(args: argparse.Namespace) -> None:
    from .core import Scanner, export_html, find_cleanup, save_snapshot

    result = Scanner().scan(args.path)
    print("%s : %d fichiers, %.1f s" % (result.path, result.files, result.seconds))
    if args.snapshot:
        print("Instantané :", save_snapshot(result))
    if args.export_html:
        page = export_html(result.root, result.path, find_cleanup(result.root, result.path),
                           result.used, result.total)
        with open(args.export_html, "w", encoding="utf-8") as f:
            f.write(page)
        print("Rapport :", args.export_html)


if __name__ == "__main__":
    main()
