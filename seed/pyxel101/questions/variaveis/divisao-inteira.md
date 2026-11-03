---
title: Blocos cheios da barra de vida
tags: [variaveis, operadores]
locale: pt-BR
domain: integer
incorrectFeedback: Use a divisão inteira `//`, que descarta a parte fracionária. A divisão `17 / 5` daria 3.4, mas só contam os blocos cheios.
---

A barra de vida do jogador mostra um bloco para cada 5 pontos de vida. O jogador
tem 17 pontos, e o programa calcula os blocos cheios assim:

```python
blocos_cheios = 17 // 5
```

Qual é o valor de `blocos_cheios`?

[numeric]: 3
