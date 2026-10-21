import os
from types import SimpleNamespace

import pytest

from diskmap.core import Node, Scanner, explain
from diskmap.core import scanner as scanner_mod
from diskmap.core.explain import UNREADABLE_NAME


def test_explain_known_folder_is_case_insensitive():
    assert "Store" in explain(r"C:\Program Files\WindowsApps", "denied")
    assert "restauration" in explain(r"C:\System Volume Information", "denied")


def test_explain_falls_back_to_reason():
    assert "administrateur" in explain(r"C:\Inconnu", "denied")
    assert "Cible : X" in explain(r"C:\Lien", "junction", "X")


def test_cloud_only_detection():
    on_demand = SimpleNamespace(st_file_attributes=0x400000)
    local = SimpleNamespace(st_file_attributes=0x20)
    no_attr = SimpleNamespace()
    assert scanner_mod.is_cloud_only(on_demand)
    assert not scanner_mod.is_cloud_only(local)
    assert not scanner_mod.is_cloud_only(no_attr)


def test_unreadable_gap_added_for_whole_drive(monkeypatch):
    monkeypatch.setattr(scanner_mod.os.path, "ismount", lambda p: True)
    root = Node("r", 100, [Node("f", 100)])
    gap = Scanner._add_unreadable(root, "X:\\", 160)
    assert gap == 60 and root.size == 160
    extra = root.children[-1]
    assert extra.unreadable and extra.name == UNREADABLE_NAME and extra.note


def test_no_unreadable_gap_for_plain_folder(tmp_path):
    root = Node("r", 100, [Node("f", 100)])
    assert Scanner._add_unreadable(root, str(tmp_path), 10_000) == 0
    assert len(root.children) == 1


def test_no_unreadable_gap_when_scan_exceeds_used(monkeypatch):
    monkeypatch.setattr(scanner_mod.os.path, "ismount", lambda p: True)
    root = Node("r", 200, [Node("f", 200)])
    assert Scanner._add_unreadable(root, "X:\\", 100) == 0


def test_compact_never_merges_unreadable_block():
    root = Node("r", 1_000_100, [Node("big", 1_000_000),
                                 Node("lock", 50, grouped=True, unreadable=True, count=0),
                                 Node("tiny", 50)])
    scanner_mod.compact(root, 1000)
    assert any(c.unreadable for c in root.children)


def test_duplicates_never_read_cloud_only_files(tmp_path, monkeypatch):
    """Lire un placeholder OneDrive le téléchargerait : il doit être ignoré par la recherche de doublons."""
    from diskmap.core import DuplicateFinder, duplicates

    (tmp_path / "a.bin").write_bytes(b"A" * 5000)
    (tmp_path / "b.bin").write_bytes(b"A" * 5000)
    monkeypatch.setattr(duplicates, "is_cloud_only", lambda st: True)
    assert DuplicateFinder(min_size=1000).find(str(tmp_path)).groups == []


def test_symlink_is_reported_not_followed(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (target / "f.bin").write_bytes(b"x" * 10_000)
    try:
        os.symlink(target, tmp_path / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("création de lien symbolique non autorisée")
    result = Scanner().scan(str(tmp_path))
    assert any(s.reason == "symlink" and s.path.endswith("link") for s in result.skipped)
    assert result.files == 1  # pas de double comptage
