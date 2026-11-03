---
title: Estado do jogo em um dicionário
tags: [dicionarios, estado, semanal]
locale: pt-BR
---

O estado de um jogo é guardado em um dicionário.

```python
state = {"tela": "titulo", "pontos": 0, "vidas": 3, "jogador": (80, 100)}
```

Marque as afirmações corretas.

* [x] `state["pontos"] += 10` soma 10 ao placar.
* [ ] `state["jogador"][0] = 90` move o jogador para `x = 90`.
  > O valor de `"jogador"` é uma tupla e não aceita atribuição por índice.
* [x] `state["jogador"] = (90, 100)` move o jogador, trocando a tupla inteira.
* [x] `"vidas" in state` vale `True`.
  > O operador `in` testa as chaves do dicionário.
* [ ] `state[0]` devolve `"titulo"`, o primeiro valor.
  > Dicionários são acessados por chave, não por posição. Aqui haveria `KeyError`.
* [ ] `state.tela` lê a tela atual.
  > Dicionários não expõem as chaves como atributos. O correto é `state["tela"]`.
