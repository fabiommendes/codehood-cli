---
title: return ou print
tags: [funcoes, retorno]
locale: pt-BR
shuffle: true
---

O que o programa abaixo mostra no terminal?

```python
def dobra(x):
    print(x * 2)


resultado = dobra(4)
print(resultado)
```

* [ ] `8` e depois `8`
  > `dobra` imprime, mas não devolve nada. Sem `return`, o valor de `resultado` não é 8.
* [*] `8` e depois `None`
  > A chamada imprime 8 e devolve `None`, o valor padrão de uma função sem `return`.
* [ ] Apenas `None`
  > O `print` dentro de `dobra` também executa, então o 8 aparece primeiro.
* [ ] Um `TypeError`, porque `dobra` não devolve um valor
  > Atribuir o resultadoado de uma função sem `return` é permitido. A variável fica com `None`.
