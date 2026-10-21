import os

import pytest

from diskmap.core import detect_drives, human_size
from diskmap.ui.theme import extension_color, hsl


@pytest.mark.parametrize("value, expected", [
    (0, "0 o"), (1023, "1023 o"), (1024, "1.0 Ko"), (1536, "1.5 Ko"),
    (5 * 1024 ** 2, "5.0 Mo"), (3 * 1024 ** 3, "3.0 Go"), (2 * 1024 ** 5, "2048.0 To"),
])
def test_human_size(value, expected):
    assert human_size(value) == expected


def test_detect_drives_returns_existing_paths():
    drives = detect_drives()
    assert drives and all(os.path.exists(d) for d in drives)


def test_shorten_middle_keeps_the_end_of_a_path():
    from diskmap.ui.text import shorten_middle
    path = "C:\\Users\\someone\\AppData\\Local\\Temp\\project\\webapp\\node_modules"
    short = shorten_middle(path, 40)
    assert len(short) == 40 and short.endswith("webapp\\node_modules") and short.startswith("C:\\Users")
    assert "…" in short
    assert shorten_middle("court", 40) == "court"


def test_hsl_known_values():
    assert hsl(0, 1, 0.5) == "#ff0000"
    assert hsl(120, 1, 0.5) == "#00ff00"
    assert hsl(0, 0, 0) == "#000000"


def test_extension_color_is_stable_and_case_insensitive():
    assert extension_color("a.MP4") == extension_color("b.mp4")
    assert extension_color("noext") == extension_color(".hidden")
