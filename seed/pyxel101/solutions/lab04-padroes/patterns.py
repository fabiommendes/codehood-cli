"""Padrões que o main.py desenha com laços aninhados."""


def is_dark(col: int, row: int) -> bool:
    """Diz se a casa (col, row) do tabuleiro de xadrez é escura."""
    return (col + row) % 2 == 1


def stair_line(n: int) -> str:
    """Devolve a linha de `n` símbolos '#' de uma escada."""
    return "#" * n


def grid_pos(index: int, step: int, margin: int = 0) -> int:
    """Devolve a posição do ponto de índice `index` em uma grade."""
    return margin + index * step
