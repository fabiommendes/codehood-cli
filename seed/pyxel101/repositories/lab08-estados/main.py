import pyxel

from states import advance, new_state

pyxel.init(160, 120, title="Estados")
state = new_state()


def update():
    global state
    start = pyxel.btnp(pyxel.KEY_RETURN)
    points = 1 if pyxel.btnp(pyxel.KEY_SPACE) else 0
    hit = pyxel.btnp(pyxel.KEY_H)
    state = advance(state, start, points, hit)


def draw():
    pyxel.cls(0)
    screen = state["screen"]
    if screen == "title":
        pyxel.text(50, 56, "ENTER para jogar", 7)
    elif screen == "game":
        pyxel.text(4, 4, f"Pontos {state['score']}  Vidas {state['lives']}", 7)
    else:
        pyxel.text(60, 56, "FIM DE JOGO", 8)


pyxel.run(update, draw)
