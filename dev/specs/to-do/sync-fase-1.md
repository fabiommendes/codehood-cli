# Sync bidirecional, fase 1: detectar e não sobrescrever

Desenho completo e justificativas: `../../../../dev/rfc/sync-bidirecional.md`
(na raiz do servidor). Esta spec cobre só a fase 1 e a divide em tarefas.

## Resultado

`ch push` deixa de tratar o repositório como única fonte de verdade. Ele
compara local, base e servidor, envia só o que mudou localmente, e mostra sem
tocar o que mudou no servidor. Nada é escrito nos arquivos do curso nesta
fase: `ch pull` e `ch sync` ficam para a fase 2.

## Requisitos

- R1. O estado local fica em `.local/codehood/`, com um `.gitignore` interno
  contendo `*`. `ch init` cria esse diretório e não cria mais `.codehood/`.
  Um `.codehood/` existente é ignorado pelo scan de arquivos não consumidos,
  como hoje, e pode ser apagado pelo usuário.
- R2. A base guarda, por coleção e por chave natural, o payload enviado no
  último sync bem-sucedido, o `rev` e o `updatedAt` do servidor. A gravação é
  atômica (arquivo temporário e rename). Um arquivo ilegível equivale a base
  ausente, com aviso.
- R3. Cada tipo de recurso sincronizado tem uma projeção
  `read model -> payload` tal que, para todo payload `p` aceito pelo servidor,
  `project(GET depois de PUT p) == p`. Vale para curso, recurso, questão,
  time slot, evento e coluna de nota. Documentos de questão são comparados
  normalizados.
- R4. `plan_sync(local, base, remote)` é pura e implementa a tabela de decisão
  e os casos especiais da RFC (seções "Três vias com base local" e "Mudança
  vinda de outra CLI"). Decisões novas: `Pull`, `Conflict` e `OtherCli`.
- R5. Base ausente para uma entidade: `server.rev` igual ao hash local adota
  como base; diferente é `Conflict`.
- R6. `ch push` executa `Put` e `Prune`. `Pull`, `Conflict` e `OtherCli` são
  mostrados e a entidade fica intocada dos dois lados. Uma entidade criada no
  servidor nunca é podada.
- R7. A base só é atualizada para as entidades cuja operação deu certo, e para
  as que estavam iguais dos dois lados.
- R8. `--ours <glob>` resolve um `Conflict` enviando a versão local.
  `--theirs` não existe nesta fase.
- R9. O relatório em texto lista cada `Pull`, `Conflict` e `OtherCli` com a
  chave, o tipo e os campos que diferem. `OtherCli` sugere `git pull`. O
  código de saída é diferente de zero quando sobra `Conflict`.
- R10. O status de questão continua regido por `join_status`, fora da
  comparação. `InvalidQuestion` continua `Keep`. Arquivo em `[push] exclude`
  é sempre `Skip`.
- R11. Mudança no vínculo recurso-aula e remoção no servidor de um recurso
  ainda referenciado localmente são `Conflict`.
- R12. `--dry-run`, `--no-prune`, `--drop-roll-calls` e `--drop-repositories`
  mantêm o comportamento atual. Repositórios e colunas de nota continuam em
  sentido único: mudança no servidor é sobrescrita, como hoje, com aviso.

## Tipos compartilhados

Definidos em T1 e T2 e consumidos por T3. Os nomes são os desta lista.

- `BaseEntry`: `payload`, `rev: str | None`, `updated_at: str | None`.
- `BaseState`: uma coleção `dict[str, BaseEntry]` por tipo de recurso.
- `RemoteEntry`: `payload`, `rev`, `updated_at`.
- `ServerState` passa a carregar `RemoteEntry` por chave em vez de marcadores.
- `Decision` ganha `Pull`, `Conflict` e `OtherCli`, cada uma com a chave e a
  lista de campos que diferem.

## Tarefas

| Id | Tarefa | Depende de | Módulos |
| :- | :----- | :--------- | :------ |
| T1 | Diretório `.local/codehood/` e armazenamento da base (R1, R2) | nenhuma | `repo/_scaffold.py`, `repo/_layout.py`, `push/unconsumed.py`, novo `push/base.py` |
| T2 | Projeções `read model -> payload` e `fetch_server_state` com `RemoteEntry` (R3) | nenhuma | `push/run.py`, `push/wire.py`, novo `push/project.py` |
| T3 | `plan_sync` de três vias (R4, R5, R10, R11) | T1, T2 | `push/plan.py` |
| T4 | Execução: filtro de decisões, gravação da base, `--ours` (R6, R7, R8, R12) | T3 | `push/run.py`, `cli/push.py` |
| T5 | Relatório e código de saída (R9) | T3 | `push/report.py`, `cli/push.py` |
| T6 | Teste de integração contra o dev server e documentos | T4, T5 | `tests/test_push_integration.py`, `dev/specs/to-do/push.md`, `GLOSSARY.md`, `CHANGELOG.md` |

T1 e T2 rodam em paralelo. T4 e T5 rodam em paralelo depois de T3.

## Provas exigidas

- T1: gravar, matar o processo no meio (simulado) e reler devolve a base
  anterior ou a nova, nunca metade.
- T2: teste de propriedade por tipo de recurso sobre a projeção, e o mesmo
  round-trip contra o dev server no teste de integração.
- T3: um teste por linha da tabela de decisão e por caso especial; teste de
  propriedade de convergência (aplicar o plano e replanejar dá só `Skip`).
  Os testes atuais de `test_push_plan.py` e `test_push_merge.py` continuam
  passando com base igual ao servidor.
- T6, contra o dev server:
  - editar uma entidade pela REST mantendo o `rev` (simula a web), rodar
    `ch push`: a edição continua no servidor e aparece como `Pull`;
  - criar uma entidade pela REST, rodar `ch push`: ela não é podada;
  - editar dos dois lados: `Conflict`; `--ours` envia a versão local;
  - apagar `.local/codehood/` e rodar `ch push` num curso em sincronia:
    nenhum conflito e a base é recriada.

## Fora da fase 1

Writers, `ch pull`, `ch sync`, `--theirs`, TUI, `If-Match` (depende de
`dev/issues/escrita-condicional-nos-services.md` no servidor), calendário no
pull, exames.
