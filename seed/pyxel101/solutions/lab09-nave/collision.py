"""Colisão entre retângulos (x, y, w, h)."""

Rect = tuple[int, int, int, int]


def overlaps(a: Rect, b: Rect) -> bool:
    """Os retângulos têm área em comum?"""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def point_in_rect(px: int, py: int, rect: Rect) -> bool:
    """O ponto está dentro do retângulo?"""
    x, y, w, h = rect
    return x <= px < x + w and y <= py < y + h


def first_hit(rect: Rect, others: list[Rect]) -> int | None:
    """Índice do primeiro retângulo atingido, ou None."""
    for index, other in enumerate(others):
        if overlaps(rect, other):
            return index
    return None
