import random

import pyxel

from rain import fall, make_drop

W = 160
H = 120
pyxel.init(W, H, title="Chuva")
drops = []


def update():
    global drops
    if pyxel.frame_count % 4 == 0:
        drops.append(make_drop(random.randrange(W), random.randint(2, 5)))
    drops = fall(drops, H)


def draw():
    pyxel.cls(1)
    for x, y, speed in drops:
        pyxel.line(x, y, x, y + 3, 12)


pyxel.run(update, draw)
