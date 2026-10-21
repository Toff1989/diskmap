"""Suppression encadrée : on teste d'abord ce qui doit être REFUSÉ, puis ce qui est exécuté."""
import dataclasses
import json
import os
import stat
import sys

import pytest

from diskmap.core import Node, Remover, Scanner, find_cleanup, plan_removal
from diskmap.core import removal
from diskmap.core.cleanup import Finding, classify


@pytest.fixture(autouse=True)
def data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DISKMAP_HOME", str(tmp_path / "home"))


def make_dir_link(link, target):
    """Lien (symbolique, ou jonction sous Windows sans privilège) ; ignore le test si impossible."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if sys.platform == "win32":
        import subprocess
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        if done.returncode == 0:
            return
    pytest.skip("création de lien impossible")


def make_tree(tmp_path):
    root = tmp_path / "data"
    (root / "proj" / "node_modules" / "pkg").mkdir(parents=True)
    (root / "proj" / "package.json").write_text("{}")
    (root / "proj" / "node_modules" / "pkg" / "index.js").write_bytes(b"x" * 400_000)
    (root / "keep.bin").write_bytes(b"k" * 100_000)
    return root


def findings_of(root):
    res = Scanner().scan(str(root))
    return find_cleanup(res.root, str(root), min_size=1)


def fake_finding(path, name=None, is_dir=True, size=1 << 30):
    """Finding fabriqué à la main (le disque n'est pas forcément scanné)."""
    name = name or os.path.basename(path)
    node = Node(name, size, [Node("x", 1)] if is_dir else [])
    return Finding(str(path), node, classify(str(path), node))


# -- ce qui doit être refusé ---------------------------------------------------
def test_plan_for_node_modules_is_a_runnable_delete(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    plan = plan_removal(finding, str(root))
    assert plan.kind == "delete" and plan.runnable and not plan.blocked
    assert plan.targets == ((finding.path, False),)


def test_target_must_be_inside_the_scanned_root(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    assert "hors du dossier analysé" in plan_removal(finding, str(elsewhere)).blocked
    root_as_target = dataclasses.replace(finding, path=str(root))
    assert plan_removal(root_as_target, str(root)).blocked


def test_missing_target_is_blocked(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    gone = dataclasses.replace(finding, path=str(root / "proj" / "absent" / "node_modules"))
    assert "introuvable" in plan_removal(gone, str(root)).blocked


def test_target_that_no_longer_matches_its_rule_is_blocked(tmp_path):
    """Si le dossier ne s'appelle plus node_modules, on ne le supprime pas."""
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    renamed = root / "proj" / "important_documents"
    os.rename(finding.path, renamed)
    stale = dataclasses.replace(finding, path=str(renamed))
    plan = plan_removal(stale, str(root))
    assert "ne correspond plus" in plan.blocked
    assert not plan.runnable


def test_protected_and_ancestor_paths_are_refused(tmp_path):
    home = os.path.expanduser("~")
    root = os.path.dirname(home)  # le dossier qui CONTIENT le dossier personnel
    finding = fake_finding(os.path.join(home, "node_modules"))
    # même si l'analyse portait sur le dossier parent, le dossier personnel lui-même est protégé
    assert removal.check_target(home, root, finding, must_match=False)
    assert removal.check_target(os.path.abspath(os.sep), root, finding, must_match=False)


def test_manual_rules_are_never_executable(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    for name in ("disk.vhdx", "ext4.vhdx", "machine.vmdk"):
        plan = plan_removal(fake_finding(root / name, is_dir=False), str(root))
        assert plan.kind == "none" and not plan.runnable
        assert "ne la supprime pas" in plan.blocked


def test_windows_update_folders_stay_manual(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    plan = plan_removal(fake_finding(root / "SoftwareDistribution"), str(root))
    assert plan.kind == "none" and not plan.runnable


def test_symlink_target_is_refused(tmp_path):
    root = make_tree(tmp_path)
    real = tmp_path / "precious"
    real.mkdir()
    (real / "a.txt").write_text("a")
    link = root / "proj" / "node_modules_link"
    make_dir_link(link, real)
    finding = fake_finding(root / "proj" / "node_modules_link", name="node_modules")
    plan = plan_removal(finding, str(root))
    assert "lien" in plan.blocked
    assert (real / "a.txt").exists()


def test_a_link_in_the_parent_chain_is_refused(tmp_path):
    root = tmp_path / "data"
    outside = tmp_path / "outside"
    (outside / "node_modules").mkdir(parents=True)
    (outside / "node_modules" / "a.js").write_text("a")
    root.mkdir()
    make_dir_link(root / "via", outside)
    plan = plan_removal(fake_finding(root / "via" / "node_modules"), str(root))
    assert "lien" in plan.blocked
    assert (outside / "node_modules" / "a.js").exists()


# -- suppression --------------------------------------------------------------
def test_removes_the_folder_and_counts_freed_bytes(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    plan = plan_removal(finding, str(root))
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert outcome.ok and outcome.freed >= 400_000
    assert not os.path.exists(finding.path)
    assert (root / "proj" / "package.json").exists() and (root / "keep.bin").exists()


def test_read_only_files_are_removed(tmp_path):
    root = make_tree(tmp_path)
    ro = root / "proj" / "node_modules" / "pkg" / "locked.js"
    ro.write_text("x")
    os.chmod(ro, stat.S_IREAD)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    (outcome,) = Remover([plan_removal(finding, str(root))], str(root), log=False).run()
    assert outcome.ok and not os.path.exists(finding.path)


def test_symlinks_inside_are_removed_but_never_followed(tmp_path):
    root = make_tree(tmp_path)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "important.txt").write_text("à garder")
    make_dir_link(root / "proj" / "node_modules" / "lnk", precious)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    (outcome,) = Remover([plan_removal(finding, str(root))], str(root), log=False).run()
    assert outcome.ok and not os.path.exists(finding.path)
    assert (precious / "important.txt").read_text() == "à garder"


def test_container_rules_are_emptied_but_kept(tmp_path):
    root = tmp_path / "data"
    cache = root / ".cache"
    (cache / "sub").mkdir(parents=True)
    (cache / "a.bin").write_bytes(b"a" * 5000)
    (cache / "sub" / "b.bin").write_bytes(b"b" * 5000)
    plan = plan_removal(fake_finding(cache), str(root))
    assert plan.kind == "delete" and plan.targets == ((str(cache), True),)
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert outcome.ok and outcome.freed >= 10_000
    assert cache.is_dir() and os.listdir(cache) == []


def test_gradle_only_caches_subfolder_is_removed(tmp_path):
    root = tmp_path / "data"
    gradle = root / ".gradle"
    (gradle / "caches").mkdir(parents=True)
    (gradle / "caches" / "big.bin").write_bytes(b"g" * 5000)
    (gradle / "gradle.properties").write_text("org.gradle.jvmargs=-Xmx2g")
    (outcome,) = Remover([plan_removal(fake_finding(gradle), str(root))], str(root), log=False).run()
    assert outcome.ok
    assert not (gradle / "caches").exists()
    assert (gradle / "gradle.properties").exists()      # la config de l'utilisateur est conservée


def test_cancel_before_start_deletes_nothing(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    remover = Remover([plan_removal(finding, str(root))], str(root), log=False)
    remover.cancel()
    assert remover.run() == []
    assert os.path.exists(finding.path)


def test_revalidation_catches_a_target_that_disappeared(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    plan = plan_removal(finding, str(root))
    import shutil
    shutil.rmtree(finding.path)                 # le disque change entre la confirmation et l'exécution
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert not outcome.ok and "introuvable" in outcome.message


def test_revalidation_refuses_a_target_swapped_for_a_link(tmp_path):
    root = make_tree(tmp_path)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "important.txt").write_text("à garder")
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    plan = plan_removal(finding, str(root))
    import shutil
    shutil.rmtree(finding.path)
    make_dir_link(finding.path, precious)
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert not outcome.ok
    assert (precious / "important.txt").exists()


def test_every_removal_is_logged(tmp_path):
    root = make_tree(tmp_path)
    finding = next(f for f in findings_of(root) if f.rule.id == "node_modules")
    Remover([plan_removal(finding, str(root))], str(root)).run()
    lines = open(removal.log_path(), encoding="utf-8").read().splitlines()
    entry = json.loads(lines[-1])
    assert entry["path"] == finding.path and entry["ok"] is True and entry["rule"] == "node_modules"


@pytest.mark.skipif(sys.platform != "win32", reason="chemins longs : Windows uniquement")
def test_windows_long_paths_are_removed(tmp_path):
    root = tmp_path / "data"
    deep = root / "node_modules"
    for _ in range(14):
        deep = deep / ("d" * 30)                # > 260 caractères au total
    os.makedirs("\\\\?\\" + str(deep))
    with open("\\\\?\\" + str(deep / "f.js"), "wb") as f:
        f.write(b"x" * 1000)
    plan = plan_removal(fake_finding(root / "node_modules"), str(root))
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert outcome.ok and not os.path.exists(root / "node_modules")


# -- commandes ----------------------------------------------------------------
def npm_cache(tmp_path):
    root = tmp_path / "data"
    cache = root / ".npm" / "_cacache"
    cache.mkdir(parents=True)
    (cache / "blob").write_bytes(b"n" * 20_000)
    return root, cache


def test_tool_rule_runs_the_official_command_without_a_shell(tmp_path, monkeypatch):
    root, cache = npm_cache(tmp_path)
    monkeypatch.setattr(removal.shutil, "which", lambda name: "/fake/" + name)
    plan = plan_removal(fake_finding(cache), str(root))
    assert plan.kind == "command" and plan.argv == ("/fake/npm", "cache", "clean", "--force")

    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        for name in os.listdir(cache):
            os.unlink(cache / name)             # la vraie commande vide le cache
        return type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(removal.subprocess, "run", fake_run)
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert outcome.ok and outcome.freed >= 20_000
    argv, kwargs = calls[0]
    assert isinstance(argv, list) and not kwargs.get("shell")
    assert kwargs["stdin"] is removal.subprocess.DEVNULL


def test_failed_command_is_reported_not_hidden(tmp_path, monkeypatch):
    root, cache = npm_cache(tmp_path)
    monkeypatch.setattr(removal.shutil, "which", lambda name: "/fake/" + name)
    monkeypatch.setattr(removal.subprocess, "run", lambda argv, **kw: type(
        "P", (), {"returncode": 1, "stdout": "", "stderr": "npm ERR! boom"})())
    plan = plan_removal(fake_finding(cache), str(root))
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert not outcome.ok and "boom" in outcome.message and outcome.freed == 0


def test_missing_tool_falls_back_to_deleting_the_cache_folder(tmp_path, monkeypatch):
    root, cache = npm_cache(tmp_path)
    monkeypatch.setattr(removal.shutil, "which", lambda name: None)
    plan = plan_removal(fake_finding(cache), str(root))
    assert plan.kind == "delete" and "introuvable" in plan.summary
    (outcome,) = Remover([plan], str(root), log=False).run()
    assert outcome.ok and not cache.exists()


def test_missing_tool_without_fallback_is_blocked(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    (root / "docker.raw").write_bytes(b"d")
    monkeypatch.setattr(removal.shutil, "which", lambda name: None)
    plan = plan_removal(fake_finding(root / "docker.raw", is_dir=False), str(root))
    assert plan.kind == "command" and "introuvable" in plan.blocked and not plan.runnable


def test_admin_only_commands_are_blocked_without_admin(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    (root / "hiberfil.sys").write_bytes(b"h")
    monkeypatch.setattr(removal.shutil, "which", lambda name: "/fake/" + name)
    finding = fake_finding(root / "hiberfil.sys", is_dir=False)
    assert "administrateur" in plan_removal(finding, str(root), is_admin=False).blocked
    allowed = plan_removal(finding, str(root), is_admin=True)
    assert allowed.runnable and allowed.argv[1:] == ("/h", "off")
