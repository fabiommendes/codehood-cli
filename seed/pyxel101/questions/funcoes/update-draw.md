---
title: Ciclo update e draw
tags: [funcoes, pyxel, ciclo]
locale: pt-BR
---

Julgue as afirmações sobre as funções passadas a `pyxel.run`.

* [T] A cada quadro, o Pyxel chama `update` e depois `draw`.
  > `update` calcula o novo estado e `draw` o desenha.
* [F] `draw` deve calcular as novas posições, e `update` só deve desenhar.
  > Os papéis são o contrário: `update` muda o estado, `draw` só o mostra.
* [T] `update` e `draw` são escritas pelo programador e chamadas pelo Pyxel.
  > Você entrega as funções, e o Pyxel decide quando chamá-las.
* [F] É preciso chamar `update()` dentro de `draw` para que a lógica do jogo rode.
  > O Pyxel já chama `update` a cada quadro. Chamá-la de novo executaria a lógica duas vezes.
