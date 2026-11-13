# Quadrado que anda com as setas e não sai da tela.
import pyxel

LARGURA = 160
ALTURA = 120
LADO = 10
VELOCIDADE = 2

x = 75
y = 55

pyxel.init(LARGURA, ALTURA, title="Mover quadrado")


def update():
    global x, y

    if pyxel.btn(pyxel.KEY_LEFT):
        x = x - VELOCIDADE
    if pyxel.btn(pyxel.KEY_RIGHT):
        x = x + VELOCIDADE
    if pyxel.btn(pyxel.KEY_UP):
        y = y - VELOCIDADE
    if pyxel.btn(pyxel.KEY_DOWN):
        y = y + VELOCIDADE

    # Limites da tela: o quadrado inteiro precisa continuar visível.
    x = max(x, 0)
    x = min(x, LARGURA - LADO)
    y = max(y, 0)
    y = min(y, ALTURA - LADO)


def draw():
    pyxel.cls(1)
    pyxel.rect(x, y, LADO, LADO, 9)
    pyxel.text(4, 4, f"({x}, {y})", 7)


pyxel.run(update, draw)
