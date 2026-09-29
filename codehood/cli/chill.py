"""
`codehood chill`: does nothing useful -- just mounts the mascot and lets it
blink and hop until you quit.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ..theme import CodehoodApp
from ..widgets.mascot import Mascot
from .base import app

__all__ = ["chill"]


@app.command()
def chill() -> None:
    """
    Chill for a bit.
    """
    ChillApp().run()


class ChillApp(CodehoodApp[None]):
    """Full-screen mascot with a "Chilling..." caption. Press q to quit."""

    BINDINGS = [("q", "quit", "Quit")]
    TITLE = "codehood chill"

    DEFAULT_CSS = """
    Screen {
        align: center middle;
    }
    #chill {
        width: auto;
        height: auto;
        align: center middle;
    }
    #caption {
        margin-top: 1;
        width: auto;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="chill"):
            yield Mascot(id="mascot")
            yield Static("Chilling...", id="caption")
