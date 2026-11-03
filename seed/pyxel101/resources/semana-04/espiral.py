# Espiral desenhada com while: o raio e o ângulo crescem a cada passo.
import math

import pyxel

pyxel.init(160, 120, title="Espiral")


def update():
    pass


def draw():
    pyxel.cls(0)
    centro_x = 80
    centro_y = 60
    angulo = 0.0
    raio = 1.0

    # Desenha até o raio chegar ao limite da tela.
    while raio < 56:
        x = centro_x + math.cos(angulo) * raio
        y = centro_y + math.sin(angulo) * raio
        pyxel.circ(x, y, 1, 8 + int(raio) % 8)
        angulo = angulo + 0.25
        raio = raio + 0.25


pyxel.run(update, draw)
