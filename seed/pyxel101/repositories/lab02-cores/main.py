import pyxel

from shapes import center, color_at, mirror_x

pyxel.init(160, 120, title="Cores")


def draw():
    pyxel.cls(0)
    # A paleta inteira: 4 colunas por 4 linhas de células 8x8.
    for y in range(32):
        for x in range(32):
            pyxel.pset(x, y, color_at(x, y))
    pyxel.rectb(center(160, 24), center(120, 16), 24, 16, 7)
    pyxel.rect(mirror_x(4, 8, 160), 100, 8, 8, 8)
    pyxel.rect(4, 100, 8, 8, 11)


pyxel.run(lambda: None, draw)
