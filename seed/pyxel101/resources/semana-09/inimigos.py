# Uma lista de objetos Enemy: cada objeto tem o seu próprio estado.
import pyxel

LARGURA = 160
ALTURA = 120


class Enemy:
    """Inimigo que desce a tela e balança de um lado para o outro."""

    def __init__(self, x, y, speed):
        self.x = x
        self.y = y
        self.speed = speed
        self.direction = 1

    def update(self):
        self.y += self.speed
        self.x += self.direction * 0.5
        if self.x < 6 or self.x > LARGURA - 6:
            self.direction = -self.direction

    def is_off_screen(self):
        return self.y > ALTURA + 8

    def draw(self):
        pyxel.circ(self.x, self.y, 5, 8)
        pyxel.pset(self.x - 2, self.y - 1, 7)
        pyxel.pset(self.x + 2, self.y - 1, 7)


enemies = []


def update():
    if pyxel.frame_count % 20 == 0:
        enemies.append(Enemy(pyxel.rndi(10, LARGURA - 10), -4, pyxel.rndf(0.5, 1.5)))
    for enemy in enemies:
        enemy.update()
    enemies[:] = [e for e in enemies if not e.is_off_screen()]


def draw():
    pyxel.cls(1)
    for enemy in enemies:
        enemy.draw()
    pyxel.text(4, 4, f"inimigos: {len(enemies)}", 7)


pyxel.init(LARGURA, ALTURA, title="Inimigos")
pyxel.run(update, draw)
