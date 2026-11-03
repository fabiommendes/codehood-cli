---
title: Laço duplo
tags: [lacos, aninhados]
locale: pt-BR
shuffle: true
---

Quanto vale `count` ao final do programa?

```python
count = 0
for i in range(4):
    for j in range(i + 1):
        count += 1
print(count)
```

* [ ] 4
  > Esse é o número de voltas do laço de fora. O de dentro roda várias vezes.
* [ ] 6
  > Faltou contar uma volta em cada linha: o laço interno roda `i + 1` vezes, não `i`.
* [*] 10
  > O laço interno roda 1, 2, 3 e 4 vezes, e 1 + 2 + 3 + 4 = 10.
* [ ] 16
  > Seriam 16 voltas se o laço interno sempre rodasse 4 vezes, mas o limite depende de `i`.
