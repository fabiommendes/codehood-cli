---
title: Lendo o recorde
tags: [arquivos, json, semanal]
locale: pt-BR
---

O recorde do jogo fica em `recorde.json`. Veja a leitura:

```python
import json

with open("recorde.json", encoding="utf-8") as f:
    best = json.load(f)
```

O bloco [^bloco] fecha o arquivo automaticamente ao sair, mesmo se ocorrer um erro. Para
converter o conteúdo do arquivo `f` em um valor Python, usamos a função json.[^funcao]
passando o arquivo, e não um texto.

[^bloco/short-answer]: with

[^funcao/short-answer]:
* load
  > `json.load` lê de um arquivo aberto.

[^funcao/short-answer/reject]:
* loads
  > `json.loads` (com "s" de *string*) lê de um texto. Para um arquivo aberto, use `load`.
