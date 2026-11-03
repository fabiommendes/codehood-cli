---
type: doc
status: active
tags: [seed, gaps, cli, push]
relatedTo: [seed-cli-pyxel101]
---

# Lacunas medidas pelo curso `pyxel101`

O curso em `pyxel101/` foi escrito como um professor gostaria de dar, não em
torno do que o Codehood já faz. Cada linha abaixo é uma diferença entre o que
o material pede e o que `pnpm run db:seed:cli` produz no servidor.

Este documento é temporário. Quando uma lacuna vira issue ou spec, a coluna
"Estado" aponta para ela. Quando é resolvida, a linha sai. Quando as tabelas
esvaziarem, o arquivo é apagado.

Os desejos `W1` a `W14` estão na spec `dev/specs/to-review/seed-cli-pyxel101.md`
(R18). "Formato proposto" quer dizer que o arquivo usa um formato inventado
para o desejo ficar concreto. Ele não foi decidido e pode mudar quando a
lacuna for atacada. "Onde" diz quem precisa mudar: `cli`, `server`, `mdq` ou
`desenho` (`cli/docs/design/mapping-local-filesystem.md`).

Último push medido: 2026-11-03, `186 operation(s) executed, 32 failed, 0
skipped, 5 excluded`, mais 22 arquivos `not pushed (no handler)`.

## Recursos

| G | W | Onde | Arquivos | Esperado | Observado | Estado |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| G1 | W1, W2, W14 | server, cli | 12 PNG, 13 PDF, `semana-11/personagem.pyxres` | Sobem como `FILE` e abrem no navegador | 26 falhas `blocked: the server accepts no FILE upload yet`; a CLI recusa antes de enviar | issue `dev/issues/recurso-file-pede-buffer-em-rota-json.md`; `cli/ROADBLOCKS.md` (1ª entrada) |
| G2 | W3 | cli | 6 `resources/**/*.url` | Viram `LINK`, título e descrição dos comentários (mapping doc) | A CLI não conhece `.url`: viram `FILE` e caem em G1 | `cli/BACKLOG.md`, "Resource manifest" |
| G3 | W2, W3 | cli | `calendar.md` | Link de aula para recurso que não subiu é avisado ou omitido | O link publicado leva a uma página 404, sem aviso no push | aberta |
| G4 | W1 | cli | `resources/**/notas.md`, `resources/projeto/enunciado.md` | Links e imagens relativos dentro de um MD apontam para os recursos no servidor | Vão crus: `<img src="repl.png">`, `[rubrica](rubrica.md)` dão 404. Só as descrições de aula são reescritas | aberta |
| G5 | -- | cli, desenho | `resources/semana-{01,05,11}/info.yaml` | Metadado da pasta, não recurso (mapping doc) | Sobem como `CODE` (`yaml`) e os metadados são ignorados. O `cli/BACKLOG.md` propõe `resources.toml` para o mesmo fim: dois desenhos | `cli/BACKLOG.md`, "Resource manifest" |
| G6 | W1, W3 | cli | `.py` e MD sem `title` em `resources/` | Título legível (fallback em title case do mapping doc) | Título é o nome cru do arquivo: `janela-minima`, `bola-jogavel` | aberta |
| G7 | W4 | cli, server | `resources/semana-05/bola-jogavel.html` | Exemplo jogável no navegador | Sobe como `CODE` e mostra o fonte. Mesmo como `FILE`, falta o servidor exibir HTML isolado (iframe) | aberta |
| G8 | W11 | cli, server | `semana-05/gabarito-lab05.md`, `provas/gabarito-prova*.md` (`release: after-lesson`, formato proposto) | Visível só depois da aula ou da prova | Publicado na hora. A CLI só lê `title`/`description`, e o servidor não tem visibilidade agendada de recurso | aberta |
| G9 | W2 | cli, server, desenho | um recurso citado em duas aulas | O mesmo material aparece nas duas aulas | `ResourceLinkError` aborta o push; `Resource.eventId` é único. O curso evita o caso | aberta |

## Questões e provas

| G | W | Onde | Arquivos | Esperado | Observado | Estado |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| G10 | W6, W7 | cli | `exams/*.md`, `exams/practice/quiz-semanal.md` | Provas e quiz sobem | `not pushed (no handler)` | spec `cli/dev/specs/to-do/push-exams.md` |
| G11 | W6, W7 | server | `exams/*.md` (`shuffle`, `grading`, `penalty`, `includeAll` + `max`) | O servidor sorteia, embaralha e aplica penalidade | `examSchema` não tem esses campos; `questions` é lista fixa | aberta; ver `dev/issues/embaralhar-escolhas.md` |
| G12 | W7 | mdq, server | `exams/prova*.md` (`meta: {release: after-end}`) | Gabarito liberado depois da prova | O mdq rejeita `release` no topo; o curso usa `meta:` | issue `dev/issues/aluno-ve-gabarito-apos-liberacao.md` |
| G13 | W7 | server, cli | `calendar.md` `## Prova 1` + `exams/prova1.md` `start:` | A aula da prova aponta para a prova; a data fica num lugar só | Sem relação prova↔evento. A spec push-exams lê `start` sem fuso como UTC: a prova cairia 3h antes do evento | aberta |
| G14 | W8 | mdq | `questions/código/*.md` (formato proposto) | Questão de código com testes ocultos e correção automática | O mdq não tem o tipo; excluídas no `codehood.toml`. `prova2` inclui duas delas e vai falhar quando G10 existir | aberta |
| G15 | -- | cli | qualquer questão inválida | A questão inválida falha sozinha e o resto sobe | O push inteiro aborta em `QuestionParseError` (motivo da exclusão em G14) | aberta |
| G16 | -- | cli | `questions/laços/*`, `classes/herança.md`, `condicionais/condição-dupla.md` | Slug translitera acentos (`lacos-...`, `heranca`), como `src/utils/slugify.ts` (NFKD sem diacríticos) | Acento vira hífen: `la-os-passos-do-range`, `classes-heran-a` | aberta |
| G16b | -- | cli | questões com `id:` no front matter | `id:` define o slug (mapping doc) | `scan_questions` ignora `id:`; o slug vem só do caminho. O curso não usa `id:` por causa disso | aberta |
| G17 | W6, W7 | cli | todas as questões | Questão sem `_` no nome sobe `PUBLISHED` (mapping doc) | As 42 sobem `DRAFT` | issue `cli/dev/issues/question-status-divergence.md` |
| G18 | -- | cli | `ch init`, `cli/tests/examples/*/exams` | O modelo de prova usa `start`/`duration`, que o mdq e a spec push-exams leem | Gera `meta.codehood.scheduled_at`/`duration_min` | aberta |

## Agenda

| G | W | Onde | Arquivos | Esperado | Observado | Estado |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| G19 | W10 | desenho | `calendar.md`, horário de atendimento | Horário recorrente sem conteúdo por ocorrência | Cada ocorrência consome uma seção `##`: 14 seções "Atendimento", 12 só de enchimento | aberta |
| G20 | W10 | desenho | `calendar.md`, aula 5 cancelada | Aula marcada como cancelada no repositório, com reposição | Sobe `REGULAR` com o texto "cancelada" | por desenho: `CANCELLED` é do servidor (mapping doc, "Calendar events") |

## Notas, entregas e projeto

| G | W | Onde | Arquivos | Esperado | Observado | Estado |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| G21 | W5 | server | `repositories/lab*/`, `solutions/*/` (`tests_ocultos/`, `autograde.toml`, formato proposto) | Aluno entrega por git; testes ocultos rodam e dão nota | `solutions/` não é consumido; o Codehood não recebe entrega por git nem roda testes | issue `dev/issues/entrega-por-git.md`; `dev/specs/to-review/auto-grading.md` cobre só questões mdq |
| G22 | W5 | server | `README.md` (nota máxima de 70% após o prazo) | Entrega atrasada com desconto | Entrega fora do prazo é recusada | issue `dev/issues/politica-de-atraso.md` |
| G23 | W9 | server | `repositories/projeto-final/`, `RUBRICA.md` (formato proposto) | Projeto em grupo: repositório por grupo, rubrica, banca agendada | Só existe repositório da turma; sem grupos nem rubrica | aberta |
| G24 | W12 | cli | `grades.py` | `student.attendance` vem do roll call do servidor; `labs` vem da correção automática | `codehood.grades.Student` não expõe presença, embora o servidor tenha `Attendance`; `grades.py` lê a frequência de uma coluna do CSV | aberta |
| G25 | W12 | cli | `codehood.toml` | Regra de aprovação (frequência mínima) declarada no curso | `codehood.toml` rejeita chaves extras; a regra mora no `grades.py` | aberta |

## Curso e push

| G | W | Onde | Arquivos | Esperado | Observado | Estado |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| G26 | -- | cli, desenho | `README.md` | A descrição do curso é o README (mapping doc, "Course") | Só o 1º parágrafo sobe; avaliação, bibliografia e política somem | aberta |
| G27 | W13 | server | `avisos/*.md` (formato proposto) | Avisos da disciplina com data e destaque | `not pushed (no handler)`; o Codehood não tem avisos | aberta |
| G28 | -- | desenho | `resources/semana-10/aabb.py` + `aabb.png` (renomeado `aabb-diagrama.png`) | Código e diagrama de mesmo nome convivem na pasta | `error: colliding slugs` aborta o push | por desenho: o slug tira a extensão e colisão é erro (mapping doc, "Resource") |
| G29 | -- | desenho | todo o curso | O segundo push sem mudanças não executa nada | Sempre refaz `upsert course` | por desenho: o curso não tem hash comparável (`plan.py`, `plan_push`) |

## Verificado, sem lacuna

- Feedback por alternativa (`>`) chega ao servidor em 39 de 42 questões
  (`choices[].feedback`, `incorrectFeedback`). Comentários `!` não foram
  exercitados. Também não foi conferido se o aluno vê o feedback na tela.
- `weight:` das questões é preservado.
- Repositórios: `scripts/run.sh` com `100755`, `.pyxres`, PNG e
  `.gitignore` aninhado chegam ao clone.
- Feriado e reposição do `calendar.md` viram `HOLIDAY` e evento na data fixa.

## Cobertura dos desejos

| W | Lacunas | Situação |
| :-- | :-- | :-- |
| W1 | G1, G4, G6 | não funciona |
| W2 | G1, G3, G9 | não funciona |
| W3 | G2, G3, G6 | não funciona |
| W4 | G7 | não funciona |
| W5 | G21, G22 | não funciona; starters sobem |
| W6 | G10, G11, G17 | não funciona |
| W7 | G10 a G13, G17 | não funciona |
| W8 | G14 | não funciona |
| W9 | G23 | não funciona; template sobe |
| W10 | G19, G20 | parcial: horários, feriado e reposição funcionam |
| W11 | G8 | não funciona |
| W12 | G24, G25 | parcial: colunas e `grades.py` funcionam |
| W13 | G27 | não funciona |
| W14 | G1 | funciona nos repositórios; `.pyxres` como recurso cai em G1 |
