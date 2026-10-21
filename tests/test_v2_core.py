import os
import time

from diskmap.core import (DuplicateFinder, Node, Scanner, diff_trees, export_html, find_chain,
                          find_cleanup, find_cold, find_projects, growth_map, list_snapshots,
                          load_snapshot, save_snapshot, signed_size)
from diskmap.core.age import age_bucket
from diskmap.core.cleanup import SAFE, classify

MB = 1 << 20


def make_tree(tmp_path):
    proj = tmp_path / "proj"
    (proj / "node_modules" / "lib").mkdir(parents=True)
    (proj / "src").mkdir()
    (proj / "package.json").write_text("{}")
    (proj / "node_modules" / "lib" / "big.js").write_bytes(b"x" * 300_000)
    (proj / "src" / "main.js").write_bytes(b"y" * 50_000)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.bin").write_bytes(b"z" * 100_000)
    return tmp_path


# -- scanner enrichi --
def test_scan_records_mtime_and_project(tmp_path):
    root = Scanner().scan(str(make_tree(tmp_path))).root
    proj = next(c for c in root.children if c.name == "proj")
    assert proj.project == "Node"
    assert proj.mtime > 0 and root.mtime >= proj.mtime


# -- projets --
def test_find_projects_splits_deps(tmp_path):
    res = Scanner().scan(str(make_tree(tmp_path)))
    (p,) = find_projects(res.root, res.path)
    assert p.kind == "Node" and p.path.endswith("proj")
    assert p.deps >= 300_000 and p.deps_names == ["node_modules"]
    assert p.source + p.deps + p.vcs == p.total


# -- nettoyage --
def test_cleanup_finds_node_modules(tmp_path):
    res = Scanner().scan(str(make_tree(tmp_path)))
    (f,) = find_cleanup(res.root, res.path, min_size=1000)
    assert f.rule.id == "node_modules" and f.rule.safety == SAFE
    assert f.path.endswith("node_modules")


def test_classify_depends_on_project():
    d = Node("target", 10, [Node("x", 10)])
    assert classify("/p/target", d, "Rust").id == "cargo_target"
    assert classify("/p/target", d, "") is None
    big = Node("crash.dmp", 100 * MB)
    assert classify("/x/crash.dmp", big).safety == SAFE
    assert classify("/x/crash.dmp", Node("crash.dmp", 10)) is None


def test_find_cold_picks_old_entries():
    now = time.time()
    old = Node("old", 20 * MB, [Node("f", 20 * MB, mtime=now - 3 * 365 * 86400)],
               mtime=now - 3 * 365 * 86400)
    new = Node("new", 30 * MB, [Node("g", 30 * MB, mtime=now)], mtime=now)
    root = Node("r", 50 * MB, [old, new])
    cold = find_cold(root, "/r", min_days=730, min_size=MB, now=now)
    assert [c.path for c in cold] == ["/r/old"]


def test_age_bucket():
    now = 10_000_000_000.0
    assert age_bucket(0, now) == -1
    assert age_bucket(now - 86400, now) == 0
    assert age_bucket(now - 10 * 365 * 86400, now) == 5


# -- différences --
def test_diff_trees_detects_growth_shrink_new_gone():
    old = Node("r", 1000, [Node("a", 600, [Node("a1", 400), Node("a2", 200)]),
                           Node("gone", 300), Node("same", 100)])
    new = Node("r", 1200, [Node("a", 900, [Node("a1", 700), Node("a2", 200)]),
                           Node("fresh", 200), Node("same", 100)])
    d = diff_trees(old, new)
    assert d.delta == 200
    by = {k.name: k for k in d.children}
    assert set(by) == {"a", "gone", "fresh"}           # « same » a disparu
    assert by["a"].delta == 300 and by["gone"].delta == -300 and by["fresh"].delta == 200
    assert by["a"].children[0].name == "a1" and by["a"].children[0].delta == 300
    assert by["gone"].size == 300


def test_diff_residual_for_grouped_items():
    old = Node("r", 100, [Node("big", 50), Node("(3 petits éléments)", 50, grouped=True)])
    new = Node("r", 130, [Node("big", 50), Node("(5 petits éléments)", 80, grouped=True)])
    d = diff_trees(old, new)
    assert d.delta == 30 and d.children[0].grouped and d.children[0].delta == 30


def test_diff_identical_is_empty():
    t = Node("r", 10, [Node("a", 10)])
    assert diff_trees(t, t).children == [] and diff_trees(t, t).delta == 0


def test_growth_map():
    old = Node("r", 10, [Node("a", 5), Node("b", 5)])
    new = Node("r", 18, [Node("a", 13), Node("b", 5)])
    assert growth_map(diff_trees(old, new), "/r") == {"/r/a": 8, "/r": 8}


def test_signed_size():
    assert signed_size(2048) == "+2.0 Ko" and signed_size(-2048) == "-2.0 Ko" and signed_size(0) == "0 o"


# -- instantanés --
def test_snapshot_roundtrip_and_rotation(tmp_path):
    res = Scanner().scan(str(make_tree(_mk(tmp_path))))
    d = str(tmp_path / "snaps")
    f1 = save_snapshot(res, d, created=1000.0)
    save_snapshot(res, d, created=2000.0)
    infos = list_snapshots(res.path, d)
    assert [i.created for i in infos] == [2000.0, 1000.0]
    back = load_snapshot(f1)
    assert back.path == res.path and back.root.size == res.root.size
    proj = next(c for c in back.root.children if c.name == "proj")
    assert proj.project == "Node" and proj.mtime > 0
    assert diff_trees(res.root, back.root).children == []
    assert list_snapshots("/autre", d) == []


def _mk(tmp_path):
    p = tmp_path / "data"
    p.mkdir()
    return p


# -- doublons --
def test_duplicates(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "a.bin").write_bytes(b"A" * 2000)
    (tmp_path / "x" / "copy.bin").write_bytes(b"A" * 2000)
    (tmp_path / "x" / "same_size.bin").write_bytes(b"B" * 2000)   # même taille, contenu différent
    (tmp_path / "x" / "tiny.bin").write_bytes(b"A" * 10)
    big = os.urandom(200_000)
    (tmp_path / "b1.dat").write_bytes(big)
    (tmp_path / "x" / "b2.dat").write_bytes(big)
    (tmp_path / "x" / "b3.dat").write_bytes(big[:-1] + b"!")      # diffère à la fin
    res = DuplicateFinder(min_size=1000).find(str(tmp_path))
    sets = sorted(sorted(os.path.basename(p) for p in g.paths) for g in res.groups)
    assert sets == [["a.bin", "copy.bin"], ["b1.dat", "b2.dat"]]
    assert res.reclaimable == 2000 + 200_000
    assert res.groups[0].size == 200_000


def test_duplicates_ignore_hardlinks(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"A" * 5000)
    try:
        os.link(tmp_path / "a.bin", tmp_path / "b.bin")
    except OSError:
        return
    assert DuplicateFinder(min_size=1000).find(str(tmp_path)).groups == []


# -- arbre et export --
def test_find_chain():
    leaf = Node("c", 1)
    root = Node("r", 1, [Node("a", 1, [Node("b", 1, [leaf])])])
    chain = find_chain(root, "/base", "/base/a/b")
    assert [p for _n, p in chain] == ["/base", "/base/a", "/base/a/b"]
    assert find_chain(root, "/base", "/ailleurs") is None


def test_export_html_is_self_contained(tmp_path):
    res = Scanner().scan(str(make_tree(tmp_path)))
    page = export_html(res.root, res.path, find_cleanup(res.root, res.path, 1000))
    assert page.startswith("<!doctype html>") and "node_modules" in page
    assert "__DATA__" not in page and "</script></body>" in page
    assert "Gains rapides" in page
