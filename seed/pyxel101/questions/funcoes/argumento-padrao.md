---
title: Argumento com valor padrão
tags: [funcoes, argumentos, semanal]
locale: pt-BR
---

A função de desenho abaixo deve usar a cor amarela, de índice 10 na paleta, quando o
chamador não passar a cor.

def desenha_bola(x, y, cor=[^cor]):

Assim, a chamada desenha_bola(5, 5, 8) desenha a bola na cor [^usada].

[^cor/numeric]: 10

[^usada]:
* [*] 8, o argumento passado
  > O valor padrão só vale quando o argumento é omitido.
* [ ] 10, o valor padrão
  > O valor padrão é ignorado quando o chamador passa o argumento.
* [ ] Nenhuma, a chamada é um erro
  > Passar o argumento explicitamente é sempre permitido.
