---
title: "Formato do recorde (rascunho)"
description: "Rascunho da professora: guardar os cinco maiores recordes, com nome e data."
---

# Formato do recorde (rascunho)

Rascunho para a aula 13. Em vez de um número só, o arquivo guarda os cinco
maiores recordes, cada um com nome, pontos e data.

```json
{
  "recordes": [
    {"nome": "Ada", "pontos": 120, "data": "2026-11-02"},
    {"nome": "Alan", "pontos": 95, "data": "2026-11-02"}
  ]
}
```

Pontos em aberto:

- Datas em formato ISO (`AAAA-MM-DD`) ordenam como texto, o que ajuda.
- Ordenar por `pontos`, do maior para o menor, antes de gravar.
- Decidir se o exemplo da aula já usa a lista, ou se fica para o projeto.
