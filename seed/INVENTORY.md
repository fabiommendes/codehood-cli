# Inventário do curso `pyxel101`

Contrato entre T5a (resources e avisos), T5b (questions e exams) e T5c
(repositories, solutions, grades). Caminhos relativos a `cli/seed/pyxel101/`.
Cada arquivo abaixo deve existir ao final, e nenhum fora da lista deve ser
criado sem atualizar este arquivo. Todo link de `calendar.md` para `resources/`
e `repositories/` aponta para um caminho daqui. Já existem: `codehood.toml`,
`README.md`, `calendar.md`.

Desejos W1-W14: ver `dev/specs/to-review/seed-cli-pyxel101.md` (R18). A coluna W diz
qual desejo o arquivo exercita. `[proposto]` marca formato sem definição no
mapping doc, a registrar no `GAPS.md` como "formato proposto, não decidido".

## Regras comuns

- pt-BR no texto e nos comentários. Identificadores Python em inglês nos laboratórios, nas classes e nas questões de código; nos trechos de aula e nas questões das semanas 1 a 8, o vocabulário das notas (`tela`, `titulo`, `gotas`, `linha`, `coluna`).
- Até a semana 6, as funções dos laboratórios devolvem só números, textos e booleanos (e, na semana 6, listas de números). Dicionários e tuplas entram na semana 8. Notas, exemplos e testes seguem essa ordem.
- Datas por extenso não aparecem em texto corrido (o seed só desloca as ISO do front matter e das provas): use "semana N" ou "da semana seguinte".
- Slug de resource: caminho sem extensão, achatado com `-`. Duas entradas com o
  mesmo caminho sem extensão na mesma pasta colidem e abortam o push (por isso
  `bola.py` e `bola-jogavel.html` têm nomes diferentes). Não crie
  `x.md` e `x.pdf` juntos.
- Um resource pertence a no máximo uma aula. Os `.png` embutidos nas notas e os
  arquivos que nenhuma aula linka ficam sem link, de propósito.
- `slugify` hoje descarta letras acentuadas (`laços/a.md` vira `la-os-a`).
  Questões acentuadas ficam sem `id:` e as provas as incluem por caminho
  (`include: laços/passos-do-range.md`). As demais incluem por slug.
- Os `.py` de `resources/` rodam com `python -m py_compile`; os que usam Pyxel
  só importam `pyxel`, sem outras dependências. Os testes dos starters nunca
  importam `pyxel`: a lógica fica em módulos puros e o `main.py` só desenha.
- PNG com no máximo 160x120 px, PDF com 1 a 3 páginas, tudo abaixo de 50 KB.

## resources/ (T5a)

`T` é o tipo no servidor: MD, CODE, FILE, LINK. Notas MD levam front matter
`title`/`description`, blocos de código, ao menos uma tabela nas semanas 2, 3,
8 e 10, e imagem relativa (`![...](x.png)`) onde há `.png` na mesma pasta.

| Caminho | T | Propósito | W |
| :-- | :-- | :-- | :-- |
| `resources/curso/plano-de-ensino.md` | MD | Ementa, avaliação e cronograma resumido | W1 |
| `resources/curso/guia-de-estudo-python.pdf` | FILE | Folha de consulta de sintaxe | W2 |
| `resources/semana-01/notas.md` | MD | Instalação, REPL e primeiro programa, com `janela.png` e `repl.png` | W1 |
| `resources/semana-01/janela.png` | FILE | Captura da janela do Pyxel | W1 |
| `resources/semana-01/repl.png` | FILE | Captura do REPL | W1 |
| `resources/semana-01/slides-ambiente.pdf` | FILE | Slides da aula 1 | W2 |
| `resources/semana-01/janela-minima.py` | CODE | `pyxel.init` e `pyxel.run` mínimos | |
| `resources/semana-01/docs-pyxel.url` | LINK | Repositório e documentação do Pyxel | W3 |
| `resources/semana-01/instalacao-video.url` | LINK | Vídeo de instalação | W3 |
| `resources/semana-01/info.yaml` | meta | Títulos de `janela.png`, `repl.png` e `slides-ambiente.pdf` | |
| `resources/semana-02/notas.md` | MD | Tipos, operadores, coordenadas; tabela de tipos; `paleta.png` | W1 |
| `resources/semana-02/paleta.png` | FILE | As 16 cores com seus índices | W1, W14 |
| `resources/semana-02/slides-variaveis.pdf` | FILE | Slides da aula 2 | W2 |
| `resources/semana-02/coordenadas.py` | CODE | Pontos e retângulos em posições calculadas | |
| `resources/semana-02/cores.py` | CODE | Todas as 16 cores em uma grade | |
| `resources/semana-02/paleta-oficial.url` | LINK | Paleta na documentação | W3 |
| `resources/semana-03/notas.md` | MD | `if`/`elif`/`else`, lógicos, `btn`; tabela de operadores; `fluxograma-condicional.png` | W1 |
| `resources/semana-03/fluxograma-condicional.png` | FILE | Fluxograma de um `if/else` | W1 |
| `resources/semana-03/slides-condicionais.pdf` | FILE | Slides da aula 3 | W2 |
| `resources/semana-03/teclado.py` | CODE | Mostra qual tecla está pressionada | |
| `resources/semana-03/mover-quadrado.py` | CODE | Quadrado que anda com as setas | |
| `resources/semana-04/notas.md` | MD | `for`, `range`, `while`, laços aninhados; `padrao-xadrez.png` | W1 |
| `resources/semana-04/padrao-xadrez.png` | FILE | Tabuleiro de xadrez gerado por laços | W1 |
| `resources/semana-04/slides-lacos.pdf` | FILE | Slides da aula 4 | W2 |
| `resources/semana-04/grade.py` | CODE | Grade de pontos com laço duplo | |
| `resources/semana-04/espiral.py` | CODE | Espiral com `while` | |
| `resources/semana-05/notas.md` | MD | Funções, retorno, escopo, ciclo `update`/`draw`; `ciclo-update-draw.png` | W1 |
| `resources/semana-05/ciclo-update-draw.png` | FILE | Diagrama do ciclo do Pyxel | W1 |
| `resources/semana-05/slides-funcoes.pdf` | FILE | Slides da aula 5 (reposta) | W2 |
| `resources/semana-05/bola.py` | CODE | Bola quicando com funções | |
| `resources/semana-05/bola-jogavel.html` | CODE | Saída de `pyxel app2html` da bola; o servidor o trata como CODE (`html`) | W4 |
| `resources/semana-05/funcoes-python.url` | LINK | Tutorial de funções do Python | W3 |
| `resources/semana-05/gabarito-lab05.md` | MD | Solução comentada do lab05; front matter `release: after-lesson` `[proposto]` | W11 |
| `resources/semana-05/info.yaml` | meta | `bola-jogavel.html` com `mime: text/html` `[proposto]` (hoje a extensão decide) | W4 |
| `resources/semana-06/notas.md` | MD | Listas, `append`, fatiamento, laços sobre listas; `inimigos.png` | W1 |
| `resources/semana-06/inimigos.png` | FILE | Sprites de inimigos | W1, W14 |
| `resources/semana-06/slides-listas.pdf` | FILE | Slides da aula 6 | W2 |
| `resources/semana-06/chuva.py` | CODE | Gotas em uma lista | |
| `resources/semana-06/estrelas.py` | CODE | Campo de estrelas | |
| `resources/provas/revisao-prova1.md` | MD | Roteiro de revisão das semanas 1 a 6 | W1 |
| `resources/provas/revisao-prova2.md` | MD | Roteiro de revisão das semanas 8 a 13 | W1 |
| `resources/provas/gabarito-prova1.md` | MD | Gabarito comentado; `release: after-lesson` `[proposto]` | W7, W11 |
| `resources/provas/gabarito-prova2.md` | MD | Gabarito comentado; `release: after-lesson` `[proposto]` | W7, W11 |
| `resources/semana-08/notas.md` | MD | Dicionários, tuplas, estado do jogo; tabela dict x tuple; `maquina-de-estados.png` | W1 |
| `resources/semana-08/maquina-de-estados.png` | FILE | Diagrama título, jogo, fim | W1 |
| `resources/semana-08/slides-dicionarios.pdf` | FILE | Slides da aula 8 | W2 |
| `resources/semana-08/estados.py` | CODE | Três telas controladas por um dicionário | |
| `resources/semana-09/notas.md` | MD | Classes, `__init__`, métodos, `Player` e `Enemy`; `diagrama-classes.png` | W1 |
| `resources/semana-09/diagrama-classes.png` | FILE | Diagrama das classes | W1 |
| `resources/semana-09/slides-classes.pdf` | FILE | Slides da aula 9 | W2 |
| `resources/semana-09/nave.py` | CODE | Classe `Player` | |
| `resources/semana-09/inimigos.py` | CODE | Lista de objetos `Enemy` | |
| `resources/semana-10/notas.md` | MD | AABB e testes de colisão; tabela de casos; `aabb-diagrama.png` | W1 |
| `resources/semana-10/aabb-diagrama.png` | FILE | Dois retângulos sobrepostos e separados | W1 |
| `resources/semana-10/slides-colisao.pdf` | FILE | Slides da aula 10 | W2 |
| `resources/semana-10/aabb.py` | CODE | Colisão entre retângulos | |
| `resources/semana-10/colisao-circulo.py` | CODE | Colisão entre círculos | |
| `resources/semana-11/notas.md` | MD | Editor, `.pyxres`, sprites, tilemaps; `sprites.png` com `![](sprites.png)` | W1 |
| `resources/semana-11/sprites.png` | FILE | Folha de sprites 8x8 | W1, W14 |
| `resources/semana-11/slides-sprites.pdf` | FILE | Slides da aula 11 | W2 |
| `resources/semana-11/plataforma.py` | CODE | Carrega `personagem.pyxres` e desenha um tilemap | |
| `resources/semana-11/personagem.pyxres` | FILE | Recursos gerados pelo Pyxel (se não for possível gerar, PNG no lugar e aviso aqui) | W14 |
| `resources/semana-11/editor-pyxel.url` | LINK | Vídeo do editor | W3 |
| `resources/semana-11/info.yaml` | meta | `personagem.pyxres` com `mime: application/octet-stream` | W14 |
| `resources/semana-12/notas.md` | MD | `pyxel.sound`, `pyxel.music`, notação de notas; `notas-musicais.png` | W1 |
| `resources/semana-12/notas-musicais.png` | FILE | Tabela de notas | W1 |
| `resources/semana-12/slides-som.pdf` | FILE | Slides da aula 12 | W2 |
| `resources/semana-12/som.py` | CODE | Efeito sonoro ao apertar uma tecla | |
| `resources/semana-12/musica.py` | CODE | Melodia em dois canais | |
| `resources/semana-13/notas.md` | MD | `open`, `with`, JSON, recorde em disco | W1 |
| `resources/semana-13/slides-arquivos.pdf` | FILE | Slides da aula 13 | W2 |
| `resources/semana-13/recorde.py` | CODE | Lê e grava `recorde.json` | |
| `resources/semana-13/formato-json.url` | LINK | Documentação de JSON no Python | W3 |
| `resources/semana-13/rascunho-formato-recorde.md` | MD | Rascunho; excluído por `resources/**/rascunho-*`, pode ser inválido | |
| `resources/semana-14/game-jam.md` | MD | Regras, escopo, divisão de tarefas | W9 |
| `resources/semana-16/apresentacao-roteiro.md` | MD | Roteiro de 8 minutos por grupo | W9 |
| `resources/projeto/enunciado.md` | MD | Requisitos do jogo, entregas, prazos | W9 |
| `resources/projeto/rubrica.md` | MD | Tabela de critérios e pesos (jogo, código, testes, git, apresentação) | W9 |
| `resources/projeto/banca.md` | MD | Composição da banca, ordem e horários das apresentações | W9 |

## avisos/ (T5a) `[proposto]`

Fora de qualquer pasta que o push lê; aparecem como não consumidos. Cada
arquivo tem front matter `title`, `date` e `pinned`.

| Caminho | Propósito | W |
| :-- | :-- | :-- |
| `avisos/2026-08-03-boas-vindas.md` | Boas-vindas e como clonar os laboratórios | W13 |
| `avisos/2026-08-28-aula-5-cancelada.md` | Cancelamento da aula 5 e reposição na quarta | W13, W10 |
| `avisos/2026-10-09-feriado-de-quinta.md` | Dia do Professor: sem laboratório, lab11 começa na semana seguinte | W13, W10 |

## questions/ (T5b)

41 questões do banco, mais 3 de código `[proposto]`, mais 1 rascunho excluído.
Slug = caminho achatado (`ambiente/pyxel-init.md` vira `ambiente-pyxel-init`).
Tipos: MC multiple-choice, MS multiple-selection, TF true-false, NUM numeric,
SA short-answer, ES essay (com gabarito), FI fill-in.

| Caminho | Tipo | Propósito | W |
| :-- | :-- | :-- | :-- |
| `questions/ambiente/potencia-no-repl.md` | NUM | Valor de `2 ** 10` no REPL | |
| `questions/ambiente/pyxel-init.md` | FI | Completar `pyxel.init(160, ___, title=...)` | |
| `questions/ambiente/primeiro-programa.md` | TF | `pyxel.run` precisa de `update` e `draw` | |
| `questions/variaveis/tipo-de-literal.md` | MC | `type(3.0)` | |
| `questions/variaveis/nomes-validos.md` | MS | Quais nomes de variável são válidos | |
| `questions/variaveis/divisao-inteira.md` | NUM | `17 // 5` | |
| `questions/variaveis/coordenadas-tela.md` | SA | Onde fica o pixel (0, 0) | |
| `questions/variaveis/cores-pyxel.md` | MC | Índice da cor vermelha na paleta | |
| `questions/variaveis/imutabilidade-de-string.md` | TF | Strings não mudam in-place | |
| `questions/condicionais/btn-vs-btnp.md` | MC | Diferença entre `btn` e `btnp` | |
| `questions/condicionais/tabela-verdade.md` | MS | Expressões `and`/`or` verdadeiras | |
| `questions/condicionais/limite-da-tela.md` | FI | Completar o teste que impede sair pela direita | |
| `questions/condicionais/condição-dupla.md` | SA | Reescrever dois `if` em um com `and` (arquivo acentuado) | |
| `questions/laços/passos-do-range.md` | NUM | Quantos valores `range(2, 20, 3)` produz (diretório acentuado) | |
| `questions/laços/while-infinito.md` | TF | Um `while True` sempre trava o Pyxel | |
| `questions/laços/quantas-iteracoes.md` | MC | Iterações de um laço duplo | |
| `questions/laços/padrão-xadrez.md` | ES | Descrever os laços que desenham um tabuleiro | |
| `questions/laços/break-continue.md` | MS | O que `break` e `continue` fazem | |
| `questions/funcoes/retorno-vs-print.md` | MC | `return` versus `print` | |
| `questions/funcoes/escopo-de-variaveis.md` | SA | Por que uma variável local não existe fora da função | |
| `questions/funcoes/argumento-padrao.md` | FI | Completar `def draw_ball(x, y, color=___)` | |
| `questions/funcoes/update-draw.md` | TF | `update` roda antes de `draw` a cada quadro | |
| `questions/funcoes/fase-do-ciclo.md` | MS | O que pertence a `update` e o que a `draw` | |
| `questions/listas/indice-negativo.md` | NUM | Valor de `lista[-2]` | |
| `questions/listas/remover-durante-iteracao.md` | ES | Por que remover itens durante o `for` é perigoso | |
| `questions/listas/append-ou-extend.md` | MC | Resultado de `append` versus `extend` | |
| `questions/listas/fatiamento.md` | SA | Resultado de `lista[1:4]` | |
| `questions/dicionarios/acessar-chave-ausente.md` | MC | `d["x"]` versus `d.get("x")` | |
| `questions/dicionarios/tupla-imutavel.md` | TF | Tuplas aceitam atribuição por índice | |
| `questions/dicionarios/estado-do-jogo.md` | MS | Que valores cabem em `state = {...}` | |
| `questions/classes/self.md` | MC | Papel de `self` | |
| `questions/classes/init-do-inimigo.md` | FI | Completar o `__init__` de `Enemy` | |
| `questions/classes/herança.md` | ES | Quando usar herança em `Enemy` (arquivo acentuado) | |
| `questions/classes/metodos-vs-funcoes.md` | TF | Todo método recebe `self` explicitamente na definição | |
| `questions/colisao/aabb-sobrepoe.md` | MS | Quais pares de retângulos se sobrepõem | |
| `questions/colisao/area-do-retangulo.md` | NUM | Área de sobreposição de dois retângulos | |
| `questions/colisao/ponto-no-retangulo.md` | SA | Condição para um ponto estar dentro de um retângulo | |
| `questions/pyxel/tilemap-tamanho.md` | MC | Tamanho de um tile em pixels | |
| `questions/pyxel/canais-de-som.md` | NUM | Quantos canais de som o Pyxel tem | |
| `questions/arquivos/modo-de-abertura.md` | MC | Modo de `open` para acrescentar ao fim | |
| `questions/arquivos/recorde-com-with.md` | FI | Completar a leitura do recorde com `with` | |
| `questions/código/soma-pares.md` | código | Escrever `sum_even(values)`; testes ocultos no corpo `[proposto]` | W8 |
| `questions/código/fatorial.md` | código | Escrever `factorial(n)` com testes `[proposto]` | W8 |
| `questions/código/colisao-aabb.md` | código | Escrever `overlaps(a, b)` com testes `[proposto]` | W8 |
| `questions/rascunhos/ideia-gerador-de-fases.md` | inválida | Excluída por `questions/rascunhos`; pode ser sintaxe quebrada | |

Contagem por tipo no banco de 42: MC 11, MS 6, TF 6, NUM 6, SA 5, ES 3, FI 5.
Formato `[proposto]` das questões de código: front matter `type: code`,
`language: python`, `function: sum_even`, e os testes em um bloco
```` ```python tests ````. Se `mdq` rejeitar, escrever como `[essay]` com os
testes no gabarito e anotar aqui.

## exams/ (T5b)

Formato do mapping doc: front matter `course`, `author`, `locale: pt-BR`,
`start` (ISO), `duration`, H1 `# [id] Título`, preâmbulo, depois blocos
`include:` e questões inline (`id:`), separados como no mapping doc. As datas
batem com `calendar.md`. Chaves `[proposto]` (W7): `draw: N` (sorteia N do
conjunto), `shuffle: true`, `release: after-end` (gabarito depois). Se o
parser do `mdq` rejeitar chave desconhecida, mover para `meta:` e anotar aqui.

| Caminho | Tipo | Início | Conteúdo | W |
| :-- | :-- | :-- | :-- | :-- |
| `exams/prova1.md` | EXAM | 2026-09-15T10:00:00, 2h | 15 includes: ambiente-primeiro-programa, ambiente-potencia-no-repl, variaveis-tipo-de-literal, variaveis-nomes-validos, variaveis-divisao-inteira, variaveis-coordenadas-tela, condicionais-btn-vs-btnp, condicionais-tabela-verdade, `laços/passos-do-range.md`, `laços/padrão-xadrez.md`, funcoes-retorno-vs-print, funcoes-escopo-de-variaveis, funcoes-update-draw, listas-indice-negativo, listas-append-ou-extend; 3 inline (MC, NUM, ES); `shuffle`, `release: after-end` | W7 |
| `exams/prova2.md` | EXAM | 2026-11-10T10:00:00, 2h | 14 includes: dicionarios-acessar-chave-ausente, dicionarios-tupla-imutavel, dicionarios-estado-do-jogo, classes-self, classes-init-do-inimigo, `classes/herança.md`, classes-metodos-vs-funcoes, colisao-aabb-sobrepoe, colisao-area-do-retangulo, colisao-ponto-no-retangulo, pyxel-tilemap-tamanho, pyxel-canais-de-som, arquivos-modo-de-abertura, listas-remover-durante-iteracao; `código/colisao-aabb.md`; 2 inline (FI, TF); `shuffle`, `release: after-end` | W7, W8 |
| `exams/practice/quiz-semanal.md` | PRACTICE | sem início | Banco de 8 includes (ambiente-pyxel-init, variaveis-imutabilidade-de-string, condicionais-limite-da-tela, funcoes-argumento-padrao, listas-fatiamento, dicionarios-estado-do-jogo, classes-init-do-inimigo, arquivos-recorde-com-with) + 1 inline (MC); `draw: 5`, `shuffle`; `tags: [semanal]`; sem nota | W6, W7 |
| `exams/prova-reposicao.md` | EXAM | 2026-11-18T16:00:00, 2h | 10 includes: variaveis-cores-pyxel, condicionais-btn-vs-btnp, funcoes-fase-do-ciclo, listas-fatiamento, dicionarios-acessar-chave-ausente, classes-self, colisao-aabb-sobrepoe, pyxel-tilemap-tamanho, arquivos-modo-de-abertura, `código/soma-pares.md`; 2 inline (SA, ES); `shuffle`, `release: after-end` | W7, W8 |

Questões que nenhuma prova cita ficam só no banco, de propósito: `condicionais/condição-dupla`, `laços/while-infinito`, `laços/quantas-iteracoes`, `laços/break-continue`, `rascunhos/ideia-gerador-de-fases`.

## repositories/ (T5c)

Cada repositório tem `README.md` (enunciado em pt-BR), `main.py` (jogo com
Pyxel, só desenha e chama o módulo puro), o módulo puro e `tests/`. Starter:
funções com `raise NotImplementedError` ou corpo incompleto, de modo que os
testes falhem. Cada repositório tem `.gitignore` com `__pycache__/` e
`.pytest_cache/`.

| Caminho | Propósito | W |
| :-- | :-- | :-- |
| `repositories/lab01-janela/README.md` | Enunciado do lab 1 | W5 |
| `repositories/lab01-janela/main.py` | Abre a janela usando `window.py` | |
| `repositories/lab01-janela/window.py` | `window_width()`, `window_height()`, `window_title()` e `window_fps()` a completar | W5 |
| `repositories/lab01-janela/tests/test_window.py` | Testes visíveis | W5 |
| `solutions/lab01-janela/autograde.toml` | Comando e peso da autocorreção, com referência a testes ocultos `[proposto]`; fora do repositório do aluno | W5 |
| `repositories/lab02-cores/{README.md,main.py,shapes.py,tests/test_shapes.py}` | Posições e cores calculadas | |
| `repositories/lab03-controle/{README.md,main.py,controls.py,tests/test_controls.py}` | Movimento por teclado limitado à tela | |
| `repositories/lab04-padroes/{README.md,main.py,patterns.py,tests/test_patterns.py}` | Padrões com laços aninhados | |
| `repositories/lab05-bola/{README.md,main.py,ball.py,tests/test_ball.py}` | Bola com funções | |
| `solutions/lab05-bola/autograde.toml` | Autocorreção `[proposto]`; fora do repositório do aluno | W5 |
| `repositories/lab06-chuva/{README.md,main.py,rain.py,tests/test_rain.py}` | Lista de gotas, cada uma uma lista `[x, y, speed]` | |
| `repositories/lab08-estados/{README.md,main.py,states.py,tests/test_states.py}` | Máquina de estados em dicionário | |
| `repositories/lab09-nave/{README.md,main.py,ship.py,collision.py}` | Nave, tiros e AABB | |
| `repositories/lab09-nave/tests/test_ship.py` | Testes da nave | |
| `repositories/lab09-nave/tests/test_colisao.py` | Testes de AABB; linkado por `calendar.md` | |
| `repositories/lab11-plataforma/{README.md,main.py,movement.py,tests/test_movement.py}` | Movimento e gravidade em tilemap | |
| `repositories/lab11-plataforma/requirements.txt` | `pyxel` e `pytest` | |
| `repositories/lab11-plataforma/.gitignore` | Raiz: `__pycache__/`, `.pytest_cache/`, `build/` | |
| `repositories/lab11-plataforma/assets/sprites.png` | Folha de sprites | W14 |
| `repositories/lab11-plataforma/assets/plataforma.pyxres` | Recursos do Pyxel, se o Pyxel gerar | W14 |
| `repositories/lab11-plataforma/assets/.gitignore` | Aninhado: `*.png` e `!sprites.png` | W14 |
| `repositories/lab11-plataforma/assets/rascunho.png` | Presente no seed, ignorado pelo `.gitignore` aninhado, não deve chegar ao repositório | W14 |
| `repositories/lab11-plataforma/scripts/run.sh` | Roda o jogo; modo `100755` | |
| `repositories/projeto-final/README.md` | Como o grupo trabalha com o template | W9 |
| `repositories/projeto-final/CONTRIBUTING.md` | Fluxo de git por grupo, commits por integrante | W9 |
| `repositories/projeto-final/main.py` | Esqueleto do jogo | |
| `repositories/projeto-final/game/__init__.py` | Pacote do jogo | |
| `repositories/projeto-final/game/state.py` | Estados (título, jogo, fim) | |
| `repositories/projeto-final/game/entities.py` | `Player` e `Enemy` | |
| `repositories/projeto-final/assets/sprites.png` | Sprites iniciais | W14 |
| `repositories/projeto-final/tests/test_smoke.py` | Teste mínimo que já passa | |
| `repositories/projeto-final/requirements.txt` | `pyxel` e `pytest` | |
| `repositories/projeto-final/.gitignore` | `__pycache__/`, `.pytest_cache/` | |

## solutions/ (T5c)

Fora do que o push lê. Cada solução tem os mesmos nomes de arquivo do módulo
puro do starter correspondente; copiar sobre o starter faz os testes passarem.

| Caminho | Propósito | W |
| :-- | :-- | :-- |
| `solutions/lab01-janela/window.py` | Referência | W5 |
| `solutions/lab01-janela/tests_ocultos/test_window_hidden.py` | Testes que o aluno não vê | W5 |
| `solutions/lab02-cores/shapes.py` | Referência | |
| `solutions/lab03-controle/controls.py` | Referência | |
| `solutions/lab04-padroes/patterns.py` | Referência | |
| `solutions/lab05-bola/ball.py` | Referência | W5 |
| `solutions/lab05-bola/tests_ocultos/test_ball_hidden.py` | Testes que o aluno não vê | W5 |
| `solutions/lab06-chuva/rain.py` | Referência | |
| `solutions/lab08-estados/states.py` | Referência | |
| `solutions/lab09-nave/ship.py` | Referência | |
| `solutions/lab09-nave/collision.py` | Referência | |
| `solutions/lab09-nave/tests_ocultos/test_collision_hidden.py` | Testes que o aluno não vê | W5 |
| `solutions/lab11-plataforma/movement.py` | Referência | |

## Raiz (T5c)

| Caminho | Propósito | W |
| :-- | :-- | :-- |
| `grades.py` | `grade(student)` com pesos 25/20/25/30 e conceito `final` como label; resultado `aprovado`/`reprovado` (média de 50 ou mais e frequência de pelo menos 75%) | W12 |
| `grades.csv` | Só o cabeçalho (`username,labs`); lab vindo do autograder em vez de planilha é o desejo | W12 |

## Adições de T5c

- `repositories/<lab>/pytest.ini` em cada repositório (`pythonpath = .`), para
  que `pytest` importe o módulo da raiz sem `python -m`.
- `repositories/projeto-final/RUBRICA.md` `[proposto]` (W9): rubrica dentro do
  template, espelhando `resources/projeto/rubrica.md`.
- `tools/make_lab_assets.py`: gera `sprites.png`, `rascunho.png` e
  `plataforma.pyxres` (`uv run --with pyxel python cli/seed/tools/make_lab_assets.py`).
- `solutions/<lab>/autograde.toml` aponta os testes ocultos em `tests_ocultos` (mesma pasta). O repositório do aluno não leva `autograde.toml`.
