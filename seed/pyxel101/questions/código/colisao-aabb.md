---
# FORMATO PROPOSTO, NÃO DECIDIDO (W8): o MDQ não tem um tipo de questão de código.
# Esta questão usa `type: code`, as chaves `language` e `function`, a tag `[code]`
# e os testes ocultos em um bloco `python tests` depois da tag. Espera-se que o
# `mdq` rejeite este arquivo.
title: Colisão entre retângulos
type: code
language: python
function: overlaps
tags: [colisao, codigo]
locale: pt-BR
weight: 2
---

Escreva a função `overlaps(a, b)`, que recebe dois retângulos como tuplas
`(x, y, w, h)` e devolve `True` quando eles têm ao menos um pixel em comum. Retângulos
que só se encostam pela borda não se sobrepõem.

```python
def overlaps(a, b):
    """Devolve True se os retângulos a e b se sobrepõem."""
```

[code]

```python tests
assert overlaps((0, 0, 10, 10), (5, 5, 10, 10))
assert overlaps((0, 0, 10, 10), (2, 2, 3, 3))
assert not overlaps((0, 0, 10, 10), (10, 0, 5, 5))
assert not overlaps((0, 0, 10, 10), (0, 20, 5, 5))
assert overlaps((5, 5, 1, 1), (5, 5, 1, 1))
```

## [answer-key]

```python
def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
```
