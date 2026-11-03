# Janela mínima do Pyxel: abre uma tela de 160x120 pixels e a mantém aberta.
import pyxel

# Cria a janela. Tem que ser a primeira chamada ao Pyxel.
pyxel.init(160, 120, title="Minha primeira janela")


def update():
    """Roda a cada quadro e cuida da lógica. Aqui não há nada para atualizar."""
    pass


def draw():
    """Roda a cada quadro, depois de update, e só desenha."""
    pyxel.cls(1)  # limpa a tela com a cor 1 (azul escuro)
    pyxel.text(40, 56, "Ola, Pyxel!", 7)  # texto branco


# Inicia o laço principal. Esc fecha a janela.
pyxel.run(update, draw)
