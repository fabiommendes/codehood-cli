"""Física do personagem em um tilemap."""

TILE = 8
GRAVITY = 1
MAX_FALL = 4
JUMP_SPEED = -6


def collides(x: int, y: int, is_solid) -> bool:
    """O quadrado 8x8 em (x, y) toca um tile sólido?"""
    corners = [
        (x, y),
        (x + TILE - 1, y),
        (x, y + TILE - 1),
        (x + TILE - 1, y + TILE - 1),
    ]
    return any(is_solid(cx // TILE, cy // TILE) for cx, cy in corners)


def jump(vy: int, on_ground: bool) -> int:
    """Velocidade vertical depois de apertar o pulo."""
    return JUMP_SPEED if on_ground else vy


def step(x: int, y: int, vx: int, vy: int, is_solid) -> tuple[int, int, int, bool]:
    """Um quadro de física. Devolve (x, y, vy, on_ground)."""
    if not collides(x + vx, y, is_solid):
        x += vx
    vy = min(vy + GRAVITY, MAX_FALL)
    on_ground = False
    if not collides(x, y + vy, is_solid):
        y += vy
    elif vy > 0:
        y = (y + vy + TILE - 1) // TILE * TILE - TILE
        vy = 0
        on_ground = True
    else:
        y = (y + vy) // TILE * TILE + TILE
        vy = 0
    return x, y, vy, on_ground
