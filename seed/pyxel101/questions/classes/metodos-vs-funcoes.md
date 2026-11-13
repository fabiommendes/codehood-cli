---
title: Métodos e self
tags: [classes, metodos]
locale: pt-BR
---

Considere a classe e julgue as afirmações.

```python
class Enemy:
    def move(self):
        self.x += 1


enemy = Enemy()
```

* [T] Na definição de um método de instância, o primeiro parâmetro costuma ser `self`.
  > O Python o preenche sozinho na chamada.
* [F] Para chamar o método é preciso escrever `enemy.move(enemy)`.
  > `enemy.move()` já passa `enemy` como `self`. Passar de novo causaria `TypeError`.
* [T] `Enemy.move(enemy)` é uma chamada válida e equivale a `enemy.move()`.
  > Chamando pela classe, o primeiro argumento vira o `self` explicitamente.
* [F] Uma função solta, fora de classe, recebe `self` automaticamente.
  > Só os métodos de instância têm esse comportamento.
