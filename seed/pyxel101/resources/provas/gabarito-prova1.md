---
title: "Gabarito comentado da Prova 1"
description: "Respostas e comentários das questões da Prova 1, por tema."
release: after-lesson
---

# Gabarito comentado da Prova 1

Este gabarito é liberado depois da prova. Cada prova é sorteada a partir de um
banco, então use-o para os temas, não para a numeração da sua prova.

## Ambiente e REPL

- `2 ** 10` vale **1024**. O operador `**` é a potência.
- `pyxel.init(160, ___, title=...)` pede a altura da janela em pixels. Os
  argumentos vêm na ordem largura, altura.

## Variáveis e tipos

- `type(3.0)` é `float`: o ponto decimal basta para criar um `float`.
- `17 // 5` vale **3** (divisão inteira) e `17 % 5` vale **2**.
- O pixel `(0, 0)` fica no **canto superior esquerdo**. O eixo `y` cresce
  para baixo.
- O índice da cor vermelha é **8**, na paleta padrão.
- Nomes de variáveis começam com letra ou `_`, e não aceitam espaço nem hífen.
  Palavras reservadas como `for` também não valem.

## Condicionais

- `btn` é verdadeira **enquanto** a tecla está apertada; `btnp` só no quadro em
  que foi apertada.
- Nas tabelas-verdade, `A and B` exige as duas; `A or B` exige uma;
  `not A` inverte.
- Para não sair pela direita: `if x > LARGURA - lado: x = LARGURA - lado`.

## Laços

- `range(2, 20, 3)` produz 2, 5, 8, 11, 14, 17: **seis** valores. O 20 não
  entra.
- Na descrição do tabuleiro, esperamos um laço externo para as linhas, um
  interno para as colunas, e a cor decidida por `(linha + coluna) % 2`.
  Quem cita só a ideia da paridade sem os laços recebe nota parcial.

## Funções

- `return` entrega o valor a quem chamou; `print` só mostra. Quem faz
  `x = f()` com uma função que só imprime recebe `None`.
- Variáveis locais existem apenas durante a chamada da função: o escopo delas
  termina com o fim da função.
- `update` roda **antes** de `draw` em todo quadro.

## Listas

- `lista[-2]` é o **penúltimo** elemento.
- `append(x)` acrescenta `x` como **um** elemento; `extend(it)` acrescenta os
  elementos de `it` um a um.
- `lista[1:4]` vai do índice 1 ao 3, sem incluir o 4.

## Dissertativa

A questão sobre remover itens durante o `for` espera: os elementos seguintes
mudam de índice após a remoção, então o laço pula um deles. A saída é
reconstruir a lista com uma compreensão ou percorrer uma cópia.
