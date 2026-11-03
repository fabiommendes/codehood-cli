---
title: Expressões lógicas
tags: [condicionais, logica]
locale: pt-BR
---

Sejam `a = True`, `b = False` e `c = True`. Marque as expressões que valem `True`.

* [x] `a and c`
* [ ] `a and b`
  > `and` exige que os dois lados sejam verdadeiros, e `b` é falso.
* [x] `a or b`
  > `or` basta que um lado seja verdadeiro.
* [x] `not b`
* [ ] `not (a or b)`
  > `a or b` vale `True`, e `not True` vale `False`.
* [x] `b or (a and c)`
  > Entre parênteses, `a and c` vale `True`, então o `or` também vale.
