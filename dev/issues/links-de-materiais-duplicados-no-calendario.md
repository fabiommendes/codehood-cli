---
type: issue
status: todo
tags: [codehood-cli, push, calendar, resources, markdown]
relatedTo: [calendar, resources]
---

# Separar os vínculos de materiais da descrição renderizada das aulas

## Problema

Um link para um arquivo de `resources/` dentro de uma aula do `calendar.md`
exerce dois papéis no push:

1. Faz parte da descrição Markdown publicada para a aula.
2. Associa o recurso ao evento, para aparecer na lista de materiais da aula.

Na página do curso, os mesmos materiais acabam aparecendo duas vezes: nos
links da descrição renderizada em HTML e na lista de recursos associados.

## Reprodução

No curso `paradigmas`, a entrada "Introdução ao Prolog" contém:

```markdown
## Introdução ao Prolog

* Sintaxe do Prolog.
* Variáveis, átomos e números.

### Material da aula

* [Notas de aula](resources/prolog/aula-introducao-ao-prolog/notas.md).
* [Primeiro programa](resources/prolog/aula-introducao-ao-prolog/exemplos/hello.pl).
```

Depois de `ch push`, os dois links aparecem tanto no conteúdo da descrição
quanto na lista de recursos do evento.

## Comportamento esperado

Definir uma convenção explícita para marcar, no `calendar.md`, um bloco de
vínculos a materiais. O CLI deve usar esses vínculos para associar os objetos
à aula, mas retirar o bloco da descrição Markdown enviada ao servidor.

Não remover automaticamente todos os links de uma descrição: um link no meio
da explicação pode ser intencional. O bloco reservado deve distinguir os
vínculos usados como metadados dos links que fazem parte do texto da aula.

## Proposta de convenção

Usar um comentário HTML reservado, com o marcador `codehood:materials`:

```markdown
## Introdução ao Prolog

* Sintaxe do Prolog.
* Variáveis, átomos e números.

<!-- codehood:materials
* [Notas de aula](resources/prolog/aula-introducao-ao-prolog/notas.md)
* [Primeiro programa](resources/prolog/aula-introducao-ao-prolog/exemplos/hello.pl)
-->
```

Esta é uma proposta para avaliação, não uma sintaxe já implementada. O bloco
fica oculto também na renderização comum de Markdown. Durante o push, o CLI
extrai os vínculos desse comentário específico antes de descartá-lo da cópia
publicada. Comentários HTML comuns continuam sendo ignorados na extração.

A alternativa é um bloco de metadados próprio por aula. Escolher e documentar
uma única sintaxe antes de implementar; não usar o título livre "Material da
aula" como delimitador implícito.

## Critérios de aceite

- Os vínculos do bloco reservado associam os recursos ao evento correto.
- O bloco inteiro, incluindo seu marcador, não aparece na descrição Markdown
  enviada ao servidor nem no HTML renderizado da página do curso.
- Os recursos aparecem uma única vez, na lista de materiais associados.
- Links fora do bloco continuam aparecendo normalmente na descrição.
- A ausência do bloco preserva o comportamento dos calendários existentes;
  a migração para a nova convenção é explícita.
- Continuam válidas as verificações de destino inexistente, arquivo excluído
  e recurso associado a mais de uma aula.
- Comentários HTML comuns e exemplos de sintaxe dentro de blocos de código
  não são interpretados como declarações de materiais.
- Um bloco malformado gera diagnóstico com a aula de origem, sem consumir o
  texto da aula seguinte.
- O push não modifica o `calendar.md` local.
- Documentar o formato e atualizar o exemplo de calendário do scaffold.
- Testes cobrem a extração, a associação e o payload final publicado, além de
  uma verificação de que a página do curso não duplica os materiais.

## Ponto de investigação

A associação e a descrição são derivadas atualmente do mesmo texto. Verificar
`codehood/push/calendar.py`, `codehood/push/links.py` e a montagem do estado
local em `codehood/cli/push.py`. Separar a extração dos vínculos da produção da
descrição publicada, para não perder as associações ao remover o bloco.

## Escopo

Esta issue trata da duplicação dos materiais de uma aula no calendário. A
resolução de links internos de recursos Markdown para objetos publicados é
outro problema, registrado em `links-relativos-em-recursos-markdown.md`.
