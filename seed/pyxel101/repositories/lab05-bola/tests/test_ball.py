from ball import bounce_pos, bounce_vel


def test_free_movement():
    assert bounce_pos(50, 3, 6, 160) == 53
    assert bounce_vel(50, 3, 6, 160) == 3
    assert bounce_pos(50, -3, 6, 160) == 47
    assert bounce_vel(50, -3, 6, 160) == -3


def test_bounce_on_low_edge():
    assert bounce_pos(8, -5, 6, 160) == 6
    assert bounce_vel(8, -5, 6, 160) == 5


def test_bounce_on_high_edge():
    assert bounce_pos(150, 5, 6, 160) == 153
    assert bounce_vel(150, 5, 6, 160) == -5
