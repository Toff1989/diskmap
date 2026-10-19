import pytest

from diskmap.core import Node, ScanCancelled, Scanner
from diskmap.core import scanner as scanner_mod


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "big.bin").write_bytes(b"x" * 200_000)
    (tmp_path / "a" / "mid.bin").write_bytes(b"x" * 100_000)
    (tmp_path / "a" / "b" / "deep.bin").write_bytes(b"x" * 50_000)
    (tmp_path / "empty.txt").write_bytes(b"")
    return tmp_path


def test_scan_counts_files_and_sizes(tree):
    result = Scanner().scan(str(tree))
    assert result.files == 4
    assert result.root.size >= 350_000
    names = {c.name for c in result.root.children}
    assert {"big.bin", "a"} <= names
    assert "empty.txt" not in names  # fichiers vides ignorés


def test_directory_size_is_sum_of_children(tree):
    root = Scanner().scan(str(tree)).root
    a = next(c for c in root.children if c.name == "a")
    assert a.size >= 150_000
    assert a.is_dir


def test_cancel_raises(tree):
    scanner = Scanner()
    scanner.cancel()
    with pytest.raises(ScanCancelled):
        scanner.scan(str(tree))


def test_missing_path_raises(tmp_path):
    with pytest.raises(OSError):
        Scanner().scan(str(tmp_path / "nope"))


def test_skip_set_is_honoured(tree):
    skipped = str(tree / "a")
    result = Scanner(skip={skipped}).scan(str(tree))
    assert "a" not in {c.name for c in result.root.children}


def test_prune_groups_the_smallest():
    kids = [Node("f%d" % i, i + 1) for i in range(scanner_mod.MAX_KIDS + 50)]
    pruned = scanner_mod.prune(kids)
    assert len(pruned) == scanner_mod.MAX_KIDS + 1
    other = pruned[-1]
    assert other.grouped and other.count == 50
    assert other.size == sum(range(1, 51))


def test_compact_merges_small_items_and_keeps_total():
    root = Node("r", 1010, [Node("big", 1000), Node("s1", 5), Node("s2", 5)])
    scanner_mod.compact(root, 100)
    assert [c.name for c in root.children][0] == "big"
    grouped = root.children[-1]
    assert grouped.grouped and grouped.size == 10 and grouped.count == 2
    assert sum(c.size for c in root.children) == 1010
