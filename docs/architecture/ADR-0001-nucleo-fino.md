# ADR-0001 — Núcleo fino, módulos empresariais como plugins

Data: 2026-09-11 · Estado: aceite

## Contexto

A visão do produto inclui RH, Estoque, Financeiro, CRM, Produção, Compras,
Vendas, Manutenção e Qualidade. A tentação é criar esses módulos dentro da
aplicação, cada um com as suas tabelas, telas e regras.

O projeto tem hoje ~3.500 linhas e um Plugin Engine funcional: ciclo de vida
completo, instalação segura por ZIP, atualização com rollback, persistência de
estado e abstração de fontes.

## Decisão

O núcleo fica **fino**. Contém apenas o que todos os módulos precisam:

- versão, caminhos, configuração e logging;
- persistência com migrações;
- Plugin Engine;
- Event Bus;
- permissões;
- Analytics Engine;
- interface base (janela, abas, dashboard, tela de plugins).

Os módulos empresariais entram como **plugins**, usando o `ContextoPlugin`.
Nenhum deles passa a ser dependência do núcleo.

## Consequências

**Boas**

- Um módulo com defeito não derruba a aplicação: o isolamento do Plugin
  Engine já está implementado e testado.
- O cliente instala só o que usa; o licenciamento futuro passa a ser
  "que plugins estão autorizados", não código morto atrás de um `if`.
- O núcleo continua testável e empacotável em segundos.

**Custos**

- O `ContextoPlugin` tem de crescer de forma disciplinada: cada coisa nova que
  um módulo precisa é uma decisão de API, não um import atalho.
- Um módulo de negócio precisa de mais do que uma aba: precisa de tabelas
  próprias, permissões próprias e eventos próprios. O contexto terá de
  oferecer isso antes do primeiro módulo empresarial real.

## Alternativas consideradas

- **Tudo no núcleo**: mais rápido no início, mas transforma a aplicação num
  monólito e contradiz a razão de existir do Plugin Engine.
- **Serviços separados / cliente-servidor**: resolve escala que este produto
  ainda não tem, e custa uma reescrita. Fica para quando houver multiempresa
  real.
