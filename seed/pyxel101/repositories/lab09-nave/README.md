# Laboratório 9: a nave

Uma nave que anda, atira, e tiros que acertam inimigos. O laboratório tem duas
partes, uma por aula.

## Parte 1: a nave (`ship.py`)

- `Bullet`: um tiro. `update()` sobe `speed` pixels (`speed` é negativo: -4) e
  `alive(...)` diz se o tiro ainda está na tela, isto é, se `y >= 0`.
- `Ship.move(direction, screen_w)`: soma `direction * speed` a `x` e mantém a
  nave inteira dentro da tela.
- `Ship.shoot()`: cria um `Bullet` saindo do meio da nave (`x + width // 2`),
  na altura `y` da nave.
- `Ship.rect()`: devolve `(x, y, width, height)`.
- `cleanup(bullets)`: devolve uma lista nova só com os tiros vivos.

## Parte 2: colisão (`collision.py`)

Retângulos são tuplas `(x, y, w, h)`.

- `overlaps(a, b)`: `True` se os retângulos têm área em comum. Retângulos que
  só se encostam pela borda **não** se sobrepõem.
- `point_in_rect(px, py, rect)`: `True` se o ponto está dentro. A borda
  esquerda e a de cima contam, a direita e a de baixo não.
- `first_hit(rect, others)`: índice do primeiro retângulo de `others` que se
  sobrepõe a `rect`, ou `None`.

Os testes da parte 2 ficam em `tests/test_colisao.py`. Rode `python -m pytest`
e `python main.py`.
