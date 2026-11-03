---
title: "Game jam: regras e escopo"
description: "Regras da game jam, como definir o escopo do jogo e como dividir as tarefas do grupo."
---

# Game jam

Na semana 14, o laboratório de 2 horas é dedicado ao projeto final, e o trabalho
continua fora da aula, até o fim da semana 15. É uma *game jam*: pouco tempo,
escopo pequeno e um jogo que funciona no fim.

## Regras

1. Grupos de 3 ou 4 pessoas, formados até a semana 13.
2. Todo o código fica no repositório do grupo, a partir do template
   `projeto-final`.
3. Só se usa Python e Pyxel. Bibliotecas extras precisam de aprovação da
   professora.
4. Arte e sons podem ser criados no editor do Pyxel ou vir de bancos livres,
   com a fonte citada no `README` do jogo.
5. O jogo precisa abrir com `python main.py` em uma máquina limpa, só com
   `pip install -r requirements.txt`.

## Escopo

Um escopo pequeno que funciona vale mais do que um escopo grande pela metade.
Divida as funcionalidades em três níveis:

| Nível        | O que entra                                         | Meta               |
| :----------- | :-------------------------------------------------- | :----------------- |
| Essencial    | tela de título, jogo com um objetivo, tela de fim   | fim da semana 14   |
| Desejável    | vários inimigos, pontuação, recorde em disco        | fim da semana 15   |
| Opcional     | sons, música, fases, animações                      | se sobrar tempo    |

Congele o escopo nos primeiros 20 minutos do laboratório. Ideias novas vão para uma lista de
"talvez" e só voltam se o essencial já funciona.

## Dividindo as tarefas

Cada integrante assume uma frente e trabalha em uma **branch** própria:

- Mecânica do jogador e controles.
- Inimigos e colisão.
- Telas, estados e interface.
- Arte, sons e recorde.

Cada integrante faz os próprios commits. A professora olha o histórico do
repositório. Faça commits pequenos, com mensagens que dizem o que mudou:
`Adiciona tiro do jogador`, não `ajustes`. Abra um *pull request* para juntar
as branches e peça que outra pessoa do grupo revise.

## Cronograma da aula

O laboratório tem 2 horas. O que não couber nele continua em casa e no
atendimento de quarta-feira.

| Tempo    | Atividade                                             |
| :------- | :---------------------------------------------------- |
| 0:00     | Definição do escopo e divisão das frentes (20 min)    |
| 0:20     | Desenvolvimento; a professora circula entre os grupos |
| 1:40     | Cada grupo diz, em uma frase, o que já funciona       |
| 1:55     | Combinar o que cada pessoa faz até a próxima semana   |

## Dicas

- Rode o jogo com frequência. Um erro encontrado cedo custa menos.
- A lógica em módulos puros, sem importar `pyxel`, pode ser testada com
  `pytest`, como nos laboratórios.
- Grave o recorde só quando ele for batido.
- Deixe a tela de título pronta cedo: ela organiza o resto do jogo.
