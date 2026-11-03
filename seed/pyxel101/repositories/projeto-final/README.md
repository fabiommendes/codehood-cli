# Projeto final: template do grupo

Este repositório é o ponto de partida do jogo do seu grupo. Um integrante clona
o template, os demais fazem `git pull` e todos trabalham a partir dele.

## Primeiros passos

```bash
pip install -r requirements.txt
python -m pytest        # o teste mínimo já passa
python main.py          # abre a janela com a tela de título
```

## Estrutura

| Caminho | Para que serve |
| :-- | :-- |
| `main.py` | Liga o Pyxel ao jogo. Só desenha e lê o teclado. |
| `game/state.py` | Telas do jogo: título, jogo e fim. |
| `game/entities.py` | `Player` e `Enemy`, sem dependência do Pyxel. |
| `assets/sprites.png` | Folha de sprites inicial (tiles de 8 x 8). |
| `tests/` | Testes pytest. Acrescente os do seu jogo aqui. |
| `RUBRICA.md` | Como o projeto é avaliado. |
| `CONTRIBUTING.md` | Fluxo de git do grupo. |

## O que entregar

Um jogo completo e jogável, com tela de título, ao menos uma mecânica de
colisão, pontuação e fim de jogo, testes automatizados da lógica e um README
próprio explicando como jogar. O enunciado completo e as datas estão nos
materiais da disciplina. Substitua este README pelo do seu jogo antes da
apresentação.
