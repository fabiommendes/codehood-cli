---
title: Chave ausente
tags: [dicionarios, erros]
locale: pt-BR
shuffle: true
---

O que acontece ao executar o programa abaixo?

```python
state = {"tela": "titulo", "pontos": 0}
print(state.get("vidas", 3))
print(state["vidas"])
```

* [ ] Imprime `3` e depois `None`.
  > `state["vidas"]` não devolve `None` para chave ausente: ele levanta `KeyError`.
* [*] Imprime `3` e depois termina com `KeyError`.
  > `get` aceita um valor padrão e não altera o dicionário. O acesso por colchetes
  > exige que a chave exista.
* [ ] Termina com `KeyError` já na primeira linha.
  > `get` nunca levanta `KeyError`. Se a chave faltar, devolve o padrão.
* [ ] Imprime `3` e depois `3`, porque o `get` cria a chave `"vidas"`.
  > `get` só lê, ele não cria chaves. Para isso existe `setdefault`.
