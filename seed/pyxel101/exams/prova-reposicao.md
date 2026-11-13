---
# Prova de reposição: substitui a menor nota entre a Prova 1 e a Prova 2.
course: pyxel101
author: Ada Lovelace
locale: pt-BR
description: Reposição para quem perdeu uma das provas com justificativa. Cobre o semestre inteiro.
tags: [reposicao]
start: 2026-11-18T16:00:00
duration: 2h
shuffle: true
grading: partial
penalty: none
meta:
  # Formato proposto (W7): o gabarito só é liberado depois do fim da prova.
  release: after-end
---

# [prova-reposicao] Prova de reposição

Prova individual e sem consulta, com duração de 2 horas, sobre o conteúdo do semestre.
Vale como substituta da menor nota entre a Prova 1 e a Prova 2.

---
include: variaveis-cores-pyxel
---

---
include: condicionais-btn-vs-btnp
---

---
include: funcoes-fase-do-ciclo
---

---
include: listas-fatiamento
---

---
include: dicionarios-acessar-chave-ausente
---

---
include: classes-self
---

---
include: colisao-aabb-sobrepoe
---

---
include: pyxel-tilemap-tamanho
---

---
include: arquivos-modo-de-abertura
---

---
include: código/soma-pares.md
---

---
id: remover-ultimo
title: Remover o último elemento
tags: [listas, metodos]
incorrectFeedback: Procure um método de lista que remove um elemento por posição e o devolve. Sem argumentos, ele age sobre o último.
---

Que método de lista remove o último elemento e o devolve ao chamador?

[short-answer]:
* pop
  > Isso mesmo. `items.pop()` devolve o último; `items.pop(0)` o primeiro.

[short-answer/reject]:
* remove
  > `remove(valor)` procura um valor e não devolve nada.
* del
  > `del items[-1]` apaga o último, mas é um comando, e não um método. Ele não devolve o item.

---
id: limitar-valor
title: Escrever clamp
tags: [funcoes, condicionais]
content: code
highlight: python
weight: 2
---

Escreva a função `clamp(value, low, high)`, que devolve `value` limitado ao intervalo
de `low` a `high`: se `value` for menor que `low` devolve `low`, se for maior que `high`
devolve `high`, e senão devolve o próprio `value`. Mostre também como você a usaria em
`update` para manter `player_x` dentro de uma janela de 160 pixels, sendo o jogador
de 8 pixels de largura.

[essay]

## [answer-key]

```python
def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value

player_x = clamp(player_x, 0, pyxel.width - 8)
```

Aceitar `return max(low, min(value, high))`. A chamada deve usar `pyxel.width - 8`
como limite superior (152). Descontar se os limites forem trocados ou se a função
imprimir em vez de devolver.
