# Grade de pontos desenhada com um laço dentro de outro.
import pyxel

pyxel.init(160, 120, title="Grade")


def update():
    pass


def draw():
    pyxel.cls(0)
    # Laço externo: linhas. Laço interno: colunas.
    for linha in range(10):
        for coluna in range(14):
            x = 10 + coluna * 10
            y = 10 + linha * 10
            # A cor depende da soma, o que cria listras diagonais.
            cor = 5 + (linha + coluna) % 3
            pyxel.circ(x, y, 2, cor)


pyxel.run(update, draw)
