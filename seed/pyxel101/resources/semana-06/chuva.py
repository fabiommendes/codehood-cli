# Gotas de chuva guardadas em uma lista de pares [x, y].
import pyxel

LARGURA = 160
ALTURA = 120

gotas = []


def nova_gota():
    return [pyxel.rndi(0, LARGURA - 1), 0]


def update():
    # Uma gota nova a cada 3 quadros.
    if pyxel.frame_count % 3 == 0:
        gotas.append(nova_gota())

    for gota in gotas:
        gota[1] += 3

    # Reconstrói a lista só com as gotas que ainda estão na tela. Remover
    # itens durante o for é perigoso, então filtramos.
    gotas[:] = [g for g in gotas if g[1] < ALTURA]


def draw():
    pyxel.cls(1)
    for x, y in gotas:
        pyxel.line(x, y, x, y + 3, 12)
    pyxel.text(4, 4, f"gotas: {len(gotas)}", 7)


pyxel.init(LARGURA, ALTURA, title="Chuva")
pyxel.run(update, draw)
