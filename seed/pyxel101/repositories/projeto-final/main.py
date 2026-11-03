import pyxel

from game.state import OVER, PLAYING, TITLE, Game

game = Game()
pyxel.init(game.width, game.height, title="Meu jogo")
pyxel.images[0].load(0, 0, "assets/sprites.png")


def update():
    if game.screen == TITLE and pyxel.btnp(pyxel.KEY_RETURN):
        game.start()
    elif game.screen == PLAYING:
        dx = int(pyxel.btn(pyxel.KEY_RIGHT)) - int(pyxel.btn(pyxel.KEY_LEFT))
        game.player.move(dx, 0, game.width, game.height)
        game.update()
    elif game.screen == OVER and pyxel.btnp(pyxel.KEY_RETURN):
        game.screen = TITLE


def draw():
    pyxel.cls(1)
    if game.screen == TITLE:
        pyxel.text(52, 56, "ENTER para jogar", 7)
    elif game.screen == PLAYING:
        pyxel.blt(game.player.x, game.player.y, 0, 16, 0, 8, 8, 0)
        for enemy in game.enemies:
            pyxel.blt(enemy.x, enemy.y, 0, 0, 8, 8, 8, 0)
        pyxel.text(4, 4, f"Pontos {game.score}", 7)
    else:
        pyxel.text(60, 56, "FIM DE JOGO", 8)


pyxel.run(update, draw)
