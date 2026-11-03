---
title: "Gerador de fases (rascunho)"
tags: [rascunho, dicionarios]
locale: pt-BR
weight: 2
---

Um gerador de fases guarda o mapa como uma lista de listas, e cada tile pode ser
descrito por um dicionário com o seu tipo e se é sólido.

Explique o que cada estrutura de dados representaria no gerador: a lista de listas,
o dicionário de cada tile e a tupla de uma posição `(coluna, linha)`.

[essay]

## [answer-key]

A lista de listas é o mapa: `mapa[linha][coluna]` devolve o tile. O dicionário
descreve um tipo de tile, como `{"nome": "chao", "solido": True}`. A tupla
`(coluna, linha)` identifica uma posição e pode ser chave de dicionário, por
exemplo para guardar os inimigos de cada célula.

Critérios: mapa como lista de listas (40%), tile como dicionário (30%), tupla como
posição (30%).
