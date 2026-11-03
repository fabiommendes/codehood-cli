# A classe Player: atributos no __init__ e comportamento em métodos.
import pyxel

LARGURA = 160
ALTURA = 120


class Player:
    """Nave do jogador, um triângulo que anda na horizontal e atira."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 2
        self.shots = []  # cada tiro é um par [x, y]

    def update(self):
        if pyxel.btn(pyxel.KEY_LEFT):
            self.x -= self.speed
        if pyxel.btn(pyxel.KEY_RIGHT):
            self.x += self.speed
        self.x = max(4, min(LARGURA - 4, self.x))

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.shoot()
        for shot in self.shots:
            shot[1] -= 4
        self.shots = [s for s in self.shots if s[1] > 0]

    def shoot(self):
        self.shots.append([self.x, self.y - 6])

    def draw(self):
        pyxel.tri(self.x, self.y - 5, self.x - 4, self.y + 4, self.x + 4, self.y + 4, 11)
        for x, y in self.shots:
            pyxel.rect(x, y, 1, 4, 10)


player = Player(LARGURA // 2, ALTURA - 10)


def update():
    player.update()


def draw():
    pyxel.cls(0)
    player.draw()
    pyxel.text(4, 4, f"tiros: {len(player.shots)}", 7)


pyxel.init(LARGURA, ALTURA, title="Nave")
pyxel.run(update, draw)
