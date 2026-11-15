from __future__ import annotations

from pathlib import Path

from . import _layout

__all__ = ["config_path", "set_config_override"]

#: The file `--config` / `CODEHOOD_CONFIG` points at, set once per invocation
#: by the app callback.
config_override: Path | None = None


def set_config_override(path: Path | None) -> None:
    """
    Make `config_path` return `path` instead of `<root>/codehood.toml`, or restore the default with `None`.
    """
    global config_override
    config_override = path


def config_path(root: Path) -> Path:
    """
    The config file to read for the repository at `root`: the override when set, else `root/codehood.toml`.
    """
    if config_override is not None:
        return config_override
    return root / _layout.CONFIG_FILE
