"""Palette et styles ttk (thème sombre)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG, BG2, BG3 = "#14161a", "#1c1f26", "#2a2e38"
FG, FG_DIM = "#e6e6e6", "#8a8f98"
ACCENT, ACCENT_HOVER = "#3b6fd4", "#4f84ea"
LINK = "#7fb0ff"
SELECTION = "#ffd24a"
GROUPED = "#3a3a3a"
UNREADABLE = "#6b3d3d"
FONT = ("Segoe UI", 9)


def hsl(h: float, s: float, l: float) -> str:
    """HSL (h en degrés, s et l dans [0, 1]) -> '#rrggbb'."""
    c = (1 - abs(2 * l - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs(hp % 2 - 1))
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(hp) % 6]
    m = l - c / 2
    return "#%02x%02x%02x" % (round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))


def extension_color(name: str) -> str:
    """Couleur stable déduite de l'extension du fichier."""
    i = name.rfind(".")
    ext = name[i + 1:].lower() if i > 0 else ""
    h = 0
    for ch in ext:
        h = (h * 31 + ord(ch)) % 360
    return hsl(h, 0.45, 0.38)


def folder_color(depth: int) -> str:
    return hsl(220, 0.12, min(0.2 + depth * 0.06, 0.6))


# Ancienneté : du plus récent (chaud) au plus ancien (froid) — une couleur par tranche de core.age.
AGE_HUES = (18, 40, 60, 150, 200, 225)
GROW, SHRINK = "#c0392b", "#2e8b57"
GROWTH_OUTLINE = "#ff9f1c"


def age_color(bucket: int, dim: bool = False) -> str:
    if bucket < 0:
        return GROUPED
    lightness = (0.42 if bucket < 2 else 0.36) * (0.55 if dim else 1.0)
    return hsl(AGE_HUES[bucket], 0.55, lightness)


def delta_color(delta: int, scale: float) -> str:
    """Rouge = a grossi, vert = a rétréci ; plus c'est lumineux, plus le changement est gros."""
    ratio = min(abs(delta) / scale, 1.0) ** 0.5 if scale > 0 else 0.0
    return hsl(4 if delta > 0 else 150, 0.55, 0.22 + 0.22 * ratio)


def group_color(i: int) -> str:
    """Couleur vive propre à un groupe de doublons."""
    return hsl((i * 137) % 360, 0.9, 0.62)


def apply(root: tk.Misc) -> None:
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG2, foreground=FG, fieldbackground=BG3, bordercolor=BG3)
    s.configure("TFrame", background=BG2)
    s.configure("TLabel", background=BG2, foreground=FG)
    s.configure("Dim.TLabel", foreground=FG_DIM)
    s.configure("TCheckbutton", background=BG2, foreground=FG)
    s.configure("TRadiobutton", background=BG2, foreground=FG)
    s.map("TRadiobutton", background=[("active", BG3)])
    s.configure("TNotebook", background=BG2, borderwidth=0)
    s.configure("TNotebook.Tab", background=BG3, foreground=FG, padding=(12, 4))
    s.map("TNotebook.Tab", background=[("selected", ACCENT)])
    s.configure("TEntry", fieldbackground=BG3, foreground=FG)
    s.configure("TButton", background=BG3, foreground=FG, padding=(10, 4), borderwidth=0)
    s.map("TButton", background=[("active", ACCENT), ("disabled", BG2)],
          foreground=[("disabled", FG_DIM)])
    s.configure("Accent.TButton", background=ACCENT)
    s.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", BG2)])
    s.configure("Crumb.TButton", padding=(6, 2), background=BG, foreground=LINK)
    s.map("Crumb.TButton", background=[("active", BG3)])
    s.configure("TCombobox", fieldbackground=BG3, background=BG3, foreground=FG,
                arrowcolor=FG, selectbackground=BG3, selectforeground=FG)
    s.map("TCombobox", fieldbackground=[("readonly", BG3)])
    s.configure("Treeview", background=BG2, fieldbackground=BG2, foreground=FG,
                rowheight=24, borderwidth=0)
    s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#fff")])
    s.configure("Treeview.Heading", background=BG3, foreground=FG, borderwidth=0)
    s.map("Treeview.Heading", background=[("active", BG3)])
    s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=BG3, borderwidth=0)
    root.option_add("*TCombobox*Listbox.background", BG3)
    root.option_add("*TCombobox*Listbox.foreground", FG)
