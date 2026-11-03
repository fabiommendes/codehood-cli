# Laboratório 6: chuva de gotas

Gotas guardadas em uma lista, caindo e sumindo ao passar do chão.

## O que fazer

Cada gota é uma lista `[x, y, speed]`, como as estrelas das notas da aula.
Complete `rain.py`:

- `make_drop(x, speed)`: cria uma gota no topo da tela (`y = 0`).
- `fall(drops, height)`: devolve uma lista **nova** com as gotas que ainda
  estão na tela depois de cair `speed` pixels. Uma gota cuja posição `y` fique
  maior ou igual a `height` é descartada. Não altere a lista recebida nem
  remova itens enquanto percorre a mesma lista.
- `lowest_drop(drops)`: devolve a gota com o maior `y`, ou `None` se a lista
  estiver vazia.

Rode `python -m pytest` e depois `python main.py`.
