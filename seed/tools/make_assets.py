"""Gera os PNG, PDF e .pyxres de cli/seed/pyxel101/resources/ (stdlib + Pillow + Pyxel).

Uso, a partir de cli/seed/: uv run --with pillow --with pyxel python tools/make_assets.py
"""

import os
import sys
import zlib  # noqa: F401  (o PDF é escrito sem compressão, para ficar legível)
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RES = Path(__file__).resolve().parent.parent / "pyxel101" / "resources"

PALETTE = [
    "000000", "2B335F", "7E2072", "19959C", "8B4852", "395C98", "A9C1FF", "EEEEEE",
    "D4186C", "D38441", "E9C35B", "70C6A9", "7696DE", "A3A3A3", "FF9798", "EDC7B0",
]  # fmt: skip


def rgb(i: int) -> tuple[int, int, int]:
    h = PALETTE[i]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def font(size: int = 8) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size)


def save_png(img: Image.Image, rel: str) -> None:
    img = img.convert("RGB").quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    img.save(RES / rel, optimize=True)


def centered(
    d: ImageDraw.ImageDraw, cx: float, cy: float, text: str, fill, size: int = 8
) -> None:
    d.text((cx, cy), text, fill=fill, font=font(size), anchor="mm")


def arrow(d: ImageDraw.ImageDraw, p0, p1, fill) -> None:
    d.line([p0, p1], fill=fill, width=1)
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    n = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / n, dy / n
    left = (x1 - 5 * ux + 3 * uy, y1 - 5 * uy - 3 * ux)
    right = (x1 - 5 * ux - 3 * uy, y1 - 5 * uy + 3 * ux)
    d.polygon([p1, left, right], fill=fill)


# ---------------------------------------------------------------- sprites

SPRITES = {
    "ground": [
        "bbbbbbbb", "3b3bb3b3", "49449494", "94944949",
        "49494494", "94949449", "49449494", "94494949",
    ],
    "brick": [
        "44444444", "99949999", "99949999", "44444444",
        "99999499", "99999499", "44444444", "99949999",
    ],
    "coin": [
        "...aa...", "..a77a..", ".a7aa9a.", ".a7aa9a.",
        ".a7aa9a.", ".a7aa9a.", "..a99a..", "...aa...",
    ],
    "player_idle": [
        "..2222..", ".222222.", ".f1ff1f.", ".ffffff.",
        "..5555..", ".555555.", "..5..5..", "..2..2..",
    ],
    "player_walk": [
        "..2222..", ".222222.", ".f1ff1f.", ".ffffff.",
        "..5555..", ".555555.", ".5....5.", ".2....2.",
    ],
    "slime": [
        "........", "..3333..", ".333333.", ".371371.",
        ".333333.", "33333333", "3b3bb3b3", "........",
    ],
    "bat": [
        "8......8", "88.22.88", "8822228.", ".822228.",
        "..2772..", "...22...", "........", "........",
    ],
    "ghost": [
        "..7777..", ".777777.", ".717717.", ".777777.",
        ".777777.", ".777777.", ".7.77.7.", "........",
    ],
    "alien": [
        ".b....b.", "..b..b..", ".bbbbbb.", "bb1bb1bb",
        "bbbbbbbb", ".b.bb.b.", "b......b", "........",
    ],
}  # fmt: skip


def sprite_pixels(name: str) -> list[list[int]]:
    return [[int(c, 16) if c != "." else 0 for c in row] for row in SPRITES[name]]


def draw_sprite(
    img: Image.Image, name: str, ox: int, oy: int, scale: int = 1, bg: int | None = None
) -> None:
    d = ImageDraw.Draw(img)
    for y, row in enumerate(sprite_pixels(name)):
        for x, c in enumerate(row):
            if c == 0 and bg is None:
                continue
            d.rectangle(
                [
                    ox + x * scale,
                    oy + y * scale,
                    ox + (x + 1) * scale - 1,
                    oy + (y + 1) * scale - 1,
                ],
                fill=rgb(bg if c == 0 and bg is not None else c),
            )


# Posição (coluna, linha), em tiles, de cada sprite na folha.
SHEET = {
    "ground": (1, 0), "brick": (2, 0), "coin": (3, 0),
    "player_idle": (0, 1), "player_walk": (1, 1),
    "slime": (0, 2), "bat": (1, 2), "ghost": (2, 2), "alien": (3, 2),
}  # fmt: skip


def sheet_image() -> Image.Image:
    img = Image.new("RGB", (64, 32), rgb(0))
    for name, (tx, ty) in SHEET.items():
        draw_sprite(img, name, tx * 8, ty * 8)
    return img


# ------------------------------------------------------------------ PNGs


def png_janela() -> None:
    img = Image.new("RGB", (160, 120), rgb(1))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 159, 119], outline=rgb(5))
    centered(d, 80, 60, "Olá, Pyxel!", rgb(7), 10)
    d.rectangle([0, 0, 159, 9], fill=rgb(5))
    d.text((3, 5), "Minha primeira janela", fill=rgb(7), font=font(7), anchor="lm")
    save_png(img, "semana-01/janela.png")


def png_repl() -> None:
    img = Image.new("RGB", (160, 120), (24, 24, 28))
    d = ImageDraw.Draw(img)
    lines = [
        ("Python 3.12.3", 13),
        ('Digite "help"', 13),
        (">>> 2 ** 10", 7),
        ("1024", 11),
        (">>> import pyxel", 7),
        (">>> pyxel.VERSION", 7),
        ("'2.9.9'", 11),
        (">>> type(3.0)", 7),
        ("<class 'float'>", 11),
        (">>> _", 10),
    ]
    for i, (text, col) in enumerate(lines):
        d.text((4, 6 + i * 11), text, fill=rgb(col), font=font(8))
    save_png(img, "semana-01/repl.png")


def png_paleta() -> None:
    img = Image.new("RGB", (160, 120), rgb(0))
    d = ImageDraw.Draw(img)
    for i in range(16):
        x, y = (i % 4) * 40, (i // 4) * 30
        d.rectangle([x, y, x + 39, y + 29], fill=rgb(i))
        col = rgb(7) if i in (0, 1, 2, 4, 5, 8) else rgb(0)
        centered(d, x + 20, y + 11, str(i), col, 11)
        centered(d, x + 20, y + 22, "#" + PALETTE[i].lower(), col, 7)
    save_png(img, "semana-02/paleta.png")


def png_fluxograma() -> None:
    img = Image.new("RGB", (160, 120), rgb(7))
    d = ImageDraw.Draw(img)
    ink = rgb(1)
    d.rounded_rectangle([50, 3, 110, 17], radius=7, outline=ink, fill=rgb(6))
    centered(d, 80, 10, "inicio", ink)
    arrow(d, (80, 17), (80, 27), ink)
    d.polygon([(80, 27), (118, 45), (80, 63), (42, 45)], outline=ink, fill=rgb(10))
    centered(d, 80, 45, "x > 0 ?", ink)
    arrow(d, (42, 45), (22, 45), ink)
    arrow(d, (118, 45), (138, 45), ink)
    centered(d, 30, 38, "sim", ink, 7)
    centered(d, 130, 38, "não", ink, 7)
    d.rectangle([2, 45 + 0, 22, 45], outline=None)
    d.rectangle([3, 50, 40, 68], outline=ink, fill=rgb(11))
    centered(d, 21, 59, "x = x - 1", ink, 7)
    d.rectangle([120, 50, 157, 68], outline=ink, fill=rgb(14))
    centered(d, 139, 59, "x = 0", ink, 7)
    arrow(d, (22, 68), (22, 68), ink)
    d.line([(21, 68), (21, 84), (80, 84)], fill=ink)
    d.line([(139, 68), (139, 84), (80, 84)], fill=ink)
    arrow(d, (80, 84), (80, 95), ink)
    d.rounded_rectangle([50, 95, 110, 111], radius=7, outline=ink, fill=rgb(6))
    centered(d, 80, 103, "desenha", ink)
    save_png(img, "semana-03/fluxograma-condicional.png")


def png_xadrez() -> None:
    img = Image.new("RGB", (160, 120), rgb(1))
    d = ImageDraw.Draw(img)
    cell = 13
    ox, oy = 4, 8
    for linha in range(8):
        for coluna in range(8):
            cor = 7 if (linha + coluna) % 2 == 0 else 5
            x, y = ox + coluna * cell, oy + linha * cell
            d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=rgb(cor))
    d.text((115, 20), "for linha:", fill=rgb(10), font=font(8))
    d.text((115, 32), " for coluna:", fill=rgb(10), font=font(8))
    d.text((115, 50), "(linha+coluna)", fill=rgb(7), font=font(7))
    d.text((115, 60), "% 2 == 0", fill=rgb(7), font=font(7))
    save_png(img, "semana-04/padrao-xadrez.png")


def png_ciclo() -> None:
    img = Image.new("RGB", (160, 120), rgb(7))
    d = ImageDraw.Draw(img)
    ink = rgb(1)
    d.rectangle([8, 14, 68, 50], outline=ink, fill=rgb(11))
    centered(d, 38, 26, "update()", ink, 9)
    centered(d, 38, 40, "lógica", ink, 7)
    d.rectangle([92, 14, 152, 50], outline=ink, fill=rgb(10))
    centered(d, 122, 26, "draw()", ink, 9)
    centered(d, 122, 40, "desenho", ink, 7)
    arrow(d, (68, 32), (92, 32), ink)
    d.line([(122, 50), (122, 78), (38, 78), (38, 56)], fill=ink)
    arrow(d, (38, 62), (38, 50), ink)
    centered(d, 80, 70, "30 vezes por segundo", ink, 8)
    centered(d, 80, 94, "pyxel.run(update, draw)", rgb(5), 9)
    save_png(img, "semana-05/ciclo-update-draw.png")


def png_inimigos() -> None:
    img = Image.new("RGB", (160, 120), rgb(1))
    d = ImageDraw.Draw(img)
    names = ["slime", "bat", "ghost", "alien"]
    for i, name in enumerate(names):
        draw_sprite(img, name, 4 + i * 39, 24, scale=4)
        centered(d, 4 + i * 39 + 16, 66, name, rgb(7), 8)
    centered(d, 80, 10, "inimigos = [slime, bat, ghost, alien]", rgb(10), 7)
    centered(d, 80, 90, "sprites de 8x8 pixels, ampliados 4x", rgb(13), 7)
    save_png(img, "semana-06/inimigos.png")


def png_estados() -> None:
    img = Image.new("RGB", (160, 120), rgb(7))
    d = ImageDraw.Draw(img)
    ink = rgb(1)
    boxes = {"titulo": (4, 36), "jogo": (62, 36), "fim": (118, 36)}
    for name, (x, y) in boxes.items():
        d.rounded_rectangle([x, y, x + 38, y + 24], radius=6, outline=ink, fill=rgb(6))
        centered(d, x + 19, y + 12, name, ink, 9)
    arrow(d, (42, 44), (62, 44), ink)
    centered(d, 52, 36, "ENTER", ink, 6)
    arrow(d, (100, 44), (118, 44), ink)
    centered(d, 109, 36, "tempo 0", ink, 6)
    d.line([(137, 60), (137, 90), (23, 90), (23, 66)], fill=ink)
    arrow(d, (23, 72), (23, 60), ink)
    centered(d, 80, 100, "ENTER", ink, 7)
    centered(d, 80, 12, 'state["tela"]', rgb(5), 9)
    save_png(img, "semana-08/maquina-de-estados.png")


def png_classes() -> None:
    img = Image.new("RGB", (160, 120), rgb(7))
    d = ImageDraw.Draw(img)
    ink = rgb(1)
    for x, title, attrs, meths in [
        (4, "Player", ["x, y", "speed", "shots"], ["update()", "shoot()", "draw()"]),
        (
            84,
            "Enemy",
            ["x, y", "speed", "direction"],
            ["update()", "is_off_screen()", "draw()"],
        ),
    ]:
        d.rectangle([x, 8, x + 72, 108], outline=ink, fill=rgb(15))
        d.rectangle([x, 8, x + 72, 22], outline=ink, fill=rgb(12))
        centered(d, x + 36, 15, title, ink, 9)
        d.line([(x, 56), (x + 72, 56)], fill=ink)
        for i, a in enumerate(attrs):
            d.text((x + 4, 28 + i * 9), a, fill=ink, font=font(7))
        for i, m in enumerate(meths):
            d.text((x + 4, 62 + i * 9), m, fill=ink, font=font(7))
    save_png(img, "semana-09/diagrama-classes.png")


def png_aabb() -> None:
    img = Image.new("RGB", (160, 120), rgb(7))
    d = ImageDraw.Draw(img)
    ink = rgb(1)
    d.rectangle([8, 10, 52, 44], outline=ink, fill=rgb(12))
    d.rectangle([34, 28, 70, 56], outline=ink, fill=rgb(14))
    d.rectangle([34, 28, 52, 44], fill=rgb(8))
    centered(d, 40, 66, "sobrepoe", ink, 8)
    d.rectangle([92, 10, 128, 40], outline=ink, fill=rgb(12))
    d.rectangle([134, 48, 154, 70], outline=ink, fill=rgb(14))
    centered(d, 124, 80, "separados", ink, 8)
    d.line([(90, 0), (90, 119)], fill=rgb(13))
    d.text((6, 88), "ax < bx + bw", fill=ink, font=font(7))
    d.text((6, 98), "and bx < ax + aw", fill=ink, font=font(7))
    d.text((6, 108), "and (o mesmo em y)", fill=ink, font=font(7))
    save_png(img, "semana-10/aabb-diagrama.png")


def png_notas() -> None:
    img = Image.new("RGB", (160, 90), rgb(7))
    d = ImageDraw.Draw(img)
    ink = rgb(1)
    names = ["c", "d", "e", "f", "g", "a", "b"]
    for i, n in enumerate(names):
        x = 4 + i * 22
        d.rectangle([x, 8, x + 21, 70], outline=ink, fill=rgb(7))
        centered(d, x + 11, 62, n, ink, 9)
    for i, label in [(0, "c#"), (1, "d#"), (3, "f#"), (4, "g#"), (5, "a#")]:
        x = 4 + i * 22 + 16
        d.rectangle([x, 8, x + 12, 42], fill=rgb(0))
        centered(d, x + 6, 34, label, rgb(7), 6)
    centered(d, 80, 80, 'sound.set("c3e3g3", ...) : nota + oitava', ink, 7)
    save_png(img, "semana-12/notas-musicais.png")


def png_sprites() -> None:
    save_png(sheet_image(), "semana-11/sprites.png")


def make_pngs() -> None:
    for fn in (
        png_janela, png_repl, png_paleta, png_fluxograma, png_xadrez, png_ciclo,
        png_inimigos, png_estados, png_classes, png_aabb, png_notas, png_sprites,
    ):  # fmt: skip
        fn()


# ------------------------------------------------------------------- PDF


def pdf_escape(text: str) -> bytes:
    raw = text.encode("cp1252", errors="strict")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def wrap(text: str, size: float, width: float, mono: bool = False) -> list[str]:
    per_char = size * (0.6 if mono else 0.5)
    limit = max(int(width / per_char), 10)
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > limit:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def write_pdf(
    path: Path, pages: list[tuple[str, list[str]]], size=(480, 270), base=15
) -> None:
    """Escreve um PDF mínimo. Item de lista que começa com '> ' vira código monoespaçado."""
    w, h = size
    objs: list[bytes] = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    add(b"")  # 2, preenchido depois
    fonts = {
        "F1": b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        "F2": b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        "F3": b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    }
    fids = {k: add(v) for k, v in fonts.items()}  # 3, 4, 5
    kids = []
    for n, (title, items) in enumerate(pages, 1):
        c = bytearray()
        c += f"0.17 0.2 0.37 rg 0 {h - 46} {w} 46 re f\n".encode()
        c += (
            f"BT /F2 {base + 7} Tf 1 1 1 rg 20 {h - 31} Td (".encode()
            + pdf_escape(title)
            + b") Tj ET\n"
        )
        c += b"0.1 0.1 0.1 rg\n"
        y = h - 72
        for item in items:
            mono = item.startswith("> ")
            text = item[2:] if mono else item
            size_pt = base - 2 if mono else base
            font_name = "F3" if mono else "F1"
            first = True
            for line in wrap(text, size_pt, w - 70, mono):
                prefix = b"" if mono else (b"\x95  " if first else b"    ")
                c += (
                    f"BT /{font_name} {size_pt} Tf 28 {y} Td (".encode()
                    + prefix
                    + pdf_escape(line)
                    + b") Tj ET\n"
                )
                y -= size_pt + 5
                first = False
            y -= 4
        c += (
            f"BT /F1 8 Tf 0.5 0.5 0.5 rg {w - 60} 10 Td (".encode()
            + f"{n} / {len(pages)}".encode()
            + b") Tj ET\n"
        )
        content = add(
            b"<< /Length %d >>\nstream\n" % len(c) + bytes(c) + b"\nendstream"
        )
        page = add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Contents {content} 0 R "
            f"/Resources << /Font << /F1 {fids['F1']} 0 R /F2 {fids['F2']} 0 R /F3 {fids['F3']} 0 R >> >> >>".encode()
        )
        kids.append(page)
    objs[1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


SLIDES: dict[str, list[tuple[str, list[str]]]] = {
    "semana-01/slides-ambiente.pdf": [
        (
            "Aula 1: Ambiente, REPL e primeiro programa",
            [
                "Introdução à Programação com Python e Jogos",
                "Profa. Ada Lovelace",
                "Hoje: instalar, explorar o REPL e abrir uma janela",
            ],
        ),
        (
            "Instalação",
            [
                "Python 3.11 ou mais novo: python3 --version",
                "Pyxel: pip install pyxel (de preferência dentro de um venv)",
                "Teste: digite pyxel; ele imprime a versão",
                "Problemas? Traga a mensagem de erro inteira para o atendimento",
            ],
        ),
        (
            "REPL e primeiro programa",
            [
                "REPL: digite uma expressão, veja o resultado na hora",
                "> >>> 2 ** 10",
                "Um programa é um arquivo .py rodado de ponta a ponta",
                "> pyxel.init(160, 120)",
                "> pyxel.run(update, draw)",
            ],
        ),
        (
            "Funções: a receita mínima",
            [
                "def nome(parametros): abre a função; o corpo é indentado",
                "return devolve o resultado para quem chamou",
                "> def dobro(n):",
                ">     return n * 2",
                "Na semana 5 voltamos às funções com calma",
            ],
        ),
    ],
    "semana-02/slides-variaveis.pdf": [
        (
            "Aula 2: Variáveis, tipos e expressões",
            [
                "Variável é um nome ligado a um valor",
                "Tipos básicos: int, float, str, bool",
                "Operadores: + - * / // % **",
            ],
        ),
        (
            "A tela é um plano de coordenadas",
            [
                "Origem (0, 0) no canto superior esquerdo",
                "x cresce para a direita, y cresce para baixo",
                "Tela 160x120: o último pixel é (159, 119)",
                "pyxel.width e pyxel.height guardam o tamanho da tela",
                "> pyxel.rect(x, y, w, h, cor)",
            ],
        ),
        (
            "Cores",
            [
                "16 cores, índices de 0 a 15",
                "0 preto, 7 branco, 8 vermelho, 10 amarelo, 11 verde",
                "Veja a paleta nas notas da aula",
            ],
        ),
    ],
    "semana-03/slides-condicionais.pdf": [
        (
            "Aula 3: Condicionais",
            [
                "if, elif e else escolhem qual bloco roda",
                "Comparações: == != < <= > >=",
                "Lógicos: and, or, not",
            ],
        ),
        (
            "Teclado no Pyxel",
            [
                "btn(tecla): verdadeiro enquanto a tecla está apertada",
                "btnp(tecla): verdadeiro só no quadro em que foi apertada",
                "> if pyxel.btn(pyxel.KEY_LEFT):",
                ">     x = x - 2",
            ],
        ),
        (
            "Limites da tela",
            [
                "Impedir que o personagem saia da janela",
                "> if x > 160 - lado:",
                ">     x = 160 - lado",
                "Teste de mesa: simule o código no papel",
            ],
        ),
    ],
    "semana-04/slides-lacos.pdf": [
        (
            "Aula 4: Laços",
            [
                "for repete para cada item de uma sequência",
                "range(inicio, fim, passo): o fim não entra",
                "while repete enquanto a condição for verdadeira",
            ],
        ),
        (
            "Laços aninhados",
            [
                "Laço externo escolhe a linha, o interno a coluna",
                "> for linha in range(8):",
                ">     for coluna in range(8):",
                "O corpo interno roda 8 x 8 = 64 vezes",
            ],
        ),
        (
            "Cuidados",
            [
                "while sem atualizar a condição trava o programa",
                "break sai do laço, continue pula para a próxima volta",
                "Padrão xadrez: (linha + coluna) % 2",
            ],
        ),
    ],
    "semana-05/slides-funcoes.pdf": [
        (
            "Aula 5 (reposição): Funções",
            [
                "def nome(parametros): agrupa um comportamento",
                "return devolve um valor; print só mostra",
                "Variáveis locais não existem fora da função",
            ],
        ),
        (
            "O ciclo do Pyxel",
            [
                "update(): lógica, 30 vezes por segundo",
                "draw(): desenho, logo depois de update",
                "Nunca desenhe no update nem mude estado no draw",
            ],
        ),
        (
            "Bola quicando",
            [
                "> def quica(pos, vel, minimo, maximo):",
                ">     if pos < minimo or pos > maximo:",
                ">         return -vel",
                ">     return vel",
            ],
        ),
    ],
    "semana-06/slides-listas.pdf": [
        (
            "Aula 6: Listas",
            [
                "Uma lista guarda vários valores em ordem",
                "Índices começam em 0; -1 é o último",
                "append, pop, len, fatiamento lista[1:4]",
            ],
        ),
        (
            "Vários inimigos",
            [
                "Uma lista de inimigos, um laço para atualizar todos",
                "> for gota in gotas:",
                ">     gota[1] += 3",
            ],
        ),
        (
            "Armadilha",
            [
                "Remover itens durante o for pula elementos",
                "Reconstrua a lista com uma compreensão",
                "> gotas[:] = [g for g in gotas if g[1] < 120]",
            ],
        ),
    ],
    "semana-08/slides-dicionarios.pdf": [
        (
            "Aula 8: Dicionários e tuplas",
            [
                "Dicionário: pares chave -> valor",
                "d[chave] falha se ausente; d.get(chave) devolve None",
                "Tupla: sequência imutável, ideal para (x, y)",
            ],
        ),
        (
            "Estado do jogo",
            [
                "> state = {'tela': 'titulo', 'pontos': 0}",
                "Uma função de update e uma de draw por tela",
                "Máquina de estados: título, jogo, fim",
            ],
        ),
    ],
    "semana-09/slides-classes.pdf": [
        (
            "Aula 9: Classes",
            [
                "Classe é a receita, objeto é o bolo",
                "__init__ prepara os atributos do objeto",
                "self é o próprio objeto, passado automaticamente",
            ],
        ),
        (
            "Player e Enemy",
            [
                "> class Enemy:",
                ">     def __init__(self, x, y):",
                ">         self.x = x",
                "Cada objeto tem os seus próprios atributos",
            ],
        ),
        (
            "Quando usar classes",
            [
                "Dados e comportamento que andam juntos",
                "Vários objetos do mesmo tipo",
                "Não transforme tudo em classe: funções ainda servem",
            ],
        ),
    ],
    "semana-10/slides-colisao.pdf": [
        (
            "Aula 10: Colisão e geometria",
            [
                "AABB: retângulo alinhado aos eixos",
                "Dois retângulos se sobrepõem se os intervalos em x e em y se sobrepõem",
            ],
        ),
        (
            "O teste",
            [
                "> ax < bx + bw and bx < ax + aw",
                "> and ay < by + bh and by < ay + ah",
                "Desenhe os casos no papel antes de codar",
            ],
        ),
        (
            "Círculos",
            [
                "Distância entre centros <= soma dos raios",
                "Compare os quadrados para evitar a raiz",
            ],
        ),
    ],
    "semana-11/slides-sprites.pdf": [
        (
            "Aula 11: Sprites e tilemaps",
            [
                "pyxel edit arquivo.pyxres abre o editor",
                "Banco de imagens 256x256, tiles de 8x8",
                "blt copia um pedaço do banco para a tela",
            ],
        ),
        (
            "Tilemaps",
            [
                "Um tilemap é uma grade de tiles",
                "bltm desenha uma região do tilemap",
                "tilemaps[0].pget(col, lin) lê o tile de uma celula",
            ],
        ),
        (
            "Plataforma",
            [
                "Gravidade: vy cresce a cada quadro",
                "Teste os quatro cantos do personagem contra tiles sólidos",
            ],
        ),
    ],
    "semana-12/slides-som.pdf": [
        (
            "Aula 12: Som e música",
            [
                "4 canais, 64 sons (0 a 63) e 8 músicas (0 a 7)",
                "> pyxel.sounds[0].set('c3e3g3', 'p', '7', 'f', 6)",
                "> pyxel.play(0, 0)",
            ],
        ),
        (
            "Notas",
            [
                "Letra da nota, # ou - e a oitava: c3, f#2, b-1",
                "Pausa: r",
                "Timbres: t triângulo, s quadrada, p pulso, n ruído",
            ],
        ),
        (
            "Música",
            [
                "Uma música é uma lista de sons por canal",
                "> pyxel.musics[0].set([0], [1])",
                "> pyxel.playm(0, loop=True)",
            ],
        ),
    ],
    "semana-13/slides-arquivos.pdf": [
        (
            "Aula 13: Arquivos",
            [
                "open(caminho, modo): 'r' ler, 'w' sobrescrever, 'a' acrescentar",
                "with fecha o arquivo sozinho",
            ],
        ),
        (
            "JSON",
            [
                "json.load e json.dump para dicionários e listas",
                "> with open('recorde.json') as f:",
                ">     dados = json.load(f)",
            ],
        ),
        (
            "Recorde em disco",
            [
                "Arquivo ausente ou quebrado: comece de zero",
                "Grave só quando bater o recorde",
            ],
        ),
    ],
    "curso/guia-de-estudo-python.pdf": [
        (
            "Guia de estudo: tipos e operadores",
            [
                "int 3, float 3.5, str 'oi', bool True",
                "+ - * / (divisão real)  // (divisão inteira)  % (resto)  ** (potência)",
                "== != < <= > >=   and or not",
                "type(x) mostra o tipo; int('3') e str(3) convertem",
            ],
        ),
        (
            "Guia de estudo: controle de fluxo",
            [
                "> if x < 0:  ...  elif x == 0:  ...  else:  ...",
                "> for i in range(inicio, fim, passo):  ...",
                "> while condição:  ...",
                "break sai do laço; continue pula para a próxima volta",
            ],
        ),
        (
            "Guia de estudo: estruturas e funções",
            [
                "lista [1, 2, 3]  tupla (1, 2)  dicionário {'a': 1}",
                "lista.append(x)  lista[1:3]  len(lista)  d.get('a')",
                "> def soma(a, b=0):  return a + b",
                "> class Enemy:  def __init__(self, x):  self.x = x",
                "> with open('f.txt') as f:  texto = f.read()",
            ],
        ),
    ],
}


def make_pdfs() -> None:
    for rel, pages in SLIDES.items():
        if rel.startswith("curso/"):
            write_pdf(RES / rel, pages, size=(595, 842), base=13)
        else:
            write_pdf(RES / rel, pages)


# ---------------------------------------------------------------- pyxres


def make_pyxres() -> None:
    import pyxel

    pyxel.init(128, 128, title="gerador", headless=True)
    for name, (tx, ty) in SHEET.items():
        rows = ["".join("0" if c == "." else c for c in row) for row in SPRITES[name]]
        pyxel.images[0].set(tx * 8, ty * 8, rows)
    width, height = 32, 16
    grid = [["0000"] * width for _ in range(height)]
    for col in range(width):
        grid[14][col] = "0100"
        grid[15][col] = "0100"
    for col in range(6, 10):
        grid[10][col] = "0200"
    for col in range(14, 18):
        grid[8][col] = "0200"
    for col in range(22, 27):
        grid[11][col] = "0200"
    for col, row in [
        (7, 9),
        (8, 9),
        (15, 7),
        (16, 7),
        (24, 10),
        (25, 10),
        (4, 13),
        (30, 13),
    ]:
        grid[row][col] = "0300"
    pyxel.tilemaps[0].set(0, 0, [" ".join(r) for r in grid])
    pyxel.sounds[0].set("c3e3g3c4", "p", "7", "f", 6)
    pyxel.sounds[1].set("c2c1", "n", "7", "f", 12)
    pyxel.save(str(RES / "semana-11" / "personagem.pyxres"))


if __name__ == "__main__":
    make_pngs()
    make_pdfs()
    if "--no-pyxres" not in sys.argv:
        os.chdir(RES)
        make_pyxres()
