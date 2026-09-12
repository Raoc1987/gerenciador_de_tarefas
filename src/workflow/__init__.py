"""Automação por regras: quando acontece X, e se Y, então faz Z.

É um **Service** (ADR-0004): atravessa os módulos, não tem domínio próprio e
não tem interface. Não é um Agent — não decide nada. Executa regras que uma
pessoa escreveu, e só ações que alguém registou.

O motor não conhece tarefas nem inventário. Quem tem uma ação para oferecer
regista-a (:mod:`workflow.acoes`); o motor liga o que aconteceu ao que fazer,
e mais nada. É o que permite a um módulo novo participar em automações sem
tocar aqui.
"""
