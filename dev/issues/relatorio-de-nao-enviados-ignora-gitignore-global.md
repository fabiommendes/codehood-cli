---
type: issue
status: in_review
kind: bug
priority: low
tags: [cli, push]
creator: claude
---

# O relatório "not pushed (no handler)" ignora o gitignore global e o `.git/info/exclude`

`codehood push --dry-run` em `~/aulas/paradigmas/ch` lista:

```
not pushed (no handler): .claude/settings.local.json
```

O arquivo é ignorado pelo git através de `~/.config/git/ignore` (`git check-ignore -v` confirma). `codehood/push/unconsumed.py:list_files` lê só o `.gitignore` da raiz, então arquivos ignorados por `core.excludesFile`, `.git/info/exclude` ou `.gitignore` de subpastas aparecem como não enviados.

## Comportamento desejado

Considerar as mesmas regras do git. Quando o curso é um repositório git, `git ls-files --cached --others --exclude-standard` dá a lista certa, inclusive de arquivos ainda não commitados. Fora de um repositório git, manter o comportamento atual.

## Critérios de aceite

- Arquivo ignorado só pelo gitignore global não aparece no relatório.
- Arquivo novo, não commitado e não ignorado continua aparecendo.
