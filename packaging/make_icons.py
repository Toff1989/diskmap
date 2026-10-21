"""Génère les icônes (PNG, ICO) dans packaging/assets/ (+ PNG/ICO copiés dans diskmap/assets/). Nécessite Pillow.

    python packaging/make_icons.py
"""
from __future__ import annotations

import os
import shutil

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
SIZE = 1024

# Rectangles d'une mini-treemap, en fractions du carré intérieur : (x0, y0, x1, y1, couleur)
TILES = [
    (0.00, 0.00, 0.58, 0.62, "#3b6fd4"),
    (0.58, 0.00, 1.00, 0.38, "#d4663b"),
    (0.58, 0.38, 1.00, 0.62, "#8a4fd4"),
    (0.00, 0.62, 0.34, 1.00, "#3bb58a"),
    (0.34, 0.62, 0.72, 1.00, "#d4b13b"),
    (0.72, 0.62, 1.00, 1.00, "#4a4f5c"),
]


def draw_icon(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill="#14161a")
    pad = size * 0.14
    inner = size - 2 * pad
    gap = size * 0.012
    for x0, y0, x1, y1, color in TILES:
        box = (pad + x0 * inner + gap, pad + y0 * inner + gap,
               pad + x1 * inner - gap, pad + y1 * inner - gap)
        d.rounded_rectangle(box, radius=size * 0.025, fill=color)
    return img


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    base = draw_icon()
    base.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon.png"))
    base.save(os.path.join(OUT, "icon.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    # Copie embarquée dans le paquet : icône de la fenêtre (barre de titre, barre des tâches, Alt-Tab).
    pkg = os.path.join(HERE, "..", "diskmap", "assets")
    os.makedirs(pkg, exist_ok=True)
    for name in ("icon.png", "icon.ico"):
        shutil.copyfile(os.path.join(OUT, name), os.path.join(pkg, name))
    print("Icônes écrites dans", OUT)


if __name__ == "__main__":
    main()
