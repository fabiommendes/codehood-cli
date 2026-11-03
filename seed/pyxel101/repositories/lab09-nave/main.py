import pyxel

from collision import first_hit
from ship import Ship, cleanup

pyxel.init(160, 120, title="Nave")
ship = Ship(76, 104)
bullets = []
enemies = [(20 + 30 * i, 16, 8, 8) for i in range(4)]


def update():
    global bullets, enemies
    ship.move(int(pyxel.btn(pyxel.KEY_RIGHT)) - int(pyxel.btn(pyxel.KEY_LEFT)), 160)
    if pyxel.btnp(pyxel.KEY_SPACE):
        bullets.append(ship.shoot())
    for bullet in bullets:
        bullet.update()
        hit = first_hit((bullet.x, bullet.y, 1, 3), enemies)
        if hit is not None:
            enemies = enemies[:hit] + enemies[hit + 1 :]
            bullet.y = -100
    bullets = cleanup(bullets)


def draw():
    pyxel.cls(0)
    pyxel.rect(*ship.rect(), 11)
    for bullet in bullets:
        pyxel.rect(bullet.x, bullet.y, 1, 3, 10)
    for x, y, w, h in enemies:
        pyxel.rect(x, y, w, h, 8)


pyxel.run(update, draw)
