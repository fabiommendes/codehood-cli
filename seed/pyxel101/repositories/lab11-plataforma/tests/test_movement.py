from movement import GRAVITY, JUMP_SPEED, MAX_FALL, collides, jump, step


def floor_at(row):
    """Mapa com chão sólido a partir da linha `row`."""
    return lambda tx, ty: ty >= row


def test_collides_with_floor():
    is_solid = floor_at(10)
    assert not collides(0, 72, is_solid)
    assert collides(0, 73, is_solid)
    assert collides(0, 80, is_solid)


def test_collides_checks_all_corners():
    only_tile = lambda tx, ty: (tx, ty) == (2, 2)
    assert collides(9, 9, only_tile)
    assert collides(16, 16, only_tile)
    assert not collides(24, 16, only_tile)


def test_jump_only_from_the_ground():
    assert jump(0, True) == JUMP_SPEED
    assert jump(3, False) == 3


def test_step_free_fall_accelerates():
    x, y, vy, on_ground = step(0, 0, 0, 0, floor_at(100))
    assert (x, y, vy, on_ground) == (0, GRAVITY, GRAVITY, False)


def test_step_fall_speed_is_limited():
    _, _, vy, _ = step(0, 0, 0, MAX_FALL, floor_at(100))
    assert vy == MAX_FALL


def test_step_lands_on_the_floor():
    # chão começa na linha 10 (pixel 80); o personagem para em y = 72
    x, y, vy, on_ground = step(0, 70, 0, 3, floor_at(10))
    assert (y, vy, on_ground) == (72, 0, True)


def test_step_standing_stays_on_ground():
    x, y, vy, on_ground = step(0, 72, 0, 0, floor_at(10))
    assert (y, vy, on_ground) == (72, 0, True)


def test_step_walks_and_stops_at_wall():
    wall = lambda tx, ty: tx >= 5
    assert step(0, 0, 1, 0, wall)[0] == 1
    assert step(32, 0, 1, 0, wall)[0] == 32


def test_step_hits_head_on_ceiling():
    ceiling = lambda tx, ty: ty <= 2
    x, y, vy, on_ground = step(0, 24, 0, -4, ceiling)
    assert (y, vy, on_ground) == (24, 0, False)
