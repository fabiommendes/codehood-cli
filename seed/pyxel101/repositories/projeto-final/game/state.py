"""Telas do jogo: título, jogo e fim."""

from game.entities import Enemy, Player

TITLE, PLAYING, OVER = "title", "playing", "over"


class Game:
    def __init__(self, width: int = 160, height: int = 120):
        self.width = width
        self.height = height
        self.screen = TITLE
        self.score = 0
        self.player = Player(width // 2, height - 16)
        self.enemies: list[Enemy] = []

    def start(self) -> None:
        """Começa uma partida nova."""
        self.screen = PLAYING
        self.score = 0
        self.player = Player(self.width // 2, self.height - 16)
        self.enemies = []

    def update(self) -> None:
        """Avança um quadro. Cada grupo desenvolve as regras a partir daqui."""
        if self.screen != PLAYING:
            return
        for enemy in self.enemies:
            enemy.update()
        # TODO: colisões, pontuação e condição de fim de jogo.
