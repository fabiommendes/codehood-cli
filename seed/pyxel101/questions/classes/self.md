---
title: O papel do self
tags: [classes, self]
locale: pt-BR
shuffle: true
---

Considere o código abaixo.

```python
class Enemy:
    def __init__(self, x):
        self.x = x

    def move(self):
        self.x += 1

a = Enemy(0)
b = Enemy(10)
a.move()
```

Quando `a.move()` executa, a que se refere `self` dentro de `move`?

* [ ] À classe `Enemy`, que é compartilhada por todos os inimigos.
  > A classe não é `self`. Cada chamada de método recebe o objeto específico.
* [*] Ao objeto `a`, aquele sobre o qual o método foi chamado.
  > Por isso, só o `x` de `a` passa a valer 1. O `x` de `b` continua 10.
* [ ] Ao último objeto criado, que aqui é `b`.
  > O Python não usa o objeto mais recente. Usa o que está antes do ponto na chamada.
* [ ] A uma palavra reservada que só existe dentro de `__init__`.
  > `self` é só uma convenção de nome, e vale em todos os métodos de instância.
