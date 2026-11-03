# Campo de estrelas: cada estrela é uma lista [x, y, velocidade].
import pyxel

LARGURA = 160
ALTURA = 120
QUANTIDADE = 40

estrelas = []


def cria_estrelas():
    for _ in range(QUANTIDADE):
        x = pyxel.rndi(0, LARGURA - 1)
        y = pyxel.rndi(0, ALTURA - 1)
        velocidade = pyxel.rndf(0.3, 2.0)
        estrelas.append([x, y, velocidade])


def update():
    for estrela in estrelas:
        estrela[1] += estrela[2]
        if estrela[1] >= ALTURA:  # saiu pela base: reaparece no topo
            estrela[0] = pyxel.rndi(0, LARGURA - 1)
            estrela[1] = 0


def draw():
    pyxel.cls(0)
    for x, y, velocidade in estrelas:
        # Estrelas rápidas parecem mais próximas, então são mais claras.
        cor = 7 if velocidade > 1.2 else 13
        pyxel.pset(x, y, cor)


pyxel.init(LARGURA, ALTURA, title="Estrelas")
cria_estrelas()
pyxel.run(update, draw)
