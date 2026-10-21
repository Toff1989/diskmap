"""Sonde TEMPORAIRE : isole ce qui fait abattre Tk sous macOS. Variantes : base, noprogress, nothread,
notransient, plain (Toplevel vide). Usage : python mac_probe.py <variante> <itérations>"""
import faulthandler
import gc
import os
import sys
import tempfile
import time
import types

faulthandler.enable()
variant, n = sys.argv[1], int(sys.argv[2])
os.environ["DISKMAP_HOME"] = tempfile.mkdtemp()

import tkinter as tk
from tkinter import ttk

from diskmap.core import Scanner, find_cleanup, plan_removal
from diskmap.ui import removal_dialog
from diskmap.ui.app import App

print("Python", sys.version.split()[0], "Tk", tk.Tcl().eval("info patchlevel"), "variante", variant, flush=True)

if variant == "noprogress":
    ttk.Progressbar.start = lambda *a, **k: None
elif variant == "nothread":
    class Sync:
        def __init__(self, target=None, args=(), daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    removal_dialog.threading = types.SimpleNamespace(Thread=Sync)
elif variant == "notransient":
    tk.Toplevel.transient = lambda self, *a, **k: None


def make_tree():
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "proj", "node_modules", "pkg"))
    open(os.path.join(root, "proj", "package.json"), "w").write("{}")
    with open(os.path.join(root, "proj", "node_modules", "pkg", "i.js"), "wb") as f:
        f.write(b"x" * 400_000)
    return root


for i in range(n):
    root = make_tree()
    finding = next(f for f in find_cleanup(Scanner().scan(root).root, root, min_size=1)
                   if f.rule.id == "node_modules")
    plan = plan_removal(finding, root)
    app = App()
    app.geometry("1000x700")
    app.update()
    if variant == "apponly":
        app.update()
    elif variant == "plain":
        win = tk.Toplevel(app)
        win.transient(app)
        tk.Label(win, text="x").pack()
        app.update()
        win.destroy()
        app.update()
    else:
        dlg = removal_dialog.RemovalDialog(app, [plan], root, lambda changed: None)
        app.update()
        dlg.confirm_var.set(True)
        dlg._sync()
        dlg._start()
        gc.collect()
        gc.disable()
        end = time.time() + 20
        while not dlg._finished and time.time() < end:
            app.update()
            time.sleep(0.02)
        gc.enable()
        assert dlg._finished, "pas terminé"
        assert not os.path.exists(finding.path)
        dlg._close()
        app.update()
    app.destroy()
    gc.collect()
    print("iter", i, "ok", flush=True)
print("TERMINE sans plantage :", variant, flush=True)
