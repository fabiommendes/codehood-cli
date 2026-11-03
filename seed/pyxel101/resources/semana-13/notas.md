---
title: "Aula 13: Arquivos"
description: "Ler e escrever arquivos com open e with, formato JSON e como guardar o recorde do jogo em disco."
---

# Aula 13: Arquivos

Quando o jogo fecha, todas as variáveis desaparecem. Para guardar algo, como o
recorde, é preciso gravar em um arquivo.

## Abrindo arquivos

```python
arquivo = open("notas.txt", "r", encoding="utf-8")
texto = arquivo.read()
arquivo.close()
```

O primeiro argumento é o caminho; o segundo é o **modo**:

| Modo | Faz                                                     | Se o arquivo não existe |
| :--- | :------------------------------------------------------ | :---------------------- |
| `r`  | lê (é o padrão)                                         | `FileNotFoundError`     |
| `w`  | escreve, **apagando** o conteúdo anterior               | cria                    |
| `a`  | escreve ao **fim**, mantendo o conteúdo                 | cria                    |
| `x`  | cria e escreve; falha se já existir                     | cria                    |

Passe sempre `encoding="utf-8"` para textos com acento funcionarem igual em
qualquer sistema.

## with

Esquecer o `close` deixa o arquivo preso. A instrução `with` fecha o arquivo
sozinha, mesmo se ocorrer um erro:

```python
with open("notas.txt", encoding="utf-8") as arquivo:
    for linha in arquivo:
        print(linha.strip())
```

Escrita:

```python
with open("log.txt", "a", encoding="utf-8") as arquivo:
    arquivo.write("jogo iniciado\n")
```

`write` não coloca a quebra de linha: inclua `\n` você mesmo.

## Caminhos

Um caminho relativo vale para a pasta de onde o programa foi **iniciado**, não
para a pasta do script. Para um arquivo ao lado do código:

```python
import os

CAMINHO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorde.json")
```

Ou, com `pathlib`, `Path(__file__).parent / "recorde.json"`.

## JSON

JSON é um formato de texto para dicionários, listas, números, strings e
booleanos. É um formato muito usado para trocar dados entre programas e entre linguagens.

```python
import json

dados = {"recorde": 42, "jogador": "Ada"}

with open("recorde.json", "w", encoding="utf-8") as f:
    json.dump(dados, f)

with open("recorde.json", encoding="utf-8") as f:
    lidos = json.load(f)
```

O arquivo resultante: `{"recorde": 42, "jogador": "Ada"}`.

Tuplas viram listas no caminho de ida e volta, e chaves de dicionário viram
strings. Não é possível gravar objetos de classes sem convertê-los antes em
dicionários.

## Tratando erros

Na primeira partida o arquivo não existe, e um arquivo editado à mão pode ficar
quebrado. Trate os dois casos:

```python
def le_recorde():
    try:
        with open(CAMINHO, encoding="utf-8") as f:
            return json.load(f)["recorde"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 0
```

O programa completo está em [recorde.py](recorde.py): lê no início, grava só
quando o recorde é batido. A documentação do módulo está em
[formato-json.url](formato-json.url).

## Exercícios

1. Qual modo de `open` acrescenta ao final do arquivo?
2. Complete: `with ___("recorde.json") as f: dados = json.___(f)`.
3. O que acontece com `open("x.txt", "w")` se `x.txt` já tem conteúdo?
4. Guarde os cinco maiores recordes, não só um. Qual estrutura usar?
5. Por que é melhor gravar só quando o recorde for batido, e não em todo
   quadro?
