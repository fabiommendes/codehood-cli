from collision import first_hit, overlaps, point_in_rect


def test_contained_rect_overlaps():
    assert overlaps((0, 0, 100, 100), (40, 40, 2, 2))
    assert overlaps((40, 40, 2, 2), (0, 0, 100, 100))


def test_overlap_is_symmetric():
    a, b = (0, 0, 10, 10), (9, 9, 10, 10)
    assert overlaps(a, b) == overlaps(b, a) is True


def test_negative_coordinates():
    assert overlaps((-5, -5, 10, 10), (0, 0, 2, 2))
    assert not overlaps((-10, -10, 5, 5), (0, 0, 5, 5))


def test_corner_touch_is_not_overlap():
    assert not overlaps((0, 0, 10, 10), (10, 10, 5, 5))


def test_point_in_zero_size_rect():
    assert not point_in_rect(0, 0, (0, 0, 0, 0))


def test_first_hit_returns_the_first_not_the_last():
    assert (
        first_hit((0, 0, 10, 10), [(100, 100, 1, 1), (1, 1, 2, 2), (3, 3, 2, 2)]) == 1
    )
