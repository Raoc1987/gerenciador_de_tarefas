# ADR-0011 — "Ver todas" passa a querer dizer "as da minha empresa"

Data: 2026-09-19 · Estado: aceite

## Contexto

A estrutura da organização já suportava várias empresas desde o ADR que a
criou: *"uma empresa é uma raiz; tudo o resto tem de ter um pai"*. O que não
existia era **isolamento**.

`tarefas_servico.ambito()` devolvia, para quem tivesse `tarefas.ver_todas`, um
âmbito sem filtro nenhum:

```python
if ve_tudo():
    return Ambito()          # sem filtro
```

Numa instalação com uma empresa, isso é a mesma coisa. Com duas, quem
administra a primeira via as tarefas da segunda — e a segunda as da primeira.

Isto foi assinalado como **o único item cujo custo cresce enquanto espera**:
cada módulo escrito sem noção de empresa é mais um a migrar depois.

## Decisão

`ver_todas` passa a significar **todas as da minha empresa**. O âmbito ganhou
um campo que *estreita* — os outros dois alargam — e o armazenamento ganhou
uma condição correspondente.

### Três casos em que o isolamento **não** se aplica

Os três são deliberados, e cada um protege uma instalação que hoje funciona:

1. **Há uma empresa ou nenhuma.** Filtrar não mudava o que se vê, e mudaria o
   que acontece. O isolamento começa a valer no dia em que a segunda empresa é
   criada.
2. **Quem está em sessão não tem unidade.** Não pertence a empresa nenhuma;
   limitá-lo à "sua" deixava-o sem nada. É o caso de quem instala e administra
   sem se pôr no organigrama — exatamente quem precisa de ver tudo quando há
   um problema.
3. **A estrutura não responde.** Um erro a ler a organização não pode esconder
   tarefas: deixa tudo como estava e fica no registo.

### As tarefas sem unidade ficam sempre dentro

São anteriores à estrutura e não pertencem a empresa nenhuma. Sem esta
exceção, **criar a segunda empresa fazia desaparecer o histórico inteiro do
ecrã de toda a gente**. O dado continuaria no banco — e ninguém acreditaria
nisso.

### `pode_ver` tem de concordar com `listar`

Já era uma promessa escrita, e agora há mais um caminho por onde podia deixar
de o ser. Se discordassem, havia tarefas que apareciam na lista e não abriam —
ou, pior, que não apareciam e abriam na mesma por id.

A contagem por pessoa passou a usar o âmbito em vez da tabela inteira: somava
as tarefas das outras empresas, e um número que não se explica a partir do que
está no ecrã é um número errado.

## Consequências

**Boas**

- A fuga entre empresas está fechada no sítio onde a política já vivia — um
  só, garantido por um teste de arquitetura.
- Um módulo de negócio escrito a partir de agora herda o isolamento das
  tarefas sem fazer nada.

**Custos**

- Mais um campo no âmbito e mais uma condição no SQL.
- `unidades_da_minha_empresa()` corre a cada `ambito()`, e com estrutura
  grande isso é uma travessia da árvore por listagem. Não é medido, e por isso
  **não se afirma que é rápido**: se vier a notar-se, o sítio para guardar o
  resultado é a sessão, que já existe.

## O que este ADR **não** faz

Isto isola **tarefas**. Não isola:

- **os dados dos plugins.** `core/plugin_dados.py` dá a cada plugin um ficheiro
  SQLite e não tem noção nenhuma de empresa. Um módulo de negócio que guarde
  itens continua a guardá-los para a instalação inteira. É a peça seguinte, e
  é maior: mexe no contrato dos plugins;
- **a auditoria, as contas, as unidades** e a configuração;
- **a escolha de empresa na interface.** Não há seletor: a empresa é a de quem
  está em sessão. Um seletor implica poder estar noutra, e isso é uma decisão
  de permissões que ainda não foi tomada.

Está escrito para não ser lido como "a multiempresa está feita". Não está: o
que está feito é a metade que estava a vazar.
