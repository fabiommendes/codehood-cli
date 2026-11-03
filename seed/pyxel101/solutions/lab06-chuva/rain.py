"""Gotas de chuva em uma lista."""


def make_drop(x: int, speed: int) -> list[int]:
    """Cria uma gota `[x, y, speed]` no topo da tela."""
    return [x, 0, speed]


def fall(drops: list[list[int]], height: int) -> list[list[int]]:
    """Faz as gotas caírem e descarta as que passaram do chão."""
    result = []
    for x, y, speed in drops:
        if y + speed < height:
            result.append([x, y + speed, speed])
    return result


def lowest_drop(drops: list[list[int]]) -> list[int] | None:
    """A gota mais perto do chão, ou None."""
    lowest = None
    for drop in drops:
        if lowest is None or drop[1] > lowest[1]:
            lowest = drop
    return lowest
