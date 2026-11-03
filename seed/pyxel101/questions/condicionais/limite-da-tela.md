---
title: Não sair pela borda direita
tags: [condicionais, colisao, semanal]
locale: pt-BR
---

Um quadrado de 8 pixels de largura está na posição `x` e anda um pixel por quadro para
a direita. Ele não pode ultrapassar a borda direita da janela. Complete a condição que
permite o movimento.

if x [^operador] pyxel.width - [^largura]:

[^operador]:
* [ ] `<=`
  > Com `<=`, o quadrado ainda andaria quando já encosta na borda e sairia 1 pixel da tela.
* [*] `<`
  > Com `x < pyxel.width - 8` o último `x` permitido é 151 e o quadrado termina em 159.
* [ ] `>`
  > Com `>`, o quadrado só andaria depois de já ter saído da tela.
* [ ] `>=`
  > Com `>=`, o quadrado só andaria depois de já ter saído da tela.

[^largura/numeric]: 8
