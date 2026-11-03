from controls import clamp, direction, next_x


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-3, 0, 10) == 0
    assert clamp(42, 0, 10) == 10


def test_direction_single_keys():
    assert direction(True, False) == -1
    assert direction(False, True) == 1


def test_direction_opposites_cancel():
    assert direction(True, True) == 0
    assert direction(False, False) == 0


def test_next_x_free():
    assert next_x(50, 1, 8, 160) == 52
    assert next_x(50, -1, 8, 160, speed=3) == 47
    assert next_x(50, 0, 8, 160) == 50


def test_next_x_stays_inside_screen():
    assert next_x(0, -1, 8, 160) == 0
    assert next_x(151, 1, 8, 160) == 152
    assert next_x(152, 1, 8, 160) == 152


def test_next_x_works_for_the_vertical_axis_too():
    assert next_x(112, 1, 8, 120) == 112
