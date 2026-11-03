"""Posições e cores calculadas."""


def color_at(x: int, y: int) -> int:
    """Devolve a cor da paleta que cobre o pixel (x, y) em uma grade de 4 colunas de células 8x8."""
    column = x // 8
    row = y // 8
    return row * 4 + column


def center(screen: int, size: int) -> int:
    """Devolve a posição inicial de um objeto de tamanho `size` centralizado em `screen`."""
    return (screen - size) // 2


def mirror_x(x: int, w: int, screen_w: int) -> int:
    """Devolve o x do retângulo refletido horizontalmente."""
    return screen_w - w - x
