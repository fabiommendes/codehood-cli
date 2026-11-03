# Colisão entre retângulos alinhados aos eixos (AABB).
import pyxel

LARGURA = 160
ALTURA = 120

# Cada retângulo é uma tupla (x, y, w, h).
fixo = (60, 40, 40, 30)
movel = [10, 10, 24, 18]


def overlaps(a, b):
    """True se os retângulos a e b tiverem área em comum."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def update():
    if pyxel.btn(pyxel.KEY_LEFT):
        movel[0] -= 2
    if pyxel.btn(pyxel.KEY_RIGHT):
        movel[0] += 2
    if pyxel.btn(pyxel.KEY_UP):
        movel[1] -= 2
    if pyxel.btn(pyxel.KEY_DOWN):
        movel[1] += 2


def draw():
    pyxel.cls(0)
    batendo = overlaps(fixo, tuple(movel))
    pyxel.rect(*fixo, 5)
    pyxel.rect(*movel, 8 if batendo else 11)
    pyxel.text(4, 4, "BATEU!" if batendo else "livre", 7)


pyxel.init(LARGURA, ALTURA, title="AABB")
pyxel.run(update, draw)
