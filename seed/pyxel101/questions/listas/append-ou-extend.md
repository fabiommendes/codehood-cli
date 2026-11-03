---
title: append ou extend
tags: [listas, metodos]
locale: pt-BR
shuffle: true
---

Qual é o conteúdo de `a` e de `b` depois do código abaixo?

```python
a = [1, 2]
a.append([3, 4])

b = [1, 2]
b.extend([3, 4])
```

* [ ] `a` é `[1, 2, 3, 4]` e `b` é `[1, 2, 3, 4]`
  > `append` acrescenta um único elemento, mesmo que ele seja uma lista.
* [*] `a` é `[1, 2, [3, 4]]` e `b` é `[1, 2, 3, 4]`
  > `append` acrescenta a lista inteira como um elemento. `extend` acrescenta os itens, um a um.
* [ ] `a` é `[1, 2, 3, 4]` e `b` é `[1, 2, [3, 4]]`
  > Os métodos estão trocados: é o `append` que aninha a lista.
* [ ] `a` é `[1, 2, [3, 4]]` e `b` é `[1, 2, [3, 4]]`
  > `extend` percorre o argumento e acrescenta cada item.
