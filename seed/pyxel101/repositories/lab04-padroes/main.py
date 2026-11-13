import pyxel
from patterns import grid_pos, is_dark, stair_line

pyxel.init(160, 120, title="Padroes")


def draw():
    pyxel.cls(0)
    # Tabuleiro de 8 x 8 casas: um laço dentro de outro.
    for row in range(8):
        for col in range(8):
            if is_dark(col, row):
                color = 1
            else:
                color = 7
            pyxel.rect(col * 8, row * 8, 8, 8, color)
    # Grade de pontos de 6 x 6, toda dentro da tela de 160 x 120.
    for row in range(6):
        for col in range(6):
            pyxel.pset(grid_pos(col, 8, 90), grid_pos(row, 8, 10), 10)
    # Escada de texto.
    for n in range(1, 6):
        pyxel.text(90, 60 + n * 8, stair_line(n), 11)


pyxel.run(lambda: None, draw)
