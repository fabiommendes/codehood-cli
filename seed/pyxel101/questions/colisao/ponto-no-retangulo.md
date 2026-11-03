---
title: Ponto dentro do retângulo
tags: [colisao, geometria]
locale: pt-BR
incorrectFeedback: O limite direito é a coordenada onde o retângulo termina, e não o seu tamanho. Parta da posição inicial.
---

Um ponto `(px, py)` está dentro do retângulo de canto `(x, y)`, largura `w` e
altura `h` quando `x <= px < ...` e `y <= py < y + h`.

Que expressão completa o limite direito, no lugar das reticências?

[short-answer]:
* /x\s*\+\s*w|w\s*\+\s*x/
  > Isso mesmo. O limite é exclusivo, porque o último pixel do retângulo é `x + w - 1`.

[short-answer/reject]:
* w
  > `w` é a largura, e não uma coordenada. O limite é uma posição na tela.
* /x\s*\*\s*w/
  > Multiplicar não faz sentido aqui: o retângulo termina uma largura depois do início.
