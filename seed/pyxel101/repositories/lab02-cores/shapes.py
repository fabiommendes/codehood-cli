"""Posições e cores calculadas."""


def color_at(x: int, y: int) -> int:
    """Devolve a cor da paleta que cobre o pixel (x, y) em uma grade de 4 colunas de células 8x8."""
    # TODO: use // para achar a coluna e a linha da célula, e depois
    # a fórmula linha * 4 + coluna.
    raise NotImplementedError


def center(screen: int, size: int) -> int:
    """Devolve a posição inicial de um objeto de tamanho `size` centralizado em `screen`."""
    # TODO: use divisão inteira.
    raise NotImplementedError


def mirror_x(x: int, w: int, screen_w: int) -> int:
    """Devolve o x do retângulo refletido horizontalmente."""
    # TODO
    raise NotImplementedError
