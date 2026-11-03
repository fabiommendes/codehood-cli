---
title: Modo de abertura do arquivo
tags: [arquivos, open]
locale: pt-BR
shuffle: true
---

O jogo guarda uma linha de texto por partida em `historico.txt`. Cada partida nova deve
ser acrescentada ao final, sem apagar o que já está lá. Qual é o modo de `open`?

```python
with open("historico.txt", "?") as f:
    f.write("nova partida\n")
```

* [ ] `"r"`
  > Esse modo é só para leitura, e `write` levantaria `io.UnsupportedOperation`.
* [ ] `"w"`
  > `"w"` apaga o conteúdo anterior ao abrir. Todo o histórico se perderia.
* [*] `"a"`
  > `"a"` (append) escreve sempre ao final e cria o arquivo se ele não existir.
* [ ] `"x"`
  > `"x"` só cria arquivos novos e falha se o arquivo já existir.
