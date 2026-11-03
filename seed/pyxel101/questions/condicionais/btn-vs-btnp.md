---
title: btn ou btnp
tags: [condicionais, teclado]
locale: pt-BR
---

O personagem deve pular uma única vez a cada vez que o jogador aperta a barra de
espaço, mesmo que a tecla continue pressionada por vários quadros. Qual teste
deve aparecer em `update`?

* [ ] `if pyxel.btn(pyxel.KEY_SPACE):`
  > `btn` é verdadeiro em todo quadro em que a tecla está pressionada. O
  > personagem pularia a cada quadro enquanto o jogador segurasse a tecla.
* [*] `if pyxel.btnp(pyxel.KEY_SPACE):`
  > `btnp` é verdadeiro só no quadro em que a tecla foi apertada.
* [ ] `if pyxel.btnr(pyxel.KEY_SPACE):`
  > `btnr` detecta a tecla sendo solta, então o pulo só começaria ao soltá-la.
* [ ] `if pyxel.key(pyxel.KEY_SPACE):`
  > Não existe a função `pyxel.key`.
