# Laboratório 2: cores e coordenadas

Variáveis e operadores viram posições e cores na tela.

## O que fazer

Complete as funções de `shapes.py`. Todas devolvem um número inteiro:

- `color_at(x, y)`: a paleta é desenhada como uma grade de 4 colunas e 4 linhas
  de células de 8 x 8 pixels, começando em `(0, 0)`. Devolva o índice da cor
  da célula que cobre o pixel `(x, y)`. A célula da coluna `c` e da linha `r`
  tem a cor `r * 4 + c`. Use divisão inteira.
- `center(screen, size)`: devolve a posição inicial de um objeto de tamanho
  `size` centralizado em uma tela de tamanho `screen`. Serve para `x` (com a
  largura) e para `y` (com a altura). Use divisão inteira.
- `mirror_x(x, w, screen_w)`: devolve o `x` de um retângulo de largura `w`
  refletido horizontalmente na tela.

Rode `python -m pytest` até passar e `python main.py` para ver o resultado.
