---
title: "Revisão da Prova 2"
description: "Roteiro de revisão dos temas das semanas 8 a 13."
---

# Roteiro de revisão da Prova 2

Prova individual e sem consulta, de 2 horas, sobre as semanas 8 a 13. As
semanas 1 a 6 continuam valendo como base, mas não são o foco.

## Semana 8: dicionários e tuplas

- [ ] Leio, altero e crio chaves de um dicionário.
- [ ] Sei a diferença entre `d["x"]` e `d.get("x")` quando a chave não existe.
- [ ] Sei que tuplas são imutáveis e por que servem como coordenadas.
- [ ] Sei montar o estado de um jogo como um dicionário.

## Semana 9: classes

- [ ] Escrevo uma classe com `__init__` e dois métodos.
- [ ] Explico o papel de `self`.
- [ ] Crio vários objetos e os guardo em uma lista.
- [ ] Sei quando faz sentido herdar de uma classe.

## Semana 10: colisão

- [ ] Escrevo o teste de sobreposição AABB de cabeça.
- [ ] Calculo a área de sobreposição de dois retângulos.
- [ ] Escrevo a condição de um ponto dentro de um retângulo.

## Semana 11: sprites e tilemaps

- [ ] Sei o tamanho de um tile e como `bltm` o usa.
- [ ] Sei carregar um `.pyxres` e ler um tile com `pget`.

## Semana 12: som

- [ ] Sei quantos canais de som o Pyxel tem.
- [ ] Sei ler uma sequência como `"c3e3g3"`.

## Semana 13: arquivos

- [ ] Escolho o modo certo do `open` para ler, sobrescrever e acrescentar.
- [ ] Leio um recorde com `with` e `json.load`.
- [ ] Trato o arquivo inexistente.

## Exercícios para treinar

1. Escreva uma classe `Coin` com posição e um método `collected_by(player)`.
2. Escreva `overlaps(a, b)` para retângulos `(x, y, w, h)` sem olhar as notas.
3. Converta um estado em dicionário para um objeto de uma classe `GameState`.
4. Escreva as duas funções, de ler e de gravar, de um arquivo `config.json`.
5. Resolva a questão de código do banco: tente escrever a função com os
   testes que ela traz.

## Como será a prova

- Questões objetivas, dissertativas e uma questão em que você escreve uma
  função que é corrigida por testes automáticos.
- O gabarito comentado será liberado depois do fim da prova.
