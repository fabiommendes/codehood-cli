---
title: Retângulos que se sobrepõem
tags: [colisao, aabb]
locale: pt-BR
---

O retângulo `A` tem `x = 10`, `y = 10`, largura 20 e altura 20, e ocupa os pixels de
10 a 29 nos dois eixos. Cada retângulo abaixo é descrito como `(x, y, largura, altura)`.
Marque os que se sobrepõem a `A`.

* [x] `(20, 20, 20, 20)`
* [ ] `(30, 10, 10, 10)`
  > Ele começa no pixel 30, logo depois da borda de `A`. Eles se encostam, mas nenhum
  > pixel é compartilhado.
* [x] `(25, 25, 5, 5)`
  > Está inteiramente dentro de `A`. Contido também é sobreposto.
* [ ] `(0, 40, 50, 10)`
  > É largo o bastante em `x`, mas fica abaixo de `A`: seus pixels de `y` vão de 40 a 49.
* [x] `(0, 0, 15, 15)`
* [ ] `(31, 12, 4, 4)`
  > Começa em `x = 31`, à direita da borda de `A`, que termina em 29.
