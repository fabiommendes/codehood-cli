from game.state import PLAYING, TITLE, Game


def test_game_starts_on_the_title_screen():
    assert Game().screen == TITLE


def test_start_begins_a_match():
    game = Game()
    game.start()
    assert game.screen == PLAYING
    assert game.score == 0


def test_player_stays_inside_the_screen():
    game = Game()
    for _ in range(200):
        game.player.move(1, 0, game.width, game.height)
    assert game.player.x == game.width - 8
