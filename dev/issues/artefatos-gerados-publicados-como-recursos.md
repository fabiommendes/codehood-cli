---
type: issue
status: backlog
kind: bug
priority: medium
tags: [cli, push, resources, python, elm]
creator: claude
---

# Evitar a publicação acidental de caches e artefatos gerados em resources

## Problema observado

Durante a migração da aula de programação funcional, os testes importaram os
exemplos Python e criaram três arquivos `.pyc` em
`resources/elm/aula-programacao-funcional/exemplos/__pycache__/`.

`read_local_state` passou a retornar esses três arquivos como recursos `FILE`,
sem evento associado, além dos sete recursos didáticos esperados. Eles foram
removidos antes do push e não foram publicados.

Executar ou validar exemplos não deveria acrescentar silenciosamente caches à
lista de materiais publicados. Projetos Elm também geram `elm-stuff/`; projetos
Node podem trazer `node_modules/` e diretórios de build. Esses casos precisam de
uma política explícita de inclusão e exclusão.

## Causa

- `codehood/repo/file_tracker.py:scan_files` percorre todos os arquivos de
  `resources/` com `rglob`, aplicando apenas os padrões de `[push].exclude`.
- `codehood/push/resource.py` transforma extensões desconhecidas em `FILE`.
- Não há proteção específica contra caches de execução. Não se deve supor que
  o `.gitignore` proteja o push, pois o scanner não o consulta.

## Reprodução sem publicar nada

1. Criar `resources/aula/exemplo.py` e importar o módulo com Python, sem definir
   `PYTHONDONTWRITEBYTECODE`.
2. Chamar `read_local_state` ou `ch push --dry-run`.
3. Observar os arquivos de `__pycache__/` na lista/plano de recursos, mesmo sem
   links correspondentes no calendário.

## Comportamento desejado

Definir uma política para ignorar artefatos gerados comuns ou avisar antes de
incluí-los. Avaliar exclusões padrão para `__pycache__/`, `*.pyc`, `elm-stuff/`
e `node_modules/`, com opção explícita para materiais que precisem publicá-los.
Não ignorar todos os arquivos não rastreados no Git: exemplos novos ainda sem
commit fazem parte do fluxo normal de preparação do curso.

A mudança deve respeitar a proteção de recursos remotos excluídos, sem
transformar uma nova regra de exclusão numa exclusão remota por prune.

## Workarounds usados

- Rodar testes Python com `PYTHONDONTWRITEBYTECODE=1` e remover caches gerados
  antes de ler o estado local.
- Compilar os projetos Elm numa cópia temporária fora de `resources/`.
- O curso também pode declarar padrões em `[push].exclude`; isso não é
  equivalente a manter arquivos fora do Git.

## Critérios de aceite

- Testar que importar um exemplo Python não acrescenta `.pyc` aos recursos.
- Testar a política de `elm-stuff/` e `node_modules/`.
- Continuar descobrindo recursos didáticos novos ainda não commitados.
- Manter funcionando as exclusões explícitas e a proteção contra prune.
- Se houver publicação deliberada de artefatos, exigir configuração explícita.
