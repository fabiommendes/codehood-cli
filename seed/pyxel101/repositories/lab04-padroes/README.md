# Laboratório 4: padrões na tela

Laços aninhados desenham tabuleiros, escadas e grades. Os laços já estão no
`main.py`; você escreve as pequenas funções que eles chamam.

## O que fazer

Complete `patterns.py`:

- `is_dark(col, row)`: devolve `True` se a casa `(col, row)` do tabuleiro é
  escura. A casa `(0, 0)` é clara e as cores alternam: use a paridade de
  `col + row`.
- `stair_line(n)`: devolve o texto com `n` símbolos `#` (`stair_line(3)` vale
  `"###"`).
- `grid_pos(index, step, margin)`: devolve a posição do ponto de índice `index`
  em uma grade com espaçamento `step` e margem `margin`. O índice 0 fica
  na margem.

Depois, leia os laços do `main.py` e mude o tamanho do tabuleiro e da grade.

Rode `python -m pytest` e `python main.py`.
