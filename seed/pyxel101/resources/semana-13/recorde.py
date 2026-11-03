# Lê e grava o recorde em recorde.json, ao lado do script.
import json
import os

import pyxel

CAMINHO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorde.json")


def le_recorde():
    """Devolve o recorde salvo, ou 0 se o arquivo não existir ou estiver quebrado."""
    try:
        with open(CAMINHO, encoding="utf-8") as arquivo:
            return json.load(arquivo)["recorde"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 0


def grava_recorde(valor):
    with open(CAMINHO, "w", encoding="utf-8") as arquivo:
        json.dump({"recorde": valor}, arquivo)


recorde = le_recorde()
pontos = 0


def update():
    global pontos, recorde
    if pyxel.btnp(pyxel.KEY_SPACE):
        pontos += 1
        if pontos > recorde:
            recorde = pontos
            grava_recorde(recorde)
    if pyxel.btnp(pyxel.KEY_R):
        pontos = 0


def draw():
    pyxel.cls(1)
    pyxel.text(4, 4, "ESPACO soma, R zera", 7)
    pyxel.text(4, 50, f"pontos:  {pontos}", 7)
    pyxel.text(4, 62, f"recorde: {recorde}", 10)


pyxel.init(160, 120, title="Recorde")
pyxel.run(update, draw)
