from collision import first_hit, overlaps, point_in_rect


def test_overlapping_rects():
    assert overlaps((0, 0, 10, 10), (5, 5, 10, 10))


def test_separated_rects():
    assert not overlaps((0, 0, 10, 10), (20, 0, 5, 5))
    assert not overlaps((0, 0, 10, 10), (0, 20, 5, 5))


def test_touching_edges_do_not_overlap():
    assert not overlaps((0, 0, 10, 10), (10, 0, 10, 10))
    assert not overlaps((0, 0, 10, 10), (0, 10, 10, 10))


def test_point_in_rect():
    assert point_in_rect(5, 5, (0, 0, 10, 10))
    assert point_in_rect(0, 0, (0, 0, 10, 10))
    assert not point_in_rect(10, 5, (0, 0, 10, 10))
    assert not point_in_rect(-1, 5, (0, 0, 10, 10))


def test_first_hit():
    others = [(50, 50, 5, 5), (0, 0, 10, 10), (2, 2, 4, 4)]
    assert first_hit((1, 1, 3, 3), others) == 1
    assert first_hit((100, 100, 3, 3), others) is None
    assert first_hit((1, 1, 3, 3), []) is None
