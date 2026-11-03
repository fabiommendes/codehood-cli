---
title: Fatiamento
tags: [listas, fatiamento, semanal]
locale: pt-BR
incorrectFeedback: Na fatia `[início:fim]`, o início é incluído e o fim não. Os índices começam em 0.
---

Que lista é o resultado de `values[1:4]`?

```python
values = [5, 10, 15, 20, 25]
```

[short-answer]:
* /\[?\s*10\s*,\s*15\s*,\s*20\s*\]?/
  > Isso mesmo: os índices 1, 2 e 3.

[short-answer/reject]:
* /\[?\s*10\s*,\s*15\s*,\s*20\s*,\s*25\s*\]?/
  > O índice final 4 não é incluído na fatia.
* /\[?\s*5\s*,\s*10\s*,\s*15\s*,\s*20\s*\]?/
  > A fatia começa no índice 1, que é o segundo elemento.
