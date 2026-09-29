"""
Codehood's visual identity for the terminal (see `docs/ui/identity.md`).

Textual apps use the hex-based themes below. Plain Rich output uses
`RICH_THEME`, which maps semantic roles onto the 16 ANSI colors so the user's
terminal palette decides the exact hues.
"""

from __future__ import annotations

from typing import ClassVar

from rich.style import Style
from rich.theme import Theme as RichTheme
from textual.app import App
from textual.theme import Theme

__all__ = [
    "CODEHOOD_DARK",
    "CODEHOOD_LIGHT",
    "RICH_THEME",
    "CodehoodApp",
    "role_style",
]

#: Forest: the default theme. Token names follow identity.md.
CODEHOOD_DARK = Theme(
    name="codehood-dark",
    dark=True,
    background="#0d211a",  # base-200
    surface="#15302a",  # base-100
    panel="#1f4034",  # base-300
    foreground="#e6f0ea",  # content
    primary="#4aa0ff",
    secondary="#ffc400",
    accent="#ff4d97",
    warning="#ff6f1a",
    error="#ff5c5c",
    success="#4cd08a",
    variables={
        "info": "#00d2e6",
        "text-muted": "#8fb3a4",
        "foreground-muted": "#8fb3a4",
    },
)

#: Cerrado: the light theme.
CODEHOOD_LIGHT = Theme(
    name="codehood",
    dark=False,
    background="#f7f3ea",  # base-200
    surface="#fffdf8",  # base-100
    panel="#e6dfd0",  # base-300
    foreground="#1f2a24",  # content
    primary="#1b4b9b",
    secondary="#f2b800",
    accent="#a8309a",
    warning="#e0731f",
    error="#b5452a",
    success="#337a27",
    variables={
        "info": "#2670c0",
        "text-muted": "#5f6862",
        "foreground-muted": "#5f6862",
    },
)

#: Semantic style names for Rich output, mapped to ANSI color names.
RICH_THEME = RichTheme(
    {
        "error": "red",
        "success": "green",
        "warning": "yellow",
        "secondary": "yellow",
        "primary": "blue",
        "accent": "magenta",
        "info": "cyan",
        "muted": "bright_black",
    }
)


def role_style(name: str) -> Style:
    """
    Return the ANSI-based Rich style for a semantic role such as `error`.

    Useful inside Textual, where `Text` styles are not looked up in a Rich theme.
    """
    return RICH_THEME.styles[name]


class CodehoodApp[ReturnType](App[ReturnType]):
    """Base app that registers the Codehood themes and starts on Forest."""

    THEMES: ClassVar[tuple[Theme, ...]] = (CODEHOOD_DARK, CODEHOOD_LIGHT)

    def __init__(self) -> None:
        super().__init__()
        for theme in self.THEMES:
            self.register_theme(theme)
        self.theme = CODEHOOD_DARK.name
