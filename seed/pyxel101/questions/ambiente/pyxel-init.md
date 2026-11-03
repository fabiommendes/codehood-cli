---
title: Abrindo a janela
tags: [ambiente, semanal]
locale: pt-BR
---

Para abrir uma janela de 160 pixels de largura por 120 de altura, com o título "Jogo",
o programa começa assim:

pyxel.init(160, [^altura], title="Jogo")

Depois, o laço principal é iniciado por pyxel.[^laco], que recebe as funções
`update` e `draw` como argumentos.

[^altura/numeric]: 120

[^laco/short-answer]:
* run
  > Isso mesmo: `pyxel.run(update, draw)` devolve o controle ao Pyxel até a janela fechar.

[^laco/short-answer/reject]:
* start
  > `pyxel.start` não existe. O Pyxel usa `pyxel.run`.
* loop
  > Não existe `pyxel.loop`.
