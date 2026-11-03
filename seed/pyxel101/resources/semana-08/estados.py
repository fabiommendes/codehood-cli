# Três telas (título, jogo, fim) controladas por um dicionário de estado.
import pyxel

LARGURA = 160
ALTURA = 120

# Todo o estado do jogo mora em um único dicionário.
state = {"tela": "titulo", "pontos": 0, "tempo": 0}


def reinicia():
    state["tela"] = "jogo"
    state["pontos"] = 0
    state["tempo"] = 5 * 30  # 5 segundos a 30 quadros por segundo


def update_titulo():
    if pyxel.btnp(pyxel.KEY_RETURN):
        reinicia()


def update_jogo():
    if pyxel.btnp(pyxel.KEY_SPACE):
        state["pontos"] += 1
    state["tempo"] -= 1
    if state["tempo"] <= 0:
        state["tela"] = "fim"


def update_fim():
    if pyxel.btnp(pyxel.KEY_RETURN):
        state["tela"] = "titulo"


def update():
    # Cada tela tem a sua função; o dicionário escolhe qual roda.
    if state["tela"] == "titulo":
        update_titulo()
    elif state["tela"] == "jogo":
        update_jogo()
    else:
        update_fim()


def draw():
    pyxel.cls(1)
    if state["tela"] == "titulo":
        pyxel.text(40, 50, "APERTE ENTER", 10)
        pyxel.text(28, 64, "e conte espacos em 5s", 7)
    elif state["tela"] == "jogo":
        pyxel.text(4, 4, f"pontos: {state['pontos']}", 7)
        pyxel.text(4, 14, f"tempo: {state['tempo'] // 30 + 1}", 13)
        pyxel.text(44, 60, "ESPACO, ESPACO!", 9)
    else:
        pyxel.text(52, 46, "FIM DE JOGO", 8)
        pyxel.text(46, 60, f"voce fez {state['pontos']}", 7)
        pyxel.text(34, 80, "ENTER volta ao titulo", 13)


pyxel.init(LARGURA, ALTURA, title="Estados")
pyxel.run(update, draw)
