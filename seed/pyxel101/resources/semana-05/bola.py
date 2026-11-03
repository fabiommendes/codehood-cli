# Bola quicando, organizada em funções pequenas.
import pyxel

LARGURA = 160
ALTURA = 120
RAIO = 6

x = 40.0
y = 30.0
vx = 1.5
vy = 1.0


def move(posicao, velocidade):
    """Devolve a nova posição em um eixo depois de um quadro."""
    return posicao + velocidade


def quica(posicao, velocidade, limite_min, limite_max):
    """Inverte a velocidade quando a posição passa de um dos limites."""
    if posicao < limite_min or posicao > limite_max:
        return -velocidade
    return velocidade


def update():
    global x, y, vx, vy
    x = move(x, vx)
    y = move(y, vy)
    vx = quica(x, vx, RAIO, LARGURA - RAIO)
    vy = quica(y, vy, RAIO, ALTURA - RAIO)


def draw():
    pyxel.cls(1)
    pyxel.circ(x, y, RAIO, 10)
    pyxel.circb(x, y, RAIO, 9)
    pyxel.text(4, 4, "Funcoes: move e quica", 7)


pyxel.init(LARGURA, ALTURA, title="Bola")
pyxel.run(update, draw)
