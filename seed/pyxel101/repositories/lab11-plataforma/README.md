# Laboratório 11: plataforma

Um personagem que anda e pula sobre um tilemap. Os recursos do jogo estão em
`assets/plataforma.pyxres` (criado no editor do Pyxel) e a folha de sprites em
`assets/sprites.png`.

## O que fazer

O mapa guarda tiles de 8 x 8 pixels. O tile de chão é o `(1, 0)`. A lógica de
física, sem Pyxel, fica em `movement.py`; a função `is_solid(tx, ty)` recebida
pelas funções diz se o tile de coordenadas `(tx, ty)` é sólido.

- `collides(x, y, is_solid)`: `True` se o quadrado de 8 x 8 com canto
  superior esquerdo em `(x, y)` toca algum tile sólido. Teste os quatro cantos
  `(x, y)`, `(x + 7, y)`, `(x, y + 7)` e `(x + 7, y + 7)`. O pixel `(x, y)` fica
  no tile `(x // 8, y // 8)`.
- `jump(vy, on_ground)`: devolve `JUMP_SPEED` se `on_ground`, senão `vy`.
- `step(x, y, vx, vy, is_solid)`: um quadro de física. Devolve
  `(x, y, vy, on_ground)`:
  1. se a posição `(x + vx, y)` não colide, anda na horizontal;
  2. soma `GRAVITY` a `vy`, sem passar de `MAX_FALL`;
  3. se `(x, y + vy)` não colide, desce ou sobe;
  4. se colide caindo (`vy > 0`), encosta no chão: `y` fica no topo do tile,
     `vy = 0` e `on_ground = True`;
  5. se colide subindo (`vy < 0`), bate a cabeça: `y` fica logo abaixo do
     tile e `vy = 0`.

## Rodando

```bash
pip install -r requirements.txt
python -m pytest
./scripts/run.sh
```
