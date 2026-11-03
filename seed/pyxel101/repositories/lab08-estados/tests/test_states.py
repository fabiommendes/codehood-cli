from states import advance, new_state


def test_new_state():
    assert new_state() == {"screen": "title", "score": 0, "lives": 3}


def test_title_waits_for_start():
    state = new_state()
    assert advance(state, False, 0, False) == state


def test_start_goes_to_game():
    assert advance(new_state(), True, 0, False)["screen"] == "game"


def test_game_scores_and_loses_lives():
    state = {"screen": "game", "score": 5, "lives": 3}
    assert advance(state, False, 2, False) == {"screen": "game", "score": 7, "lives": 3}
    assert advance(state, False, 0, True) == {"screen": "game", "score": 5, "lives": 2}


def test_last_life_goes_to_over():
    state = {"screen": "game", "score": 9, "lives": 1}
    assert advance(state, False, 0, True) == {"screen": "over", "score": 9, "lives": 0}


def test_over_returns_to_title_keeping_score():
    state = {"screen": "over", "score": 9, "lives": 0}
    assert advance(state, True, 0, False)["screen"] == "title"
    assert advance(state, True, 0, False)["score"] == 9
    assert advance(state, False, 0, False) == state


def test_input_state_is_not_mutated():
    state = {"screen": "game", "score": 5, "lives": 3}
    advance(state, False, 2, True)
    assert state == {"screen": "game", "score": 5, "lives": 3}
