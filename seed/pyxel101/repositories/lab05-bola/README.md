# Laboratório 5: a bola

Uma bola que quica nas bordas da tela, escrita com funções pequenas.

## O que fazer

Complete `ball.py`. A tela ocupa os pixels de `0` a `size - 1`, e a bola de raio
`r` e centro `pos` ocupa de `pos - r` a `pos + r`. As duas funções olham para um
eixo só e devolvem um número:

- `bounce_pos(pos, vel, r, size)`: devolve a nova posição. Se a bola passasse
  da borda, ela fica encostada nela.
- `bounce_vel(pos, vel, r, size)`: devolve a nova velocidade. Se a bola
  passasse da borda, a velocidade troca de sinal. Encostar sem passar não é
  quicar.

O `main.py` chama cada função uma vez por eixo. Cada função faz uma coisa só e
devolve um valor novo, sem usar variáveis globais. Isso é o que permite
testá-las sem abrir a janela.

Rode `python -m pytest` e depois `python main.py`.
