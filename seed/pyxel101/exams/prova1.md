---
# Prova 1: semanas 1 a 6. O gabarito comentado só é liberado depois do fim da prova.
course: pyxel101
author: Ada Lovelace
locale: pt-BR
description: Prova individual e sem consulta sobre ambiente, variáveis, condicionais, laços, funções e listas.
tags: [prova1]
start: 2026-09-15T10:00:00
duration: 2h
shuffle: true
grading: partial
penalty: none
meta:
  # Formato proposto (W7): o gabarito só é liberado depois do fim da prova.
  release: after-end
---

# [prova1] Prova 1

Prova individual e sem consulta, com duração de 2 horas. Responda a todas as questões.
Nas questões de múltipla escolha, marque uma única alternativa. Nas de múltipla
seleção e de verdadeiro ou falso, cada item vale por si. Escreva o código das
questões abertas com clareza: indentação errada é erro.

---
include: ambiente-primeiro-programa
---

---
include: ambiente-potencia-no-repl
---

---
include: variaveis-tipo-de-literal
---

---
include: variaveis-nomes-validos
---

---
include: variaveis-divisao-inteira
---

---
include: variaveis-coordenadas-tela
---

---
include: condicionais-btn-vs-btnp
---

---
include: condicionais-tabela-verdade
---

---
include: laços/passos-do-range.md
---

---
include: laços/padrão-xadrez.md
---

---
include: funcoes-retorno-vs-print
---

---
include: funcoes-escopo-de-variaveis
---

---
include: funcoes-update-draw
---

---
include: listas-indice-negativo
---

---
include: listas-append-ou-extend
---

---
id: cls-no-fim
title: Limpar a tela no fim de draw
tags: [funcoes, ciclo]
---

Um aluno escreveu a função `draw` abaixo.

```python
def draw():
    pyxel.rect(x, y, 8, 8, 9)
    pyxel.cls(0)
```

O que o jogador vê na janela a cada quadro?

* [ ] Um quadrado laranja se movendo normalmente.
  > O `cls` roda depois do `rect` e apaga o que acabou de ser desenhado.
* [*] Apenas a tela preta.
  > O Pyxel mostra o quadro quando `draw` termina, e a última coisa que a função fez foi limpar tudo.
* [ ] O quadrado laranja, deixando um rastro.
  > O rastro aparece quando `cls` nunca é chamado. Aqui ele é chamado, só que tarde.
* [ ] Uma mensagem de erro, porque `cls` só pode ser a primeira chamada.
  > Não existe essa regra, a ordem apenas muda o resultado.

---
id: retangulos-da-grade
title: Retângulos da grade
tags: [lacos, range]
domain: integer
incorrectFeedback: Conte os valores de `x` que o `range` produz. O `range(0, 160, 16)` começa em 0 e não inclui o 160.
---

Quantos retângulos o código abaixo desenha?

```python
for x in range(0, 160, 16):
    pyxel.rect(x, 0, 8, 8, 7)
```

[numeric]: 10

---
id: seta-sem-limite
title: O jogador que foge da tela
tags: [condicionais, funcoes]
weight: 2
---

O jogo tem a função `update` abaixo, com `x` guardando a posição do jogador em uma
janela de 160 pixels de largura, e o jogador tem 8 pixels de largura.

```python
def update():
    global x
    if pyxel.btn(pyxel.KEY_RIGHT):
        x += 2
```

Descreva o que acontece quando o jogador segura a seta direita por muito tempo e
reescreva `update` para que o jogador pare na borda da janela.

[essay]

## [answer-key]

Como não há limite, `x` cresce a cada quadro e o jogador sai pela direita, continuando
a existir fora da janela (e `x` cresce sem parar). O último `x` válido é
`pyxel.width - 8`, ou seja, 152.

```python
def update():
    global x
    if pyxel.btn(pyxel.KEY_RIGHT):
        x = min(x + 2, pyxel.width - 8)
```

Aceitar `if x > pyxel.width - 8: x = pyxel.width - 8` depois do `x += 2`. Descontar
a resposta `if x < 152: x += 2`: com `x` ímpar (151, por exemplo) o passo de 2 leva
a 153 e o jogador ainda passa 1 pixel da borda, porque o teste olha o `x` antes do
passo. A resposta deve citar `pyxel.width - 8` (ou 152), e não só 160.
