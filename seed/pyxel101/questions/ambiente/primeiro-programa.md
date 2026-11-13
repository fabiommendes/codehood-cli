---
title: Anatomia do primeiro programa
tags: [ambiente]
locale: pt-BR
---

Considere o programa mínimo abaixo e julgue cada afirmação.

```python
import pyxel


def update():
    pass


def draw():
    pyxel.cls(0)


pyxel.init(160, 120, title="Janela")
pyxel.run(update, draw)
print("fim")
```

* [T] `pyxel.init` precisa ser chamado antes de `pyxel.run`.
  > Sem a janela criada por `init`, não há onde o `run` desenhar.
* [T] `pyxel.run` recebe as duas funções como argumentos, sem chamá-las.
  > Escrever `pyxel.run(update(), draw())` chamaria as funções na hora e passaria `None`.
* [F] O `print("fim")` aparece depois do primeiro quadro desenhado.
  > `pyxel.run` só devolve o controle quando a janela é fechada.
* [F] Se `draw` ficasse vazia, o programa deixaria de funcionar.
  > Uma `draw` vazia é válida, a janela só fica sem desenho.
