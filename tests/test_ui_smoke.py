"""Fumée de l'interface : ne tourne que si tkinter et un affichage sont disponibles (xvfb en CI)."""
import os

import pytest

tk = pytest.importorskip("tkinter")

from diskmap.core import Node, Scanner, diff_trees  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DISKMAP_HOME", str(tmp_path / "home"))
    try:
        from diskmap.ui.app import App
        a = App()
    except tk.TclError:
        pytest.skip("pas d'affichage")
    a.geometry("1000x700")
    yield a
    a.destroy()


def _tree(tmp_path):
    root = tmp_path / "data"
    (root / "proj" / "node_modules").mkdir(parents=True)
    (root / "proj" / "package.json").write_text("{}")
    (root / "proj" / "node_modules" / "x.js").write_bytes(b"x" * 400_000)
    (root / "a.bin").write_bytes(b"a" * 200_000)
    return root


def test_window_has_icon(app):
    assert len(app._icons) == 3 and app._icons[0].width() == 64


def test_modes_and_diff(app, tmp_path):
    root = _tree(tmp_path)
    res = Scanner().scan(str(root))
    app._show_result(res, None)
    app.update()
    for mode in ("age", "type"):
        app._set_mode(mode)
        app.update()
    assert app.view._hits
    (root / "new.bin").write_bytes(b"n" * 300_000)
    res2 = Scanner().scan(str(root))
    app.result = res2
    app._stacks["normal"] = [(res2.root, res2.path)]
    app._set_baseline("test", res.root)
    app.update()
    assert app.mode == "change" and app.diff_root.delta > 250_000
    assert app.view._hits and app.entries.tree.get_children()
    app.clear_baseline()
    assert app.mode == "type"


def test_live_updates_subtree(app, tmp_path):
    root = _tree(tmp_path)
    res = Scanner().scan(str(root))
    app._show_result(res, None)
    old = res.root.size
    (root / "grow.bin").write_bytes(b"g" * 500_000)
    fresh = Scanner().scan(str(root))
    app._live_done(fresh, res.root)
    app.update()
    assert app.result.root.size >= old + 400_000
    assert any(p.endswith("grow.bin") for p in app.view._growth)


def test_goto_path_and_dialogs(app, tmp_path):
    root = _tree(tmp_path)
    res = Scanner().scan(str(root))
    app._show_result(res, None)
    app.goto_path(str(root / "proj" / "node_modules"))
    assert app.stack[-1][1].endswith("node_modules")
    app.show_cleanup()
    app.show_projects()
    app.show_duplicates()
    app.update()
    app.view.set_highlight({str(root / "a.bin"): "#ff00ff"})
    app.update()
