"""
Guards against `codehood/api/generated.py` drifting from the OpenAPI snapshot.

The client is generated from `resources/openapi/codehood.json`. Editing either
without regenerating leaves the other stale, and nothing else notices.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from codehood.api.generate import Generator, format_source

_ROOT = Path(__file__).parent.parent
SNAPSHOT = _ROOT / "resources" / "openapi" / "codehood.json"
GENERATED = _ROOT / "codehood" / "api" / "generated.py"


def test_generated_client_matches_the_snapshot():
    spec = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    expected = format_source(Generator(spec).generate())
    actual = GENERATED.read_text(encoding="utf-8")
    if expected != actual:
        diff = difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            "codehood/api/generated.py (committed)",
            "regenerated from the snapshot",
            lineterm="",
            n=1,
        )
        shown = "\n".join(list(diff)[:40])
        raise AssertionError(
            "codehood/api/generated.py is out of date with "
            "resources/openapi/codehood.json. Run `pnpm run openapi:cli` in the "
            "server repository, or `uv run python -m codehood.api.generate "
            "resources/openapi/codehood.json` here.\n" + shown
        )
