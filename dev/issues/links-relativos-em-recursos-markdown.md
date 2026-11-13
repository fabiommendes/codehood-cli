---
type: issue
status: todo
tags: [codehood-cli, push, resources, markdown, links]
relatedTo: [resources, questions]
---

# Push mantém caminhos locais nos links internos de recursos Markdown

## Problema

Links internos escritos em um recurso `.md` podem continuar apontando para
caminhos do sistema de arquivos depois de `ch push`, em vez de apontarem para
as páginas dos objetos publicados no Codehood. O arquivo existe no repositório,
mas o aluno não consegue abrir o destino a partir da nota publicada.

O caso observado é um recurso Markdown que aponta para questões do curso.
A associação de recursos à aula por links em `calendar.md` funciona; essa
reescrita não resolve os links de dentro da nota para as questões.

## Reprodução

No curso `paradigmas`, edição `2026-2`, o arquivo
`resources/prolog/aula-introducao-ao-prolog/notas.md` contém:

```markdown
## Exercícios

* [Fatos válidos em Prolog](../../../questions/logico/sintaxe/fatos-validos.md).
* [Regra para definir pai](../../../questions/logico/sintaxe/regra-pai.md).
* [Termos e cláusulas](../../../questions/logico/sintaxe/termos-e-clausulas.md).
* [Árvore genealógica](../../../questions/logico/sintaxe/arvore-genealogica.md).
```

1. Manter essa seção visível em uma nota sob `resources/`.
2. Garantir que as questões de destino também sejam publicadas.
3. Executar `ch push --no-prune`.
4. Abrir a nota publicada e seguir um dos links.

O destino permanece, por exemplo,
`../../../questions/logico/sintaxe/fatos-validos.md`. Esse caminho é relativo
à pasta da nota no repositório, não à rota da página publicada. O navegador
não chega à questão correspondente.

A seção está temporariamente oculta por definições de referência Markdown,
uma por linha, no formato `[//]: # "conteúdo"`. Retirar esse invólucro para
reproduzir o caso com o mesmo material.

Comentários HTML não servem como alternativa no renderizador atual: ele usa
MarkdownIt com `html: false`, então `<!-- ... -->` é exibido como texto e não
oculta os exercícios nem seus links.

## Comportamento esperado

Durante o push, resolver o caminho em relação à pasta do arquivo Markdown
que contém o link, identificar o objeto publicado correspondente e substituir
o destino pela URL desse objeto no curso e na edição corretos. Usar a mesma
identidade e o mesmo slug que a publicação do destino usa; não deduzir a URL
apenas removendo a extensão ou copiando o caminho local.

Os arquivos locais devem manter os links relativos originais. A conversão
pertence ao conteúdo enviado ao servidor.

## Critérios de aceite

- Links relativos de recursos Markdown para questões publicadas levam às
  páginas corretas, inclusive quando incluem `../`.
- Links entre recursos Markdown e exemplos publicados também são cobertos,
  sem regressão da associação feita pelo calendário.
- Âncoras e parâmetros de consulta são preservados quando aplicáveis.
- Links externos, âncoras locais, trechos de código e comentários HTML não
  são reescritos.
- Destinos inexistentes, excluídos do push ou sem objeto publicável recebem
  diagnóstico explícito; não se fabrica uma URL aparentemente válida.
- O push não modifica os arquivos Markdown locais.
- Testes verificam o conteúdo efetivamente enviado ao servidor, além da
  resolução dos caminhos. Incluir o caminho real da reprodução acima.

## Ponto de investigação

Verificar `codehood/push/links.py`, especialmente `rewrite_body_links`, e sua
chamada em `codehood/cli/push.py:read_local_state`. Conferir se o mapeamento
usado na reescrita inclui questões, além de recursos, e se resolve caminhos
relativos à origem do Markdown. Não restringir a correção aos links do
`calendar.md`, que já funcionam neste caso.
