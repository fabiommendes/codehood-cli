---
title: Dois if em um só
tags: [condicionais, logica]
locale: pt-BR
incorrectFeedback: Os dois testes precisam valer ao mesmo tempo. Qual operador lógico expressa isso?
---

O código abaixo desenha a bola somente quando `x` está entre 0 e 100.

```python
if x > 0:
    if x < 100:
        desenha_bola(x)
```

Qual operador lógico, escrito no lugar das reticências, reúne os dois testes em um só
`if x > 0 ... x < 100:`?

[short-answer]:
* and
  > Isso mesmo. `if x > 0 and x < 100:` equivale aos dois `if` aninhados, e o Python
  > ainda aceita a forma encadeada `if 0 < x < 100:`.

[short-answer/reject]:
* or
  > Com `or`, qualquer `x` serviria, porque todo número é maior que 0 ou menor que 100.
* &
  > `&` é um operador bit a bit, não lógico. Ele funciona por acaso com booleanos, mas
  > tem precedência diferente e não deve ser usado aqui.
* &&
  > `&&` é de C e JavaScript. No Python o operador se escreve `and`.
