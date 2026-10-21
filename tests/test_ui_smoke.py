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
    except tk.TclError as exc:
        pytest.skip("pas d'affichage : %s" % exc)
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


def _node_modules_plan(tmp_path):
    from diskmap.core import find_cleanup, plan_removal
    root = _tree(tmp_path)
    res = Scanner().scan(str(root))
    finding = next(f for f in find_cleanup(res.root, str(root), min_size=1) if f.rule.id == "node_modules")
    return root, res, finding, plan_removal(finding, str(root))


def _wait(app, dialog, seconds=15):
    import time
    end = time.time() + seconds
    while not dialog._finished and time.time() < end:
        app.update()
        time.sleep(0.02)
    assert dialog._finished, "la suppression ne s'est pas terminée"


def test_removal_needs_explicit_confirmation_before_anything_is_deleted(app, tmp_path):
    from diskmap.ui.removal_dialog import RemovalDialog
    root, _res, finding, plan = _node_modules_plan(tmp_path)
    done = []
    dlg = RemovalDialog(app, [plan], str(root), done.append)
    app.update()
    assert str(dlg.go_btn.cget("state")) == "disabled"        # case non cochée : bouton rouge inactif
    dlg._start()                                              # même appelé de force, rien ne doit partir
    app.update()
    assert dlg._thread is None and os.path.isdir(finding.path)
    dlg.confirm_var.set(True)
    dlg._sync()
    assert str(dlg.go_btn.cget("state")) == "normal"
    dlg._start()
    _wait(app, dlg)
    assert not os.path.exists(finding.path) and (root / "a.bin").exists()
    dlg._close()
    assert done == [True]


def test_closing_the_confirmation_without_confirming_deletes_nothing(app, tmp_path):
    from diskmap.ui.removal_dialog import RemovalDialog
    root, _res, finding, plan = _node_modules_plan(tmp_path)
    done = []
    dlg = RemovalDialog(app, [plan], str(root), done.append)
    app.update()
    dlg._cancel_clicked()
    app.update()
    assert os.path.isdir(finding.path) and done == []


def test_blocked_items_are_listed_but_never_executed(app, tmp_path):
    import dataclasses
    from diskmap.ui.removal_dialog import RemovalDialog
    root, _res, finding, plan = _node_modules_plan(tmp_path)
    blocked = dataclasses.replace(plan, blocked="refusé pour le test")
    dlg = RemovalDialog(app, [blocked], str(root), lambda changed: None)
    app.update()
    dlg.confirm_var.set(True)
    dlg._sync()
    assert str(dlg.go_btn.cget("state")) == "disabled"        # rien d'exécutable : jamais de bouton actif
    assert os.path.isdir(finding.path)


def test_cleanup_dialog_only_offers_runnable_items_and_opens_confirmation(app, tmp_path, monkeypatch):
    from diskmap.ui import dialogs
    root, res, finding, _plan = _node_modules_plan(tmp_path)
    opened, infos = [], []
    monkeypatch.setattr(dialogs, "RemovalDialog", lambda *a, **k: opened.append(a))
    monkeypatch.setattr(dialogs.messagebox, "showinfo", lambda *a, **k: infos.append(a))
    from diskmap.core import find_cleanup
    dlg = dialogs.CleanupDialog(app, find_cleanup(res.root, str(root), min_size=1), lambda d, s: [],
                                lambda p: None, scan_root=str(root), on_removed=lambda: None)
    app.update()
    dlg._remove()                                             # rien de sélectionné
    assert infos and not opened
    dlg._select_safe()
    assert dlg.tree.selection()
    dlg._remove()
    assert len(opened) == 1 and opened[0][1][0].finding.path == finding.path   # la confirmation s'ouvre ; rien n'est effacé
    assert os.path.isdir(finding.path)


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
