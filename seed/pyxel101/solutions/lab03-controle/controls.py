"""Movimento por teclado limitado à tela."""


def clamp(value: int, low: int, high: int) -> int:
    """Limita `value` ao intervalo [low, high]."""
    return max(low, min(value, high))


def direction(negative: bool, positive: bool) -> int:
    """Converte duas teclas opostas em -1, 0 ou 1."""
    return int(positive) - int(negative)


def next_x(x: int, dx: int, size: int, screen_w: int, speed: int = 2) -> int:
    """Soma `dx * speed` a `x` sem deixar o quadrado sair da tela."""
    return clamp(x + dx * speed, 0, screen_w - size)
