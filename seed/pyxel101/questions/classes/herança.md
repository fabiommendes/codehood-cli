---
title: Herança entre inimigos
tags: [classes, heranca]
locale: pt-BR
weight: 2
---

O jogo tem dois tipos de inimigo. O `Bat` voa em zigue-zague e o `Slime` anda pelo
chão. Os dois têm posição, vida e um método `draw`, mas se movem de modo diferente.

Explique como a herança pode organizar esse código. Diga o que ficaria em uma classe
base `Enemy` e o que ficaria em cada subclasse, e cite uma situação em que a herança
seria uma má escolha.

[essay]

## [answer-key]

A classe base `Enemy` guarda o que é comum: `__init__` com `x`, `y` e `hp`, o método
`draw` (se o desenho for parecido) e `take_damage`. Cada subclasse chama
`super().__init__(...)` no seu `__init__` e sobrescreve o `update`, que é onde o movimento difere.

```python
class Enemy:
    def __init__(self, x, y, hp):
        self.x, self.y, self.hp = x, y, hp

    def take_damage(self, amount):
        self.hp -= amount

class Bat(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, hp=3)

    def update(self):
        self.x -= 1
        self.y += 2 if pyxel.frame_count % 20 < 10 else -2

class Slime(Enemy):
    def update(self):
        self.x -= 0.5
```

A herança é má escolha quando a relação não é do tipo "é um" (por exemplo, `Enemy`
herdar de `Player` só para reaproveitar a colisão), ou quando as classes só
compartilham uma função solta. Nesses casos vale mais uma função auxiliar ou
composição (um objeto `Hitbox` dentro de cada classe).

Critérios: base com o comum (40%), subclasses com `super()` e comportamento próprio
(40%), situação de má escolha plausível (20%).
