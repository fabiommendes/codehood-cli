# Mostra as 16 cores da paleta padrão do Pyxel em uma grade 4x4.
import pyxel

TAMANHO = 30  # lado de cada quadrado, em pixels

pyxel.init(120, 120, title="As 16 cores")


def update():
    pass


def draw():
    pyxel.cls(0)
    for cor in range(16):
        # Converte o índice da cor em linha e coluna da grade.
        coluna = cor % 4
        linha = cor // 4
        x = coluna * TAMANHO
        y = linha * TAMANHO
        pyxel.rect(x, y, TAMANHO, TAMANHO, cor)
        # O número muda de cor para continuar legível sobre o fundo.
        cor_texto = 7 if cor in (0, 1, 2, 4, 5) else 0
        pyxel.text(x + 3, y + 3, str(cor), cor_texto)


pyxel.run(update, draw)
