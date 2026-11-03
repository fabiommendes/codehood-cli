"""Entidades do jogo."""


class Player:
    def __init__(self, x: int, y: int, speed: int = 2):
        self.x = x
        self.y = y
        self.speed = speed
        self.lives = 3

    def move(self, dx: int, dy: int, width: int, height: int, size: int = 8) -> None:
        """Move o jogador sem sair da tela."""
        self.x = max(0, min(self.x + dx * self.speed, width - size))
        self.y = max(0, min(self.y + dy * self.speed, height - size))


class Enemy:
    def __init__(self, x: int, y: int, speed: int = 1):
        self.x = x
        self.y = y
        self.speed = speed

    def update(self) -> None:
        """Desce uma posição por quadro."""
        self.y += self.speed
