---
type: doc
status: active
tags: [seed, cli, push, dev-server, course-repository]
relatedTo: [seed-cli-pyxel101]
---

# Seed da CLI

`pyxel101/` é o repositório de um curso completo, "Introdução à Programação
com Python e Jogos", da `ada`: 16 semanas com notas de aula, exemplos,
slides, links, um banco de questões, provas, laboratórios com testes e um
`grades.py`. Ele foi escrito como um professor gostaria de dar o curso, não
em torno do que o Codehood já suporta. Por isso o push não sai limpo, e as
diferenças ficam registradas em [GAPS.md](GAPS.md).

O curso não tem alunos. Matrículas, entregas e notas ficam no seed normal do
servidor.

## Subir o curso

Com o banco semeado e o dev server no ar:

```bash
pnpm run db:reset        # se o banco ainda não tem a disciplina pyxel101
pnpm run dev
pnpm run db:seed:cli     # em outro terminal
```

O comando:

1. recria `tmp/pyxel101/` (na raiz do servidor, ignorado pelo git) a partir
   de `cli/seed/pyxel101/`;
2. troca a edição do `codehood.toml` pela edição atual do seed e desloca as
   datas de `calendar.md` e `exams/` em semanas inteiras;
3. roda `ch push` na cópia, como `ada`.

Ele sai com 0 quando o push chega ao fim, mesmo com operações falhas, porque
essas falhas são as lacunas medidas. Sai com erro só quando o push aborta.

## Usar o `ch` à mão

`tmp/pyxel101/` é um lugar para exercitar a CLI: edite, rode `ch push`,
`ch push --dry-run`, `ch grades`. O seed cria para a `ada` uma chave fixa,
`dev-ada-cli`:

```bash
cd tmp/pyxel101
CODEHOOD_TOKEN=dev-ada-cli uv run --project ../../cli ch push
```

Também dá para fazer `ch login` com `ada`/`ada`.

A pasta é apagada e recriada a cada `pnpm run db:seed:cli`. Uma mudança que
deve ficar vai para `cli/seed/pyxel101/`.

## Arquivos

| Arquivo | Conteúdo |
| :-- | :-- |
| `pyxel101/` | O curso. |
| `pyxel101/solutions/` | Soluções de referência e testes ocultos dos labs. O push não lê esta pasta. |
| `GAPS.md` | Lacunas entre o que o curso pede e o que o push produz. Temporário. |
| `INVENTORY.md` | Lista de cada arquivo do curso, o que ele ensina e qual desejo exercita. |
| `tools/` | Geradores dos binários (PNG, PDF, `.pyxres`, HTML jogável). |

Para regenerar os binários, a partir de `cli/seed/`:

```bash
uv run --with pillow --with pyxel python tools/make_assets.py
uv run --with pyxel python tools/make_lab_assets.py
tools/make_html.sh
```
