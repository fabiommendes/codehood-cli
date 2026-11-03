# Fluxo de trabalho do grupo

O jogo é do grupo, mas a nota do projeto é individual: a divisão do trabalho
tem de aparecer no histórico do git.

1. **Um ramo por tarefa.** Crie `git switch -c nome/tarefa` a partir de `main`.
2. **Commits pequenos, no seu nome.** Configure `git config user.name` e
   `user.email` com os seus dados. Commits feitos por outra pessoa na sua
   máquina não contam como seus.
3. **Atualize com `git pull --no-rebase`.** Versões recentes do git recusam
   um `git pull` simples quando os ramos divergiram.
4. **Junte em `main` por pedido de revisão** de outro integrante, ou por
   `git merge` depois de conversar com o grupo.
5. **Rode `python -m pytest` antes de enviar.** `main` nunca fica com teste
   quebrado.
6. **Mensagens de commit** dizem o que mudou: "Adiciona colisão da nave com
   inimigos", não "ajustes".

Cada integrante precisa ter commits com código, e não só com documentação ou
arquivos de imagem.
