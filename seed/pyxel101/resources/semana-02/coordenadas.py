# Pontos e retângulos em posições calculadas a partir de variáveis.
import pyxel

LARGURA = 160
ALTURA = 120

pyxel.init(LARGURA, ALTURA, title="Coordenadas")


def update():
    pass


def draw():
    pyxel.cls(0)

    # O pixel (0, 0) fica no canto superior esquerdo; y cresce para baixo.
    pyxel.pset(0, 0, 7)
    pyxel.pset(LARGURA - 1, 0, 8)
    pyxel.pset(0, ALTURA - 1, 11)
    pyxel.pset(LARGURA - 1, ALTURA - 1, 10)

    # Retângulo centralizado: calculamos o canto superior esquerdo.
    w = 40
    h = 20
    x = (LARGURA - w) // 2
    y = (ALTURA - h) // 2
    pyxel.rect(x, y, w, h, 5)
    pyxel.rectb(x, y, w, h, 7)

    # Uma linha de pontos igualmente espaçados.
    espaco = 10
    for i in range(1, 15):
        pyxel.pset(i * espaco, 20, 9)

    # Texto com os valores calculados.
    pyxel.text(4, 4, f"x={x} y={y}", 7)


pyxel.run(update, draw)
