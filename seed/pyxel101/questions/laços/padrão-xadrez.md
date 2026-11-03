---
title: Tabuleiro com laços aninhados
tags: [lacos, aninhados, desenho]
locale: pt-BR
weight: 2
---

Uma janela de 128 por 128 pixels deve mostrar um tabuleiro de 8 por 8 casas, cada
casa com 16 pixels de lado, alternando as cores 7 (branco) e 0 (preto).

Explique como dois laços `for` aninhados desenham o tabuleiro: o que cada laço
percorre, como a posição de cada casa é calculada e qual condição decide a cor.
Pode usar código.

[essay]

## [answer-key]

Um laço percorre as linhas (`linha`, de 0 a 7) e o outro as colunas (`coluna`, de 0 a 7).
A casa de cada par fica na posição `x = coluna * 16`, `y = linha * 16`. A cor alterna
quando a soma `linha + coluna` muda de paridade, então a condição é `(linha + coluna) % 2 == 0`.

```python
for linha in range(8):
    for coluna in range(8):
        cor = 7 if (linha + coluna) % 2 == 0 else 0
        pyxel.rect(coluna * 16, linha * 16, 16, 16, cor)
```

Aceitar variações: usar `linha % 2 == coluna % 2`, trocar as cores, ou um contador que
inverte a cada casa (desde que inverta também ao mudar de linha). Descontar quando
a cor depende só de `coluna` (gera listras) ou quando as posições não são multiplicadas
por 16.
