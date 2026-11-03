from ball import bounce_pos, bounce_vel


def test_touching_the_edge_is_not_a_bounce():
    assert bounce_pos(8, -2, 6, 160) == 6
    assert bounce_vel(8, -2, 6, 160) == -2
    assert bounce_pos(151, 2, 6, 160) == 153
    assert bounce_vel(151, 2, 6, 160) == 2


def test_zero_velocity_stays():
    assert bounce_pos(50, 0, 6, 160) == 50
    assert bounce_vel(50, 0, 6, 160) == 0


def test_corner_bounces_both_axes():
    assert bounce_pos(7, -4, 6, 160) == 6
    assert bounce_vel(7, -4, 6, 160) == 4
    assert bounce_pos(112, 4, 6, 120) == 113
    assert bounce_vel(112, 4, 6, 120) == -4


def test_full_trip_stays_inside_and_turns_around():
    x = 20
    vx = 7
    seen_negative = False
    for _ in range(100):
        new_vx = bounce_vel(x, vx, 6, 160)
        x = bounce_pos(x, vx, 6, 160)
        vx = new_vx
        assert 6 <= x <= 153
        seen_negative = seen_negative or vx < 0
    assert seen_negative
