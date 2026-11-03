"""A nave do jogador e seus tiros."""

class Bullet:
    def __init__(self, x: int, y: int, speed: int = -4):
        self.x = x
        self.y = y
        self.speed = speed

    def update(self) -> None:
        """Move o tiro para cima."""
        self.y += self.speed

    def alive(self) -> bool:
        """O tiro ainda está na tela?"""
        return self.y >= 0


class Ship:
    def __init__(self, x: int, y: int, width: int = 8, height: int = 8, speed: int = 2):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = speed

    def move(self, direction: int, screen_w: int) -> None:
        """Anda para o lado sem sair da tela. direction vale -1, 0 ou 1."""
        self.x = max(0, min(self.x + direction * self.speed, screen_w - self.width))

    def shoot(self) -> Bullet:
        """Cria um tiro saindo do meio da nave."""
        return Bullet(self.x + self.width // 2, self.y)

    def rect(self) -> tuple[int, int, int, int]:
        """Retângulo (x, y, w, h) da nave."""
        return self.x, self.y, self.width, self.height


def cleanup(bullets: list[Bullet]) -> list[Bullet]:
    """Lista nova só com os tiros vivos."""
    return [bullet for bullet in bullets if bullet.alive()]
