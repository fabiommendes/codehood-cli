#!/usr/bin/env sh
# Roda o jogo a partir da raiz do repositório, de qualquer pasta.
cd "$(dirname "$0")/.." || exit 1
exec python main.py "$@"
