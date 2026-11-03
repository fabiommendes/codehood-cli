---
title: O construtor de Enemy
tags: [classes, construtor, semanal]
locale: pt-BR
---

Veja a classe abaixo.

```python
class Enemy:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.alive = True
```

Ao escrever Enemy(10, 20), o Python chama automaticamente o método [^init], e os
valores 10 e 20 ficam guardados nos atributos self.x e self.[^atributo]. O primeiro
parâmetro, que o Python preenche sozinho com o novo objeto, costuma se chamar
[^primeiro].

[^init/short-answer]:
* __init__
  > Esse é o construtor da classe, chamado na criação do objeto.

[^init/short-answer/reject]:
* constructor
  > Em Python o construtor se chama `__init__`.

[^atributo/short-answer]: y

[^primeiro]:
* [ ] this
  > `this` é de Java e JavaScript. Em Python a convenção é `self`.
* [*] self
* [ ] cls
  > `cls` é a convenção para métodos de classe, e não para `__init__`.
* [ ] obj
  > Funcionaria, mas foge da convenção que todo programador Python espera.
