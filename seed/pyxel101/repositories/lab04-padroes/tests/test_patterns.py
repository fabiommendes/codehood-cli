from patterns import grid_pos, is_dark, stair_line


def test_is_dark_first_cell_is_light():
    assert is_dark(0, 0) is False


def test_is_dark_alternates_along_a_row():
    assert is_dark(1, 0) is True
    assert is_dark(2, 0) is False


def test_is_dark_alternates_along_a_column():
    assert is_dark(0, 1) is True
    assert is_dark(1, 1) is False


def test_stair_line():
    assert stair_line(1) == "#"
    assert stair_line(3) == "###"
    assert stair_line(0) == ""


def test_grid_pos():
    assert grid_pos(0, 10) == 0
    assert grid_pos(3, 10) == 30


def test_grid_pos_margin():
    assert grid_pos(0, 4, 5) == 5
    assert grid_pos(2, 4, margin=5) == 13
