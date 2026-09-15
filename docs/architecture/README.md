# Arquitetura da plataforma

O produto evolui de **gestor de tarefas** para **plataforma modular de gestão**,
mantendo a gestão de tarefas como núcleo inicial.

A regra que organiza tudo o resto: **os módulos empresariais (RH, Estoque,
Financeiro, CRM, Manutenção…) não entram no núcleo.** O núcleo prepara-lhes o
terreno — plugins, eventos, permissões, análise — para que possam ser
acrescentados sem transformar o programa num monólito.

## Camadas

```
        ┌──────────────────────────────────────────────┐
   UI   │  gui.py · dashboard_ui.py · plugin_ui.py     │
        ├──────────────────────────────────────────────┤
 APP    │  analitica/ (métricas, séries, insights)     │
        │  relatorios/ (relatórios e exportação)       │
        ├──────────────────────────────────────────────┤
 CORE   │  eventos · permissoes · auditoria · plugins  │
        │  config · version · paths · log              │
        ├──────────────────────────────────────────────┤
 INFRA  │  banco_de_dados.py (SQLite + migrações)      │
        └──────────────────────────────────────────────┘
```

Regras de dependência, verificadas por testes:

- a **UI** pode usar tudo abaixo dela;
- **analitica** e **relatorios** não importam UI nem plugins;
- o **core** não importa UI nem analitica;
- **plugins** não importam `banco_de_dados`, `gui` nem o `PluginManager`: tudo o que
  usam chega pelo `ContextoPlugin`.

## A espinha de dados

A análise não é uma tela isolada — atravessa o produto:

```
ação do utilizador
      ↓
banco_de_dados ─publica─►  Event Bus  ──►  plugins / notificações / auditoria
      ↓
analitica (métricas, séries, tendências)
      ↓
dashboard (KPIs, gráficos)
      ↓
insights (descritivo → diagnóstico → preditivo)
      ↓
relatórios (PDF · XLSX · CSV)
```

O Event Bus alimenta também a **auditoria**, que grava o que aconteceu sem
que nenhum módulo saiba que ela existe.

Cada peça é utilizável sozinha e testável sem interface.

## Estado atual

| Bloco | Estado |
|---|---|
| Core: versão, caminhos, config, log | ✅ implementado |
| Persistência com migrações versionadas | ✅ implementado |
| Plugin Engine (ciclo de vida, ZIP seguro, rollback, fontes) | ✅ implementado |
| Idiomas (app + plugins) | ✅ implementado |
| Empacotamento e instalador Windows | ✅ implementado e testado |
| **Event Bus** | ✅ implementado |
| **Permissões (RBAC)** | ✅ implementado |
| **Analytics Engine** | ✅ implementado |
| **Dashboard + gráficos** | ✅ implementado |
| **Auditoria persistida** | ✅ implementado |
| **Relatórios e exportação (PDF, XLSX, CSV)** | ✅ implementado |
| **Autenticação de utilizadores** | ✅ implementado |
| **Dono das tarefas e visibilidade por papel** | ✅ implementado |
| **Verificação de atualizações** | ✅ implementado (como plugin) |
| Multiempresa | ❌ **NÃO IMPLEMENTADO** |
| Licenciamento | ❌ **NÃO IMPLEMENTADO** |
| Módulos empresariais (RH, Estoque, Financeiro…) | ❌ **NÃO IMPLEMENTADO** — por desenho: entram como plugins |
| Data Science (modelos) | ⚠️ parcial — tendência, previsão linear e anomalias por estatística simples; sem ML |

## Roadmap

Concluído: **FASE 0** (auditoria) · **FASE 1** (fundação arquitetural) ·
FASE 3 (Plugin Engine) · FASE 6–8 (Analytics, visualização, dashboard) ·
FASE 17–18 (empacotamento e instalador).

Também concluído: **relatórios e exportação** e **auditoria persistida**.

Também concluído: **autenticação** e o **plugin de atualizações**.

A seguir, por ordem de valor:

1. **SDK de dados e permissões para plugins** — um módulo de negócio precisa
   de tabelas próprias, permissões próprias e migrações próprias, e o
   `ContextoPlugin` ainda não dá nada disso. Tem de vir **antes** do primeiro
   módulo, ou ele acabará a importar `banco_de_dados` diretamente. (A resolver
   também aí: um plugin que importe um módulo vizinho usa um nome global —
   dois plugins com um `verificador.py` colidiriam.)
2. **Módulo Projetos** — primeiro módulo de gestão, já como plugin, para
   provar que o Plugin Engine aguenta um módulo de negócio a sério: tabelas
   próprias, permissões próprias e eventos próprios.
3. **Multiempresa** — isolamento de dados por empresa.
4. **Licenciamento** — só depois de existir algo que valha a pena licenciar.
5. **Cifrar o banco** — hoje a autenticação protege o uso da aplicação, não o
   ficheiro em disco.

Uma nota sobre a ordem: o `ContextoPlugin` ainda não oferece tabelas próprias
nem permissões próprias a um plugin. Isso tem de ser decidido **antes** do
primeiro módulo de negócio, ou o módulo acabará a importar `banco_de_dados`
diretamente e a furar a arquitetura.

Ver os ADRs nesta pasta para as decisões e os seus porquês.
