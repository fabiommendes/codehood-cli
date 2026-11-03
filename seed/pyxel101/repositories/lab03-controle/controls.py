"""Movimento por teclado limitado à tela."""


def clamp(value: int, low: int, high: int) -> int:
    """Limita `value` ao intervalo [low, high]."""
    # TODO: use min e max, ou if/elif.
    raise NotImplementedError


def direction(negative: bool, positive: bool) -> int:
    """Converte duas teclas opostas em -1, 0 ou 1."""
    # TODO: se as duas estiverem apertadas, elas se anulam.
    raise NotImplementedError


def next_x(x: int, dx: int, size: int, screen_w: int, speed: int = 2) -> int:
    """Soma `dx * speed` a `x` sem deixar o quadrado sair da tela."""
    # TODO: o maior x possível é screen_w - size.
    raise NotImplementedError
