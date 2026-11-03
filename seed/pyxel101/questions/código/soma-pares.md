---
# FORMATO PROPOSTO, NÃO DECIDIDO (W8): o MDQ não tem um tipo de questão de código.
# Esta questão usa `type: code`, as chaves `language` e `function`, a tag `[code]`
# e os testes ocultos em um bloco `python tests` depois da tag. Espera-se que o
# `mdq` rejeite este arquivo.
title: Soma dos pares
type: code
language: python
function: sum_even
tags: [funcoes, listas, codigo]
locale: pt-BR
---

Escreva a função `sum_even(values)`, que recebe uma lista de inteiros e devolve a soma
dos valores pares. Uma lista sem pares, ou vazia, devolve `0`.

```python
def sum_even(values):
    """Devolve a soma dos inteiros pares de `values`."""
```

[code]

```python tests
assert sum_even([1, 2, 3, 4]) == 6
assert sum_even([]) == 0
assert sum_even([1, 3, 5]) == 0
assert sum_even([-2, 2, 7]) == 0
assert sum_even([10]) == 10
```

## [answer-key]

```python
def sum_even(values):
    total = 0
    for value in values:
        if value % 2 == 0:
            total += value
    return total
```
