---
title: "Projeto final: rubrica"
description: "Critérios e pesos para avaliar o jogo, o código, os testes, o git e a apresentação."
---

# Rubrica do projeto final

A nota do projeto é a soma ponderada dos cinco critérios abaixo, de 0 a 10
cada.

| Critério          | Peso | O que a banca observa                                              |
| :---------------- | ---: | :----------------------------------------------------------------- |
| Jogo              |  35% | Requisitos obrigatórios, jogabilidade, acabamento, ausência de falhas |
| Código            |  25% | Organização em módulos, nomes, funções curtas, uso de classes e estados |
| Testes            |  15% | Pelo menos 5 testes úteis, lógica separada do Pyxel, testes que passam |
| Git               |  15% | Commits de todos, mensagens claras, uso de branches e revisões     |
| Apresentação      |  10% | Clareza, tempo, domínio do código, respostas à banca                |

## Níveis por critério

| Nível     | Nota | Descrição                                                      |
| :-------- | ---: | :------------------------------------------------------------- |
| Excelente |  9-10 | Cumpre tudo, com cuidado e algo além do pedido                |
| Bom       |   7-8 | Cumpre todos os requisitos obrigatórios com pequenas falhas   |
| Regular   |   5-6 | Falta um requisito obrigatório ou há falhas visíveis          |
| Fraco     |   0-4 | Faltam vários requisitos ou o jogo não abre                   |

## Detalhes

### Jogo (35%)

- Três telas, jogador, inimigos, colisão, pontuação, recorde e sprites.
- O jogo termina e reinicia sem precisar fechar o programa.
- Desejáveis (som, fases, versão web) compensam pequenas falhas, até 1 ponto.

### Código (25%)

- Nenhuma função com mais de 30 linhas sem motivo.
- Sem `while True` no `update`.
- Constantes nomeadas em vez de números soltos.

### Testes (15%)

- `pytest` roda sem abrir janela.
- Os testes cobrem colisão, movimento e o estado do jogo.

### Git (15%)

- Cada integrante tem commits, e os commits são pequenos e descritivos.
- Pelo menos um pull request com revisão de outra pessoa do grupo.

### Apresentação (10%)

- Cabe em 8 minutos. Todos falam. A demonstração roda ao vivo.

## Nota individual

A nota do grupo é ajustada por integrante conforme o histórico do git: quem
contribuiu com menos de metade da média do grupo tem a nota reduzida
proporcionalmente.
