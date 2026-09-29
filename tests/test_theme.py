"""
Tests for `codehood.theme`: the Textual themes and the ANSI-based Rich theme.
"""

from __future__ import annotations

import asyncio
import re

import pytest
from rich.color import ColorType

from codehood.cli.chill import ChillApp
from codehood.theme import CODEHOOD_DARK, CODEHOOD_LIGHT, role_style


def test_app_starts_on_forest_and_registers_both_themes():
    async def main() -> None:
        app = ChillApp()
        async with app.run_test():
            assert app.theme == "codehood-dark"
            assert app.current_theme is CODEHOOD_DARK
            app.theme = "codehood"
            assert app.current_theme is CODEHOOD_LIGHT

    asyncio.run(main())


@pytest.mark.parametrize("theme", [CODEHOOD_DARK, CODEHOOD_LIGHT])
def test_theme_colors_are_hex(theme):
    for value in (
        theme.primary,
        theme.secondary,
        theme.accent,
        theme.warning,
        theme.error,
        theme.success,
        theme.background,
        theme.surface,
        theme.panel,
        theme.foreground,
        *theme.variables.values(),
    ):
        assert re.fullmatch(r"#[0-9a-f]{6}", value)


ROLES = ["error", "success", "warning", "secondary", "primary", "accent", "info", "muted"]


@pytest.mark.parametrize("name", ROLES)
def test_rich_roles_use_the_16_ansi_colors(name):
    color = role_style(name).color
    assert color is not None
    assert color.type == ColorType.STANDARD
