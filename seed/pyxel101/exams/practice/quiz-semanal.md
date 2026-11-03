---
# Quiz de prática semanal: não vale nota. Tem 6 questões: a de `ambiente-pyxel-init`, 4 sorteadas do banco marcado como `semanal` e uma própria.
course: pyxel101
author: Ada Lovelace
locale: pt-BR
description: Treino do formato das provas, com perguntas sorteadas de um banco.
tags: [semanal]
shuffle: true
---

# [quiz-semanal] Quiz semanal

Treino sem nota. Você pode refazer o quiz quantas vezes quiser, e as perguntas mudam
a cada tentativa.

---
include: ambiente-pyxel-init
---

---
includeAll: semanal
max: 4
---

---
id: ordem-update-draw
title: Quem vem primeiro
tags: [funcoes, ciclo]
---

A cada quadro, em que ordem o Pyxel chama as funções que você passou a `pyxel.run(update, draw)`?

* [*] Primeiro `update`, depois `draw`.
  > O estado é atualizado antes de ser desenhado.
* [ ] Primeiro `draw`, depois `update`.
  > Desenhar antes de atualizar mostraria o estado do quadro anterior.
* [ ] As duas ao mesmo tempo, em threads separadas.
  > O Pyxel as chama em sequência, no mesmo thread.
