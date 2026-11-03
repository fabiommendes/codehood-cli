"""
Gera os assets dos repositorios `lab11-plataforma` e `projeto-final`.

Escreve os PNG com a biblioteca padrao (zlib e struct). Se o Pyxel estiver
instalado, tambem gera `plataforma.pyxres` a partir da folha de sprites:

    uv run --with pyxel python cli/seed/tools/make_lab_assets.py
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "pyxel101" / "repositories"

# Paleta padrao do Pyxel, indexada de 0 a 15.
PALETTE = [
    0x000000, 0x2B335F, 0x7E2072, 0x19959C, 0x8B4852, 0x395C98, 0xA9C1FF, 0xEEEEEE,
    0xD4186C, 0xD38441, 0xE9C35B, 0x70C6A9, 0x7696DE, 0xA3A3A3, 0xFF9798, 0xEDC7B0,
]  # fmt: skip

GROUND = ["bbbbbbbb", "bbbbbbbb", "49494949", "94949494", "44444444", "49494949", "94949494", "44444444"]
PLAYER = ["..6666..", "..6776..", "..6666..", ".555555.", "5.5555.5", "..5555..", "..5..5..", ".55..55."]
COIN = ["..aaaa..", ".aa99aa.", "aa9aa9aa", "aa9aa9aa", "aa9aa9aa", "aa9aa9aa", ".aa99aa.", "..aaaa.."]
ENEMY = ["..8888..", ".888888.", "88788788", "88888888", "88888888", "8.8888.8", "8......8", ".8....8."]
DRAFT = ["33333333", "3......3", "3.3333.3", "3.3..3.3", "3.3..3.3", "3.3333.3", "3......3", "33333333"]


def png(width: int, height: int, rows: list[list[int]]) -> bytes:
    """Codifica uma imagem de indices da paleta como PNG RGB."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = bytearray()
    for row in rows:
        raw.append(0)
        for index in row:
            raw += PALETTE[index].to_bytes(3, "big")
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def sheet(tiles: dict[tuple[int, int], list[str]], cols: int = 4, rows: int = 2) -> bytes:
    """Monta uma folha de sprites 8x8 com os tiles nas posicoes dadas."""
    grid = [[0] * (cols * 8) for _ in range(rows * 8)]
    for (tx, ty), art in tiles.items():
        for y, line in enumerate(art):
            for x, ch in enumerate(line):
                grid[ty * 8 + y][tx * 8 + x] = 0 if ch == "." else int(ch, 16)
    return png(cols * 8, rows * 8, grid)


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print("escrito", path.relative_to(ROOT.parent.parent.parent))


def make_pyxres(sprites: Path, target: Path) -> None:
    """Cria o `.pyxres` com a folha no banco 0 e um tilemap de chao e plataforma."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pyxel

    pyxel.init(128, 128, title="assets", headless=True)
    pyxel.images[0].load(0, 0, str(sprites))
    tilemap = pyxel.tilemaps[0]
    for tx in range(16):
        tilemap.pset(tx, 15, (1, 0))
    for tx in range(5, 9):
        tilemap.pset(tx, 11, (1, 0))
    pyxel.save(str(target))
    print("escrito", target.relative_to(ROOT.parent.parent.parent))


def main() -> None:
    tiles = {(1, 0): GROUND, (2, 0): PLAYER, (3, 0): COIN, (0, 1): ENEMY}
    lab = ROOT / "lab11-plataforma" / "assets"
    write(lab / "sprites.png", sheet(tiles))
    write(lab / "rascunho.png", sheet({(0, 0): DRAFT}))
    write(ROOT / "projeto-final" / "assets" / "sprites.png", sheet(tiles))
    try:
        make_pyxres(lab / "sprites.png", lab / "plataforma.pyxres")
    except ImportError:
        print("pyxel nao instalado: .pyxres nao gerado")


if __name__ == "__main__":
    main()
