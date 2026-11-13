# Carrega personagem.pyxres e anda sobre um tilemap, com gravidade e câmera.
import os

import pyxel

TILE = 8
MAP_WIDTH = 32  # em tiles
SOLID_TILES = {(1, 0), (2, 0)}  # chão e tijolo, na folha de sprites
COIN_TILE = (3, 0)
EMPTY_TILE = (0, 0)

GRAVITY = 0.4
JUMP = -4.2
SPEED = 1.5

pyxel.init(128, 128, title="Plataforma")
pyxel.load(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "personagem.pyxres")
)

player = {"x": 16.0, "y": 80.0, "vy": 0.0, "on_ground": False, "facing": 1}
score = 0


def tile_at(px, py):
    """Devolve o tile (coluna, linha na folha) que cobre o pixel (px, py) do mundo."""
    return pyxel.tilemaps[0].pget(int(px) // TILE, int(py) // TILE)


def is_solid(px, py):
    return tile_at(px, py) in SOLID_TILES


def box_hits_wall(x, y):
    """Testa os quatro cantos da caixa 8x8 do personagem contra tiles sólidos."""
    corners = [(x, y), (x + 7, y), (x, y + 7), (x + 7, y + 7)]
    return any(is_solid(cx, cy) for cx, cy in corners)


def update():
    global score
    dx = 0.0
    if pyxel.btn(pyxel.KEY_LEFT):
        dx = -SPEED
        player["facing"] = -1
    if pyxel.btn(pyxel.KEY_RIGHT):
        dx = SPEED
        player["facing"] = 1

    if not box_hits_wall(player["x"] + dx, player["y"]):
        player["x"] += dx
    player["x"] = max(0, min(MAP_WIDTH * TILE - TILE, player["x"]))

    if pyxel.btnp(pyxel.KEY_SPACE) and player["on_ground"]:
        player["vy"] = JUMP

    player["vy"] += GRAVITY
    new_y = player["y"] + player["vy"]
    if box_hits_wall(player["x"], new_y):
        player["on_ground"] = player["vy"] > 0
        player["vy"] = 0.0
    else:
        player["y"] = new_y
        player["on_ground"] = False

    # Pega a moeda que estiver no centro do personagem.
    cx = int(player["x"] + 4) // TILE
    cy = int(player["y"] + 4) // TILE
    if pyxel.tilemaps[0].pget(cx, cy) == COIN_TILE:
        pyxel.tilemaps[0].pset(cx, cy, EMPTY_TILE)
        score += 1


def draw():
    pyxel.cls(12)
    camera_x = max(0, min(MAP_WIDTH * TILE - 128, int(player["x"]) - 64))
    pyxel.bltm(0, 0, 0, camera_x, 0, 128, 128, 0)
    # Personagem: tile (0, 1) da folha, espelhado quando olha para a esquerda.
    pyxel.blt(
        int(player["x"]) - camera_x,
        int(player["y"]),
        0,
        0,
        8,
        TILE * player["facing"],
        TILE,
        0,
    )
    pyxel.text(4, 4, f"moedas: {score}", 7)


pyxel.run(update, draw)
