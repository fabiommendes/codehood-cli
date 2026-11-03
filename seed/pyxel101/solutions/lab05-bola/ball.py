"""Física da bola quicando."""


def bounce_pos(pos: int, vel: int, r: int, size: int) -> int:
    """Devolve a nova posição em um eixo, encostada na borda 0 ou size - 1 se passaria dela."""
    new = pos + vel
    if new - r < 0:
        return r
    if new + r > size - 1:
        return size - 1 - r
    return new


def bounce_vel(pos: int, vel: int, r: int, size: int) -> int:
    """Devolve a nova velocidade em um eixo: troca de sinal se a bola passaria da borda."""
    new = pos + vel
    if new - r < 0 or new + r > size - 1:
        return -vel
    return vel
