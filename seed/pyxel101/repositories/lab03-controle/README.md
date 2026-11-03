# Laboratório 3: controlando com o teclado

Um quadrado que anda com as setas e nunca sai da tela.

## O que fazer

Complete `controls.py`. Todas as funções devolvem um número inteiro:

- `clamp(value, low, high)`: limita `value` ao intervalo `[low, high]`.
- `direction(negative, positive)`: recebe dois booleanos (a tecla do sentido
  negativo e a do positivo) e devolve -1, 0 ou 1. Teclas opostas apertadas
  juntas se anulam.
- `next_x(x, dx, size, screen_w, speed)`: devolve o novo `x` de um quadrado de
  lado `size`, somando `dx * speed` e mantendo o quadrado inteiro dentro da
  tela. O `main.py` usa a mesma função para o eixo `y`, passando a altura.

Rode `python -m pytest` e depois `python main.py`.
