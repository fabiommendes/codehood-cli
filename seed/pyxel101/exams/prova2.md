---
# Prova 2: semanas 8 a 13. O gabarito comentado só é liberado depois do fim da prova.
course: pyxel101
author: Ada Lovelace
locale: pt-BR
description: Prova individual e sem consulta sobre dicionários, classes, colisão, recursos do Pyxel e arquivos.
tags: [prova2]
start: 2026-11-10T10:00:00
duration: 2h
shuffle: true
grading: partial
penalty: none
meta:
  # Formato proposto (W7): o gabarito só é liberado depois do fim da prova.
  release: after-end
---

# [prova2] Prova 2

Prova individual e sem consulta, com duração de 2 horas. Responda a todas as questões.
Considere sempre Python 3 e o Pyxel 2.x. Na questão de código, a função é avaliada
por testes que você não vê, então confira os casos de borda.

---
include: dicionarios-acessar-chave-ausente
---

---
include: dicionarios-tupla-imutavel
---

---
include: dicionarios-estado-do-jogo
---

---
include: classes-self
---

---
include: classes-init-do-inimigo
---

---
include: classes/herança.md
---

---
include: classes-metodos-vs-funcoes
---

---
include: colisao-aabb-sobrepoe
---

---
include: colisao-area-do-retangulo
---

---
include: colisao-ponto-no-retangulo
---

---
include: pyxel-tilemap-tamanho
---

---
include: pyxel-canais-de-som
---

---
include: arquivos-modo-de-abertura
---

---
include: listas-remover-durante-iteracao
---

---
include: código/colisao-aabb.md
---

---
id: troca-de-cena
title: Trocando de cena
tags: [dicionarios, estado]
---

O jogo tem três telas, `"titulo"`, `"jogo"` e `"fim"`, e guarda a tela atual em um
dicionário. O estado começa assim:

```python
state = {"tela": "titulo", "pontos": 0}
```

Em `update`, quando o jogador aperta Enter na tela de título, o jogo passa para a tela
de jogo. Complete o código.

if state["tela"] == [^atual] and pyxel.btnp(pyxel.KEY_RETURN):

state["tela"] = [^proxima]

[^atual/short-answer]:
* /['"]?titulo['"]?/
  > A tela inicial é a do título, como no estado do início.

[^proxima/short-answer]:
* /['"]?jogo['"]?/
  > Depois do título, a tela passa a ser a do jogo.

---
id: colisao-circulos
title: Colisão entre círculos
tags: [colisao, geometria]
---

Julgue as afirmações sobre colisão.

* [T] Dois retângulos que só se encostam pela borda não se sobrepõem quando a fórmula usa `<` estrito.
  > Eles compartilham a borda, mas nenhum pixel.
* [F] Dois círculos colidem quando a distância entre os centros é menor que a soma dos diâmetros.
  > O correto é comparar com a soma dos raios.
* [T] Comparar o quadrado da distância com o quadrado da soma dos raios evita calcular a raiz quadrada.
  > É uma otimização comum quando a colisão é testada para muitos objetos por quadro.
* [F] Em AABB, a sigla indica que os retângulos podem estar girados em qualquer ângulo.
  > AABB significa *axis-aligned bounding box*: os lados são paralelos aos eixos.
