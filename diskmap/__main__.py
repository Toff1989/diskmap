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
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    if os.name == "nt" and not args.no_admin and not is_admin():
        forward = [os.path.abspath(args.path)] if args.path else []
        if relaunch_as_admin(forward):
            return  # la nouvelle instance (administrateur) prend le relais
        # UAC refusé ou échec : on continue sans droits élevés (zones protégées non lisibles)

    if os.name == "nt":
        try:  # rendu net sur écrans HiDPI
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

    from .ui.app import App  # import tardif : --help / --version sans tkinter
    App(args.path, admin=is_admin()).mainloop()


if __name__ == "__main__":
    main()
