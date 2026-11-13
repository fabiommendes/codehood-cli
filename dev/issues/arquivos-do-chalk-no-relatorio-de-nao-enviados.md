---
type: issue
status: in_review
kind: feature
priority: low
tags: [cli, push, chalk]
creator: claude
---

# Arquivos do chalk poluem o relatório "not pushed (no handler)"

Teste de convivência em `~/aulas/paradigmas/ch` com um projeto chalk na mesma pasta (`chalk init`, um quiz `p1/`, `chalk codehood grades`). O fluxo de notas funciona: `grades.csv` escrito pelo chalk é lido pelo `codehood grades` e o push planeja a coluna `p1`. Mas todo push passa a listar:

```
not pushed (no handler): chalk.toml
not pushed (no handler): p1/conf.yaml
not pushed (no handler): p1/grades.csv
not pushed (no handler): p1/submissions.csv
not pushed (no handler): roster.csv
```

Com vários quizzes, a lista cresce e esconde o que importa (um arquivo do curso esquecido fora de `questions/` ou `resources/`).

`roster.csv` é um caso à parte: `file_tracker.scan_files` já o classifica como `FileType.ROSTER`, mas não há handler até existir `codehood roster` (ROADMAP).

## Proposta

Uma das duas, ou ambas:

1. `[push] ignore = ["chalk.toml", "p*/"]` em `codehood.toml`: padrões que saem do relatório sem efeito no servidor (diferente de `exclude`, que protege a cópia remota).
2. Reconhecer um projeto chalk (`chalk.toml` na raiz) e agrupar seus arquivos numa linha só, por exemplo `not pushed: chalk project (chalk.toml, 1 quiz)`.

Para `roster.csv`, trocar "no handler" por algo como `roster.csv: not synced yet (codehood roster)`, ou não listar.
