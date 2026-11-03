from rain import fall, lowest_drop, make_drop


def test_make_drop():
    assert make_drop(10, 3) == [10, 0, 3]


def test_fall_moves_each_drop():
    drops = [[1, 0, 2], [5, 10, 4]]
    assert fall(drops, 100) == [[1, 2, 2], [5, 14, 4]]


def test_fall_discards_drops_past_the_floor():
    drops = [[1, 98, 2], [5, 10, 4]]
    result = fall(drops, 100)
    assert [d[0] for d in result] == [5]


def test_fall_does_not_change_the_input():
    drops = [[1, 0, 2]]
    fall(drops, 100)
    assert drops == [[1, 0, 2]]


def test_lowest_drop():
    drops = [[1, 5, 1], [2, 50, 1]]
    assert lowest_drop(drops)[0] == 2
    assert lowest_drop([]) is None
