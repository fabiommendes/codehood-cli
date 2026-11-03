# Efeito sonoro ao apertar uma tecla.
import pyxel

pyxel.init(160, 120, title="Som")

# Sound.set(notas, timbres, volumes, efeitos, velocidade).
# Timbre "p" é pulso (onda de pulso estreita), efeito "f" faz o volume cair aos poucos.
pyxel.sounds[0].set("c3e3g3c4", "p", "7", "f", 6)  # moeda
pyxel.sounds[1].set("c2c1", "n", "7", "f", 12)  # batida (ruído)

ultimo = "nenhum"


def update():
    global ultimo
    if pyxel.btnp(pyxel.KEY_SPACE):
        pyxel.play(0, 0)  # canal 0, som 0
        ultimo = "moeda"
    if pyxel.btnp(pyxel.KEY_X):
        pyxel.play(1, 1)  # em outro canal, para os sons se misturarem
        ultimo = "batida"


def draw():
    pyxel.cls(1)
    pyxel.text(4, 4, "ESPACO: moeda   X: batida", 7)
    pyxel.text(4, 60, f"ultimo som: {ultimo}", 10)


pyxel.run(update, draw)
