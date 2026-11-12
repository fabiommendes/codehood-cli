---
type: issue
status: backlog
tags: [push, testes, integracao]
kind: bug
priority: low
created: 2026-11-12
creator: claude
---

# Testes de integração do push falham depois de `db:reset`

Três testes de `tests/test_push_integration.py` falham contra um dev server
recém-semeado:

- `test_push_questions_matches_the_repository_exactly_and_reconverges`
- `test_a_pushed_question_carries_a_rev_and_an_edit_with_a_new_rev_is_other_cli`
- `test_a_rebuilt_base_of_a_full_course_syncs_without_a_decision_or_a_write`

O seed põe em `cs101/ada_2026-2` questões e um time slot criados no servidor
(`rev` nulo). Desde `3c58a3c` essas entidades são pull de criação e nunca
podáveis, então o plano mostra `pull question ...` e os testes, que esperam
um curso só com o que eles mesmos empurraram, falham. Não tem relação com a
escrita condicional (a CLI ainda não envia `If-Match`).

Correção provável: os testes usam um curso próprio, criado e apagado por eles,
ou ignoram as entidades com `rev` nulo que já existiam antes do primeiro push.
