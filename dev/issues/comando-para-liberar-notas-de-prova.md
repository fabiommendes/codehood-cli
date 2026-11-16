---
type: issue
status: backlog
tags: [exam, grades, api]
kind: enhancement
priority: medium
created: 2026-11-16
creator: claude
---

# Comando para liberar as notas de uma prova

O servidor ganhou uma rota de comando para liberar as notas de uma prova:

```
POST /api/course/<disciplina>/<curso>/exam/<prova>/release
```

O snapshot OpenAPI e o `codehood/api/generated.py` são regenerados no mesmo
commit do servidor. Falta o comando na CLI.

## Contrato da rota

- 200: devolve a prova no formato de leitura, com `gradesReleasedAt`
  preenchido. É idempotente: liberar de novo uma prova já liberada devolve 200
  e mantém a data da primeira liberação.
- 409: não dá para liberar ainda. O corpo traz o motivo (`not-closed`,
  `pending`, `exception-open` ou `not-an-exam`) e os números: respostas sem nota
  e exceções abertas. Os nomes exatos dos campos estão no snapshot OpenAPI.
- 403: só o professor do curso libera. O token da CLI do professor pode; tokens
  de bot de correção não.
- 404: curso ou prova inexistente.

## O que falta na CLI

- Um comando como `codehood exam release <prova>`, no mesmo grupo dos outros
  comandos de prova.
- Ao receber 409, mostrar o motivo de forma legível, com os números (por
  exemplo, "12 respostas ainda sem nota"). Para `not-closed`, lembrar que a
  prova pode ser encerrada com `PATCH` de status `COMPLETED`, que também fecha
  as tentativas abertas.
- Testes com o cliente gerado.
