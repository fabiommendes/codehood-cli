# Colisão entre círculos: comparamos a distância dos centros com a soma dos raios.
import pyxel

LARGURA = 160
ALTURA = 120

fixo = {"x": 80, "y": 60, "r": 20}
movel = {"x": 20, "y": 20, "r": 10}


def circles_collide(a, b):
    """True se os círculos se tocam. Compara quadrados para evitar a raiz."""
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    soma = a["r"] + b["r"]
    return dx * dx + dy * dy <= soma * soma


def update():
    if pyxel.btn(pyxel.KEY_LEFT):
        movel["x"] -= 2
    if pyxel.btn(pyxel.KEY_RIGHT):
        movel["x"] += 2
    if pyxel.btn(pyxel.KEY_UP):
        movel["y"] -= 2
    if pyxel.btn(pyxel.KEY_DOWN):
        movel["y"] += 2


def draw():
    pyxel.cls(0)
    batendo = circles_collide(fixo, movel)
    pyxel.circ(fixo["x"], fixo["y"], fixo["r"], 5)
    pyxel.circ(movel["x"], movel["y"], movel["r"], 8 if batendo else 11)
    pyxel.text(4, 4, "BATEU!" if batendo else "livre", 7)


pyxel.init(LARGURA, ALTURA, title="Colisao de circulos")
pyxel.run(update, draw)
