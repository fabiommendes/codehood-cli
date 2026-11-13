import pyxel
from window import window_fps, window_height, window_title, window_width


def update():
    # Fecha a janela com a tecla Q.
    if pyxel.btnp(pyxel.KEY_Q):
        pyxel.quit()


def draw():
    pyxel.cls(1)
    pyxel.text(8, 8, "Ola, Pyxel!", 7)


pyxel.init(window_width(), window_height(), title=window_title(), fps=window_fps())
pyxel.run(update, draw)
