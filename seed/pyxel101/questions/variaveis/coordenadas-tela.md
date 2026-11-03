---
title: Origem das coordenadas
tags: [variaveis, coordenadas]
locale: pt-BR
incorrectFeedback: Na tela do Pyxel, `x` cresce para a direita e `y` cresce para baixo. A origem fica onde os dois valem zero.
---

Em qual canto da janela do Pyxel está o pixel de coordenadas `(0, 0)`?

[short-answer]:
* /(superior|topo|cima).*esquerd[oa]/n
  > Isso mesmo: a origem fica no canto superior esquerdo.
* /esquerd[oa].*(superior|topo|cima)/n
  > Isso mesmo: a origem fica no canto superior esquerdo.

[short-answer/reject]:
* /(inferior|baixo).*esquerd[oa]/n
  > Esse é o canto da matemática escolar. No Pyxel, `y` cresce para baixo.
* /centro/n
  > O centro da janela é `(pyxel.width // 2, pyxel.height // 2)`.
