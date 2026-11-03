---
title: while True dentro do jogo
tags: [lacos, while, pyxel]
locale: pt-BR
---

Julgue as afirmações sobre laços `while` em programas Pyxel.

* [T] Um `while True:` sem `break` nem `return` dentro de `update` trava o jogo.
  > O Pyxel só desenha e lê o teclado quando `update` termina. Se ela nunca termina,
  > a janela congela.
* [F] `while not pyxel.btnp(pyxel.KEY_SPACE): pass` dentro de `update` espera o jogador apertar espaço.
  > O estado do teclado só é atualizado entre quadros. Dentro do laço ele nunca muda,
  > então o laço nunca termina. A espera se faz com um `if` e uma variável de estado.
* [T] Para repetir algo a cada quadro, basta o `pyxel.run` chamar `update` e `draw`.
  > O ciclo do Pyxel já é o laço principal do jogo.
* [F] Todo `while True:` é um laço infinito.
  > Um `break` ou um `return` alcançável encerra o laço.
