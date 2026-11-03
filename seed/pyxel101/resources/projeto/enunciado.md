---
title: "Projeto final: enunciado"
description: "Requisitos do jogo, entregas e prazos do projeto final em grupo."
---

# Projeto final: um jogo em Pyxel

Em grupos de 3 ou 4 pessoas, vocês constroem um jogo completo, do zero, em
Python e Pyxel. O projeto vale **30%** da nota.

## Ponto de partida

Cada grupo clona o repositório `projeto-final` (template com `main.py`, o
pacote `game/`, `tests/` e `requirements.txt`). O fluxo de git do grupo está no
`CONTRIBUTING.md` do template.

## Requisitos obrigatórios

1. **Três telas:** título, jogo e fim, controladas por um estado (aula 8).
2. **Jogador controlado pelo teclado,** como objeto de uma classe (aula 9).
3. **Pelo menos um tipo de inimigo ou obstáculo,** com vários objetos ao mesmo
   tempo, guardados em uma lista (aulas 6 e 9).
4. **Colisão** entre elementos do jogo, com o teste em uma função pura (aula 10).
5. **Pontuação** visível, e **recorde gravado em disco** (aula 13).
6. **Sprites** desenhados com `blt` ou `bltm` a partir de um `.pyxres` ou PNG
   (aula 11).
7. **Testes** com `pytest` para a lógica sem Pyxel: ao menos 5 testes úteis.
8. O jogo abre com `python main.py` após `pip install -r requirements.txt`.

## Requisitos desejáveis

- Som e música (aula 12).
- Mais de uma fase ou dificuldade crescente.
- Uma versão jogável no navegador, gerada com `pyxel app2html`.

## Entregas e prazos

| Prazo               | Entrega                                                   |
| :------------------ | :-------------------------------------------------------- |
| Fim da semana 13    | Grupo formado e jogo escolhido, em uma frase, no `README` |
| Fim da semana 14    | Essencial funcionando: três telas, jogador e um inimigo   |
| Fim da semana 15    | Versão completa congelada no repositório                  |
| Semana 16           | Apresentação para a banca (ordem no sorteio)              |

## O que entregar

- O repositório do grupo, com histórico de git de todos os integrantes.
- Um `README` com: descrição do jogo, como rodar, controles, divisão do
  trabalho e fontes de arte e som.
- A apresentação de 8 minutos, conforme o roteiro.

## Como será avaliado

A [rubrica](rubrica.md) detalha os critérios. Em resumo: o jogo funciona e é
divertido, o código é claro, há testes, o git conta a história do trabalho e a
apresentação é clara.

## Regras

- O trabalho em grupo é coletivo, mas a nota é individual: o histórico do git
  mostra a contribuição de cada pessoa. Quem não tem commits não recebe a nota
  completa.
- Código e arte de terceiros precisam de citação. Plágio zera o projeto.
