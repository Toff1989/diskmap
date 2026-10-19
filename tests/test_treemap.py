import pytest

from diskmap.core import Node, squarify


def nodes(*sizes):
    return [Node("n%d" % i, s) for i, s in enumerate(sizes)]


def test_empty_and_degenerate_inputs():
    assert squarify([], 0, 0, 100, 100) == []
    assert squarify(nodes(10), 0, 0, 0, 100) == []
    assert squarify(nodes(0, 0), 0, 0, 100, 100) == []


def test_areas_are_proportional_and_fill_the_rectangle():
    items = nodes(600, 300, 100, 50, 25)
    rects = squarify(items, 0, 0, 400, 200)
    total_area = sum(w * h for _, _, _, w, h in rects)
    assert total_area == pytest.approx(400 * 200)
    total = sum(n.size for n in items)
    for node, _, _, w, h in rects:
        assert w * h == pytest.approx(node.size / total * 400 * 200)


def test_rectangles_stay_inside_and_do_not_overlap():
    rects = squarify(nodes(*range(1, 40)), 10, 20, 300, 150)
    for _, x, y, w, h in rects:
        assert x >= 10 - 1e-6 and y >= 20 - 1e-6
        assert x + w <= 310 + 1e-6 and y + h <= 170 + 1e-6
    for i, (_, x1, y1, w1, h1) in enumerate(rects):
        for _, x2, y2, w2, h2 in rects[i + 1:]:
            ox = min(x1 + w1, x2 + w2) - max(x1, x2)
            oy = min(y1 + h1, y2 + h2) - max(y1, y2)
            assert not (ox > 1e-6 and oy > 1e-6)


def test_largest_first():
    rects = squarify(nodes(1, 5, 3), 0, 0, 100, 100)
    assert rects[0][0].size == 5
