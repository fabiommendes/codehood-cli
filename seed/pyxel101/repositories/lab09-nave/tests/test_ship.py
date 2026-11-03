from ship import Bullet, Ship, cleanup


def test_bullet_moves_up():
    bullet = Bullet(10, 50)
    bullet.update()
    assert (bullet.x, bullet.y) == (10, 46)


def test_bullet_alive_until_it_leaves_the_top():
    assert Bullet(0, 0).alive()
    assert not Bullet(0, -1).alive()


def test_ship_moves_and_stops_at_edges():
    ship = Ship(10, 100)
    ship.move(1, 160)
    assert ship.x == 12
    ship.move(-1, 160)
    ship.move(-1, 160)
    assert ship.x == 8
    ship.x = 0
    ship.move(-1, 160)
    assert ship.x == 0
    ship.x = 151
    ship.move(1, 160)
    assert ship.x == 152


def test_shoot_leaves_from_the_middle():
    bullet = Ship(20, 100, width=8).shoot()
    assert (bullet.x, bullet.y) == (24, 100)


def test_rect():
    assert Ship(3, 4, width=8, height=6).rect() == (3, 4, 8, 6)


def test_cleanup_returns_new_list_of_live_bullets():
    bullets = [Bullet(0, 5), Bullet(0, -3), Bullet(1, 0)]
    result = cleanup(bullets)
    assert [b.x for b in result] == [0, 1]
    assert len(bullets) == 3
