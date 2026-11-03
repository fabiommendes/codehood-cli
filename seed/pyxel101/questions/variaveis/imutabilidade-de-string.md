---
title: Strings são imutáveis
tags: [variaveis, strings, semanal]
locale: pt-BR
---

Considere a variável abaixo e julgue cada afirmação.

```python
texto = "pyxel"
```

* [F] `texto[0] = "P"` troca a primeira letra e deixa `texto` igual a `"Pyxel"`.
  > Isso levanta `TypeError`: strings não aceitam atribuição por índice.
* [T] `texto = "P" + texto[1:]` cria uma nova string e faz `texto` apontar para ela.
  > A string antiga não foi alterada, só deixou de ser referenciada.
* [T] `texto.upper()` devolve uma nova string e deixa `texto` como estava.
  > Para guardar o resultado é preciso atribuí-lo: `name = texto.upper()`.
* [F] `len(texto)` vale 4.
  > Há cinco letras em `"pyxel"`, então `len(texto)` vale 5.
