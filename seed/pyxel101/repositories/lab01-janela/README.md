# Laboratório 1: abrindo a janela

Neste laboratório você configura a janela do seu primeiro jogo com Pyxel.

## O que fazer

1. Abra `window.py` e complete as quatro funções. Cada uma devolve um valor
   com `return`, que o `main.py` repassa para `pyxel.init`. Veja a receita de
   `def` e `return` nas notas da aula 1.
2. A janela deve ter **160 x 120** pixels, o título **"Minha primeira janela"**
   e rodar a **30 quadros por segundo**.
3. Rode os testes até todos passarem:

   ```bash
   python -m pytest
   ```

4. Rode o jogo com `python main.py` e veja a janela abrir.

## Entrega

Faça `git commit` e `git push`. A correção automática roda os testes visíveis
da pasta `tests/` e outros que você não vê.

## Dicas

- Os testes não abrem janela: a lógica fica em `window.py`, e o `main.py` só
  chama o Pyxel.
- Um texto vai entre aspas e um número não: `return 160` e `return "oi"`.
