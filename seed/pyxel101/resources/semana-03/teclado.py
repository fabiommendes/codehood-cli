# Mostra qual tecla de direção está pressionada.
import pyxel

pyxel.init(160, 120, title="Teclado")


def update():
    # Q fecha o programa, além do Esc padrão.
    if pyxel.btnp(pyxel.KEY_Q):
        pyxel.quit()


def draw():
    pyxel.cls(0)
    pyxel.text(4, 4, "Aperte as setas (Q sai)", 7)

    if pyxel.btn(pyxel.KEY_LEFT):
        mensagem = "esquerda"
    elif pyxel.btn(pyxel.KEY_RIGHT):
        mensagem = "direita"
    elif pyxel.btn(pyxel.KEY_UP):
        mensagem = "cima"
    elif pyxel.btn(pyxel.KEY_DOWN):
        mensagem = "baixo"
    else:
        mensagem = "nenhuma"

    pyxel.text(4, 56, f"Tecla: {mensagem}", 10)

    # btnp só é verdadeiro no quadro em que a tecla foi apertada.
    if pyxel.btnp(pyxel.KEY_SPACE):
        pyxel.circ(80, 90, 10, 8)
    else:
        pyxel.circb(80, 90, 10, 13)


pyxel.run(update, draw)
