---
title: Tuplas
tags: [dicionarios, tuplas]
locale: pt-BR
---

Considere a tupla abaixo e julgue as afirmações.

```python
posicao = (10, 20)
```

* [F] `posicao[0] = 11` troca o `x` e deixa `posicao` igual a `(11, 20)`.
  > Tuplas são imutáveis: a atribuição levanta `TypeError`.
* [T] `x, y = posicao` atribui 10 a `x` e 20 a `y`.
  > É o desempacotamento, muito usado para coordenadas.
* [T] Uma tupla pode ser chave de dicionário, como em `{(0, 0): "inicio"}`.
  > Tuplas de valores imutáveis são "hasheáveis". Listas não são.
* [F] `posicao.append(30)` acrescenta um terceiro elemento.
  > Tuplas não têm `append`; o resultado seria `AttributeError`.
