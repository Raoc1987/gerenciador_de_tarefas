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
| Posse dos plugins e atualização dos embutidos ([ADR-0006](ADR-0006-posse-dos-plugins.md)) | ✅ implementado |
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

### O que vem a seguir

**Não está aqui.** Está em [CLASSIFICACAO.md](CLASSIFICACAO.md), e está lá
sozinho de propósito.

Esta secção já teve a sua própria lista, e a lista envelheceu sem ninguém
reparar: continuava a dizer que o `ContextoPlugin` não oferecia tabelas nem
permissões próprias a um plugin, várias etapas depois de passar a oferecer
as duas. Não foi desleixo — foi o resultado previsível de a mesma decisão
estar escrita em dois sítios. Dois roteiros divergem; a única pergunta é
quando.

`CLASSIFICACAO.md` é o que se mantém, porque é o que um teste obriga a
manter: nenhum módulo ou plugin pode existir sem lá constar. Um documento
que falha a construção quando mente vale mais do que dois que concordam
por acaso.

Ver os ADRs nesta pasta para as decisões e os seus porquês.
