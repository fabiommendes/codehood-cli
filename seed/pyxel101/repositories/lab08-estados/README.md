# Laboratório 8: telas e estados

O jogo tem três telas, e um dicionário guarda em qual delas ele está.

## O que fazer

O estado é `{"screen": "title" | "game" | "over", "score": int, "lives": int}`.
Complete `states.py`:

- `new_state()`: tela `"title"`, pontuação 0 e 3 vidas.
- `advance(state, start, points, hit)`: devolve o estado do próximo quadro,
  **sem alterar** o recebido. As regras:
  - em `"title"`, `start` leva a `"game"` com pontuação 0 e 3 vidas;
  - em `"game"`, soma `points` à pontuação e, se `hit`, tira uma vida; ao
    chegar a 0 vida, vai para `"over"`;
  - em `"over"`, `start` volta para `"title"`, preservando a pontuação para
    exibir o recorde;
  - nos demais casos, o estado não muda.

Rode `python -m pytest` e depois `python main.py`.
