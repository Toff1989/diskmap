"""Un minuteur ne doit jamais survivre à la fenêtre qui l'a planifié."""
import pytest

tk = pytest.importorskip("tkinter")

from diskmap.ui.safe_after import SafeAfter, cancel_all_after  # noqa: E402


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip("pas d'affichage : %s" % exc)
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass


class Win(SafeAfter, tk.Toplevel):
    pass


def pending(widget):
    return list(widget.tk.splitlist(widget.tk.call("after", "info")))


def test_destroy_cancels_pending_timers(root):
    fired = []
    win = Win(root)
    win.after(50, lambda: fired.append("trop tard"))
    win.after(50, fired.append, "arg")
    assert len(pending(root)) == 2
    win.destroy()
    assert pending(root) == []                       # plus aucun minuteur orphelin
    root.after(120, root.quit)
    root.mainloop()
    assert fired == []


def test_a_fired_timer_is_forgotten(root):
    win = Win(root)
    fired = []
    win.after(10, lambda: fired.append(1))
    root.after(80, root.quit)
    root.mainloop()
    assert fired == [1] and win._jobs() == set()
    win.destroy()


def test_after_cancel_and_plain_sleep_still_work(root):
    win = Win(root)
    job = win.after(500, lambda: None)
    win.after_cancel(job)
    assert pending(root) == [] and win._jobs() == set()
    win.after(1)                                     # after(ms) seul : simple pause
    win.destroy()


def test_cancel_all_after_clears_the_whole_interpreter(root):
    root.after(500, lambda: None)
    root.after(500, lambda: None)
    child = tk.Frame(root)
    child.after(500, lambda: None)
    assert len(pending(root)) == 3
    cancel_all_after(root)
    assert pending(root) == []


def test_app_destroy_leaves_no_timer_behind(tmp_path, monkeypatch):
    monkeypatch.setenv("DISKMAP_HOME", str(tmp_path / "home"))
    from diskmap.ui.app import App
    try:
        app = App()
    except tk.TclError as exc:
        pytest.skip("pas d'affichage : %s" % exc)
    app.update()
    assert pending(app)                              # la boucle _poll est planifiée
    tcl = app.tk
    app.destroy()
    # L'interpréteur Tcl survit à destroy() : c'est pourquoi un minuteur oublié tirerait plus tard, pendant
    # l'update() d'une autre fenêtre. Il n'en doit plus rester aucun.
    assert tcl.splitlist(tcl.call("after", "info")) == ()
