---
# FORMATO PROPOSTO, NÃO DECIDIDO (W8): o MDQ não tem um tipo de questão de código.
# Esta questão usa `type: code`, as chaves `language` e `function`, a tag `[code]`
# e os testes ocultos em um bloco `python tests` depois da tag. Espera-se que o
# `mdq` rejeite este arquivo.
title: Fatorial
type: code
language: python
function: factorial
tags: [funcoes, codigo]
locale: pt-BR
---

Escreva a função `factorial(n)`, que devolve `n!` para um inteiro `n >= 0`. Lembre que
`0! = 1`. Para `n` negativo, levante `ValueError`.

```python
def factorial(n):
    """Devolve n! (fatorial de n)."""
```

[code]

```python tests
import pytest

assert factorial(0) == 1
assert factorial(1) == 1
assert factorial(5) == 120
assert factorial(10) == 3628800
with pytest.raises(ValueError):
    factorial(-1)
```

## [answer-key]

```python
def factorial(n):
    if n < 0:
        raise ValueError("n must be >= 0")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
```
