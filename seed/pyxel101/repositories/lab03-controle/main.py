import pyxel

from controls import direction, next_x

SIZE = 8
pyxel.init(160, 120, title="Controle")
x = 76
y = 56


def update():
    global x, y
    dx = direction(pyxel.btn(pyxel.KEY_LEFT), pyxel.btn(pyxel.KEY_RIGHT))
    dy = direction(pyxel.btn(pyxel.KEY_UP), pyxel.btn(pyxel.KEY_DOWN))
    # A mesma função serve aos dois eixos: só muda o tamanho da tela.
    x = next_x(x, dx, SIZE, 160)
    y = next_x(y, dy, SIZE, 120)


def draw():
    pyxel.cls(1)
    pyxel.rect(x, y, SIZE, SIZE, 10)


pyxel.run(update, draw)
