"""Máquina de estados do jogo em um dicionário."""


def new_state() -> dict:
    """Estado inicial: tela de título."""
    return {"screen": "title", "score": 0, "lives": 3}


def advance(state: dict, start: bool, points: int, hit: bool) -> dict:
    """Estado do próximo quadro. Não altera `state`."""
    new = dict(state)
    if state["screen"] == "title" and start:
        new = {"screen": "game", "score": 0, "lives": 3}
    elif state["screen"] == "game":
        new["score"] += points
        if hit:
            new["lives"] -= 1
        if new["lives"] <= 0:
            new["screen"] = "over"
    elif state["screen"] == "over" and start:
        new["screen"] = "title"
    return new
