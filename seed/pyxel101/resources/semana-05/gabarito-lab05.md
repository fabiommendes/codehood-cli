---
title: "Gabarito do Laboratório 5: a bola"
description: "Solução comentada de ball.py, com os erros mais comuns encontrados nas entregas."
release: after-lesson
---

# Gabarito do Laboratório 5: a bola

Este material só é liberado depois do laboratório.

## Solução

```python
def bounce_pos(pos, vel, r, size):
    """Devolve a nova posição em um eixo, encostada na borda se passaria dela."""
    new = pos + vel
    if new - r < 0:
        return r
    if new + r > size - 1:
        return size - 1 - r
    return new


def bounce_vel(pos, vel, r, size):
    """Devolve a nova velocidade em um eixo: troca de sinal se passaria da borda."""
    new = pos + vel
    if new - r < 0 or new + r > size - 1:
        return -vel
    return vel
```

## Por que funciona

- Cada função cuida de **um eixo** e devolve **um número**. O `main.py` as chama
  duas vezes, uma para `x` e outra para `y`. Escrever o eixo uma só vez evita o
  erro de ajustar `x` e esquecer `y`.
- Quando a bola passaria da borda, ela é recolocada **encostada** na borda.
  Se só invertêssemos a velocidade, a bola poderia ficar presa fora da tela,
  trocando de sinal a cada quadro.
- Encostar sem passar não é quicar: os limites usam `<` e `>`, não `<=` e `>=`.
- As duas funções repetem a mesma condição. Está bom por enquanto: devolver os
  dois valores de uma vez exige tuplas, que chegam na semana 8.

## Erros comuns

| Erro                                          | Efeito                                      |
| :-------------------------------------------- | :------------------------------------------ |
| Usar `size` em vez de `size - 1` na borda     | A bola entra 1 pixel na borda               |
| Esquecer o raio nos limites                   | A bola quica com o centro na borda          |
| Alterar variáveis globais dentro da função    | Os testes não conseguem isolar a função     |
| Imprimir o resultado em vez de devolvê-lo     | A função devolve `None`                     |
| Inverter a velocidade sem corrigir a posição  | A bola fica presa fora da tela              |

## Teste de mesa

`bounce_pos(pos=8, vel=-3, r=4, size=160)`: `new = 5`. Como `5 - 4 = 1`, não é
menor que 0, então a bola continua em `5`, e `bounce_vel` devolve `-3`. Já com `pos=5`, `new = 2`
e `2 - 4 = -2 < 0`, então `bounce_pos` devolve `r = 4` e `bounce_vel` devolve `3`.

## Para ir além

Faça a bola perder um pouco de velocidade a cada quique, multiplicando a
velocidade por `-0.9`. Que tipo de velocidade o teste do laboratório espera, e
o que muda se ela deixar de ser inteira?
