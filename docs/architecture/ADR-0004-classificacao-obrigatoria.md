# ADR-0004 — Toda a funcionalidade é classificada antes de ser escrita

Data: 2026-09-11 · Estado: aceite

## Contexto

A visão do produto tem dezenas de blocos possíveis: BI, hierarquia
empresarial, OKR, workflows, importação, API, integrações, documentos,
pesquisa global, copiloto, laboratório de dados, previsão, backup,
licenciamento, telemetria.

Cada um deles, visto isoladamente, parece pertencer ao núcleo. Se cada um
entrar por onde for mais rápido, o resultado é um monólito com um sistema de
plugins decorativo ao lado — precisamente o contrário do que justifica este
projeto.

## Decisão

**Nenhuma funcionalidade é escrita antes de ser classificada**, e a
classificação fica registada. As categorias:

| Categoria | O que é | Onde vive | Pode ser desligado? |
|---|---|---|---|
| **Core** | O que *todos* os módulos precisam e não faz sentido duplicar | `src/core/` | não |
| **Service** | Capacidade transversal, sem interface, usada por vários | `src/<nome>/` | não, mas é substituível |
| **Module** | Domínio de negócio (Projetos, RH, Estoque…) | plugin | sim |
| **Plugin** | Extensão opcional, incluindo integrações | `plugins/` | sim |
| **Agent** | Automatismo que decide, não só calcula | plugin | sim |
| **Skill** | Procedimento nomeado que um agente executa | plugin | sim |

**Entrar no Core exige justificação escrita.** A lista do que está no Core
vive em `core-inventory.json`, com uma frase por módulo a dizer porque é que
ali está — e há um teste que falha se aparecer um módulo novo em `src/core/`
sem essa justificação.

A pergunta a responder antes de escrever a primeira linha:

1. Quantos módulos precisam disto? Um? Então não é Core.
2. O produto funciona sem isto? Sim? Então é Module ou Plugin.
3. Isto decide alguma coisa, ou só calcula? Decide? Então é Agent.
4. Isto traz uma dependência nova? Então tem de ser Plugin (ADR-0002).

## Consequências

**Boas**

- O Core mantém-se pequeno o suficiente para ser compreendido inteiro.
- Um módulo de negócio que não sirva a um cliente desinstala-se, em vez de
  ficar como código morto atrás de um `if`.
- O licenciamento futuro passa a ser "que módulos estão autorizados", em vez
  de condicionais espalhadas.

**Custos**

- Mais fricção: cada funcionalidade obriga a uma decisão explícita, e a
  decisão é discutível. É o objetivo.
- Um Module tem de se contentar com o que o `ContextoPlugin` oferece. Quando
  isso não chega, a resposta certa é **melhorar o contrato**, não abrir uma
  exceção.

## Como se sabe que está a ser cumprido

`tests/test_arquitetura.py` verifica, a cada execução:

- todo o módulo em `src/core/` consta do inventário, com justificação;
- o Core não importa interface, análise nem relatórios;
- a análise e os relatórios não importam interface;
- nenhum plugin importa `banco_de_dados`, `gui` ou o `PluginManager`;
- `CLASSIFICACAO.md` menciona todos os módulos e plugins que existem;
- todo o nome de topo de `src/` está declarado, com o que faz ([ADR-0005](ADR-0005-nomes-de-topo.md)).

Uma regra de arquitetura que não falha um teste é uma sugestão.
