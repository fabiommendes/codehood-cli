# Melodia em dois canais: um para a melodia e outro para o baixo.
import pyxel

pyxel.init(160, 120, title="Musica")

# Melodia no som 0, baixo no som 1.
pyxel.sounds[0].set(
    "e3e3g3a3 g3e3d3c3 d3d3e3g3 e3d3d3r",
    "s",
    "6",
    "nnnf",
    20,
)
pyxel.sounds[1].set("c2r g1r c2r g1r", "t", "5", "n", 20)

# Cada lista é a sequência de sons de um canal.
pyxel.musics[0].set([0], [1])

tocando = False


def update():
    global tocando
    if pyxel.btnp(pyxel.KEY_SPACE):
        if tocando:
            pyxel.stop()
        else:
            pyxel.playm(0, loop=True)
        tocando = not tocando


def draw():
    pyxel.cls(0)
    pyxel.text(4, 4, "ESPACO liga e desliga", 7)
    estado = "tocando" if tocando else "parado"
    pyxel.text(4, 56, estado, 11 if tocando else 13)
    if tocando:
        # Barrinhas que pulam no ritmo, só enfeite.
        for i in range(8):
            altura = 4 + (pyxel.frame_count // 3 + i * 5) % 20
            pyxel.rect(30 + i * 12, 110 - altura, 8, altura, 9 + i % 4)


pyxel.run(update, draw)
