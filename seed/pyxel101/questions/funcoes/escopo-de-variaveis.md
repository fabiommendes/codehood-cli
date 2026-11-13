---
title: Escopo e global
tags: [funcoes, escopo]
locale: pt-BR
incorrectFeedback: Pense na palavra-chave que avisa o Python de que o nome pertence ao módulo, e não à função.
---

O programa abaixo imprime `10`, e não `0`.

```python
pontos = 10


def zera():
    pontos = 0


zera()
print(pontos)
```

Dentro de `zera`, o nome `pontos` é uma variável local nova. Que palavra-chave,
escrita como primeira linha do corpo de `zera` seguida do nome da variável, faz a
função alterar o `pontos` do módulo?

[short-answer]:
* /global(\s+pontos)?/
  > Com `global pontos` na primeira linha, o `pontos = 0` muda a variável do módulo.

[short-answer/reject]:
* nonlocal
  > `nonlocal` vale para funções aninhadas. Aqui o `pontos` está no módulo.
* return
  > `return` devolve um valor, mas não muda a variável do módulo sozinho.
