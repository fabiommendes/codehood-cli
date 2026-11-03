import pyxel

from movement import jump, step

pyxel.init(128, 128, title="Plataforma")
pyxel.load("assets/plataforma.pyxres")
x, y, vy, on_ground = 8, 0, 0, False


def is_solid(tx: int, ty: int) -> bool:
    return pyxel.tilemaps[0].pget(tx, ty) == (1, 0)


def update():
    global x, y, vy, on_ground
    vx = int(pyxel.btn(pyxel.KEY_RIGHT)) - int(pyxel.btn(pyxel.KEY_LEFT))
    if pyxel.btnp(pyxel.KEY_SPACE):
        vy = jump(vy, on_ground)
    x, y, vy, on_ground = step(x, y, vx, vy, is_solid)


def draw():
    pyxel.cls(12)
    pyxel.bltm(0, 0, 0, 0, 0, 128, 128, 0)
    pyxel.blt(x, y, 0, 16, 0, 8, 8, 0)


pyxel.run(update, draw)
