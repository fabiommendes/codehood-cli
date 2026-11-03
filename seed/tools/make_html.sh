#!/bin/sh
# Gera resources/semana-05/bola-jogavel.html com pyxel package + app2html. Uso: tools/make_html.sh
set -e
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
mkdir "$work/bola"
cp "$root/pyxel101/resources/semana-05/bola.py" "$work/bola/"
(cd "$work" && uv run --with pyxel pyxel package bola bola/bola.py && uv run --with pyxel pyxel app2html bola.pyxapp)
cp "$work/bola.html" "$root/pyxel101/resources/semana-05/bola-jogavel.html"
rm -rf "$work"
