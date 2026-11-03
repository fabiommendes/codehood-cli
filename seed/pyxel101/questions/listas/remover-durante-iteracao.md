---
title: Remover itens durante o for
tags: [listas, lacos, armadilhas]
locale: pt-BR
weight: 2
---

O programa abaixo deveria esvaziar a lista de gotas, mas termina com a lista
`[2, 4]`.

```python
gotas = [1, 2, 3, 4]
for gota in gotas:
    gotas.remove(gota)
print(gotas)
```

Explique por que a lista não fica vazia e mostre duas formas corretas de remover os
itens que atendem a uma condição.

[essay]

## [answer-key]

O `for` percorre a lista por posição interna. Quando `remove` tira um item, os
seguintes andam uma posição para trás, e o laço avança para a posição seguinte, pulando
um elemento. Com `[1, 2, 3, 4]`: remove o 1, o laço vai à posição 1, que agora é o 3;
remove o 3, a lista vira `[2, 4]` e o laço termina, porque a posição 2 não existe mais.

Formas corretas, qualquer duas:

```python
# 1. construir uma lista nova com os que ficam
gotas = [g for g in gotas if not saiu_da_tela(g)]

# 2. iterar sobre uma cópia
for gota in gotas[:]:
    if saiu_da_tela(gota):
        gotas.remove(gota)

# 3. iterar de trás para frente, por índice
for i in range(len(gotas) - 1, -1, -1):
    if saiu_da_tela(gotas[i]):
        del gotas[i]
```

Aceitar também `gotas.clear()` quando a intenção é esvaziar tudo. Descontar a
resposta que só diz "dá erro", porque não há exceção, apenas um resultado errado.
