"""Colisão entre retângulos (x, y, w, h)."""

Rect = tuple[int, int, int, int]


def overlaps(a: Rect, b: Rect) -> bool:
    """Os retângulos têm área em comum?"""
    # TODO
    raise NotImplementedError


def point_in_rect(px: int, py: int, rect: Rect) -> bool:
    """O ponto está dentro do retângulo?"""
    # TODO
    raise NotImplementedError


def first_hit(rect: Rect, others: list[Rect]) -> int | None:
    """Índice do primeiro retângulo atingido, ou None."""
    # TODO
    raise NotImplementedError
