---
title: "Gabarito comentado da Prova 2"
description: "Respostas e comentários das questões da Prova 2, por tema."
release: after-lesson
---

# Gabarito comentado da Prova 2

Este gabarito é liberado depois da prova. Como as provas são sorteadas de um
banco, use-o pelos temas.

## Dicionários e tuplas

- `d["x"]` com chave ausente causa **`KeyError`**; `d.get("x")` devolve
  `None` (ou o valor padrão, se for passado).
- Tuplas **não** aceitam atribuição por índice: `t[0] = 1` gera `TypeError`.
- Em `state = {...}` cabem números, strings, booleanos, listas, tuplas e outros
  dicionários. Valores que não cabem bem são os que não dá para gravar em
  JSON.

## Classes

- `self` é o próprio objeto: o Python o passa como primeiro argumento de todo
  método de instância.
- No `__init__` de `Enemy`, cada atributo recebe o parâmetro correspondente
  com `self.x = x`.
- Herança vale quando há a relação "é um" e comportamento comum (um `Boss` é
  um `Enemy`). Para "tem um", use atributo.
- Métodos de instância declaram `self` na definição e não o passam na chamada.

## Colisão

- Dois retângulos se sobrepõem se os intervalos se sobrepõem nos **dois**
  eixos. Encostar não é sobrepor, quando se usa `<`.
- A área de sobreposição é largura vezes altura, onde cada medida vem de
  `min(fim_a, fim_b) - max(inicio_a, inicio_b)`.
- Um ponto está dentro se `x <= px < x + w` e `y <= py < y + h`.

## Pyxel

- Um tile tem **8 por 8** pixels.
- O Pyxel tem **4** canais de som.

## Arquivos

- Para acrescentar ao final, o modo é **`"a"`**. O modo `"w"` apaga o
  conteúdo.
- A leitura do recorde usa `with open(...) as f:` e `json.load(f)`.

## Questão de código

`overlaps(a, b)` com os quatro testes de limite:

```python
def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
```

Os erros mais comuns: usar `<=` e contar retângulos encostados como colisão, e
comparar só um dos eixos.
