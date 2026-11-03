from shapes import center, color_at, mirror_x


def test_color_at_first_cell():
    assert color_at(0, 0) == 0
    assert color_at(7, 7) == 0


def test_color_at_moves_along_the_row():
    assert color_at(8, 0) == 1
    assert color_at(24, 0) == 3


def test_color_at_moves_down_the_rows():
    assert color_at(0, 8) == 4
    assert color_at(8, 8) == 5
    assert color_at(31, 31) == 15


def test_center():
    assert center(160, 24) == 68
    assert center(120, 16) == 52


def test_center_rounds_down():
    assert center(161, 24) == 68
    assert center(121, 16) == 52


def test_mirror_x():
    assert mirror_x(0, 8, 160) == 152
    assert mirror_x(152, 8, 160) == 0
    assert mirror_x(76, 8, 160) == 76
