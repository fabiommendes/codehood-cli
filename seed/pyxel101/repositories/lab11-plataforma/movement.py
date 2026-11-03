"""Física do personagem em um tilemap."""

TILE = 8
GRAVITY = 1
MAX_FALL = 4
JUMP_SPEED = -6


def collides(x: int, y: int, is_solid) -> bool:
    """O quadrado 8x8 em (x, y) toca um tile sólido?"""
    # TODO
    raise NotImplementedError


def jump(vy: int, on_ground: bool) -> int:
    """Velocidade vertical depois de apertar o pulo."""
    # TODO
    raise NotImplementedError


def step(x: int, y: int, vx: int, vy: int, is_solid) -> tuple[int, int, int, bool]:
    """Um quadro de física. Devolve (x, y, vy, on_ground)."""
    # TODO
    raise NotImplementedError
