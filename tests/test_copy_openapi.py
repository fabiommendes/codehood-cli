"""
Tests for `scripts/copy-openapi.py`, the three-source search for the server's
OpenAPI document.

Every test points `LOCAL_SERVER_URL` at a closed port, so the suite never
depends on whether a dev server happens to be running, and stubs `pnpm` with
a shell script, so it never runs the real generator or writes into a sibling
checkout.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

_ROOT = Path(__file__).parent.parent
REAL_SPEC_PATH = _ROOT / "resources" / "openapi" / "codehood.json"

#: Port 9 is discard; nothing listens, so `httpx` fails fast rather than
#: reaching a real server on some developer's machine.
DEAD_URL = "http://localhost:9/openapi.json"

runner = CliRunner()


def _load_script():
    """
    Import `scripts/copy-openapi.py`, whose hyphenated name is not an
    importable module path.
    """
    spec = importlib.util.spec_from_file_location(
        "copy_openapi", _ROOT / "scripts" / "copy-openapi.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(monkeypatch):
    module = _load_script()
    monkeypatch.setattr(module, "LOCAL_SERVER_URL", DEAD_URL)
    monkeypatch.setattr(module, "SIBLING_REPOS", ())
    return module


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A sibling checkout with the generator."""
    repo = tmp_path / "codehood-server"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "generate-openapi.ts").write_text("// stub\n")
    return repo


@pytest.fixture
def fake_pnpm(tmp_path: Path, monkeypatch):
    """
    Put a `pnpm` on `PATH` whose body each test writes.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}:{Path('/usr/bin')}:{Path('/bin')}")

    def install(body: str) -> None:
        executable = bin_dir / "pnpm"
        executable.write_text(body)
        executable.chmod(0o755)

    return install


def _invoke(script, tmp_path: Path, env: dict[str, str] | None = None):
    output = tmp_path / "out.json"
    result = runner.invoke(script.app, [str(output)], env=env or {})
    return result, output


def _is_the_real_spec(path: Path) -> bool:
    return path.is_file() and path.read_bytes() == REAL_SPEC_PATH.read_bytes()


#
# 1. $CODEHOOD_OPENAPI_JSON
#
def test_env_var_file_path_is_used(script, tmp_path):
    result, output = _invoke(
        script, tmp_path, {"CODEHOOD_OPENAPI_JSON": str(REAL_SPEC_PATH)}
    )
    assert result.exit_code == 0
    assert _is_the_real_spec(output)


def test_env_var_pointing_nowhere_is_fatal(script, tmp_path, fake_repo):
    """
    An explicit override that quietly fell through to another source would
    hide the human's mistake, so a bad `$CODEHOOD_OPENAPI_JSON` stops the
    run even though the generator below it would have worked.
    """
    script.SIBLING_REPOS = (fake_repo,)
    result, output = _invoke(
        script, tmp_path, {"CODEHOOD_OPENAPI_JSON": "/nope/missing.json"}
    )
    assert result.exit_code == 1
    assert not output.exists()


def test_env_var_pointing_at_non_json_is_fatal(script, tmp_path):
    junk = tmp_path / "junk.json"
    junk.write_text("<html>404</html>")
    result, output = _invoke(script, tmp_path, {"CODEHOOD_OPENAPI_JSON": str(junk)})
    assert result.exit_code == 1
    assert not output.exists()


def test_env_var_pointing_at_json_that_is_not_a_spec_is_fatal(script, tmp_path):
    not_a_spec = tmp_path / "other.json"
    not_a_spec.write_text('{"hello": "world"}')
    result, output = _invoke(
        script, tmp_path, {"CODEHOOD_OPENAPI_JSON": str(not_a_spec)}
    )
    assert result.exit_code == 1
    assert not output.exists()


#
# 3. The generator in a sibling checkout
#
def test_generator_writes_to_the_path_it_is_given(
    script, tmp_path, fake_repo, fake_pnpm
):
    """`pnpm exec tsx scripts/generate-openapi.ts <target>`: target is `$4`."""
    fake_pnpm(f'#!/bin/sh\ncp "{REAL_SPEC_PATH}" "$4"\n')
    script.SIBLING_REPOS = (fake_repo,)
    result, output = _invoke(script, tmp_path)
    assert result.exit_code == 0
    assert _is_the_real_spec(output)


@pytest.mark.parametrize(
    "pnpm_body",
    [
        # Exits non-zero.
        "#!/bin/sh\necho boom >&2\nexit 1\n",
        # Succeeds but writes nothing.
        "#!/bin/sh\nexit 0\n",
        # Succeeds but writes something that isn't a document.
        "#!/bin/sh\necho '<html>' > \"$4\"\n",
    ],
)
def test_a_broken_generator_never_writes_output(
    script, tmp_path, fake_repo, fake_pnpm, pnpm_body
):
    """
    A failed refresh must leave the previous snapshot alone. Half-writing a
    good file with an error page is worse than not refreshing at all.
    """
    fake_pnpm(pnpm_body)
    script.SIBLING_REPOS = (fake_repo,)
    result, output = _invoke(script, tmp_path)
    assert result.exit_code == 1
    assert not output.exists()


#
# Output formatting
#
def test_generator_runs_in_dev_environment(script, tmp_path, fake_repo, fake_pnpm):
    fake_pnpm(
        '#!/bin/sh\n[ "$ENVIRONMENT" = dev ] || exit 1\n'
        f'cp "{REAL_SPEC_PATH}" "$4"\n'
    )
    script.SIBLING_REPOS = (fake_repo,)
    result, output = _invoke(script, tmp_path)
    assert result.exit_code == 0
    assert _is_the_real_spec(output)


def test_output_is_byte_identical_to_what_the_server_writes(script, tmp_path):
    """
    Two-space indent, non-ASCII unescaped, trailing newline. Any source must
    produce the same bytes, or `git diff` on a refresh fills with noise that
    isn't a real spec change.
    """
    compact = tmp_path / "compact.json"
    compact.write_text(json.dumps(json.loads(REAL_SPEC_PATH.read_text())))
    result, output = _invoke(script, tmp_path, {"CODEHOOD_OPENAPI_JSON": str(compact)})
    assert result.exit_code == 0
    assert _is_the_real_spec(output)


def test_default_output_is_the_snapshot_the_generator_reads(script):
    assert script.DEFAULT_OUTPUT == REAL_SPEC_PATH


def test_nothing_found_exits_nonzero(script, tmp_path):
    result, output = _invoke(script, tmp_path)
    assert result.exit_code == 1
    assert not output.exists()
    assert "no OpenAPI document found" in result.output


def test_reports_whether_the_document_changed(script, tmp_path):
    output = tmp_path / "out.json"
    env: dict[str, Any] = {"CODEHOOD_OPENAPI_JSON": str(REAL_SPEC_PATH)}
    first = runner.invoke(script.app, [str(output)], env=env)
    second = runner.invoke(script.app, [str(output)], env=env)
    assert "(new)" in first.output
    assert "(unchanged)" in second.output
