"""Estrutura da organização: quem está sob quem.

Permissões por âmbito, propriedade de dados e multiempresa dependem todas de
saber onde cada pessoa está. É por isso que isto é Core e não um módulo: não
serve um domínio, serve todos.

**Uma árvore só.** Não há uma tabela para empresas, outra para departamentos e
outra para equipas. Há nós com um ``tipo``, e um nó tem um pai. As empresas não
são todas iguais — há divisões, regiões, filiais, turnos — e com uma tabela por
nível cada formato novo seria uma migração no banco de toda a gente. Aqui é uma
linha. E a travessia escreve-se uma vez em vez de três.

As regras que este módulo garante:

* uma empresa é uma raiz; tudo o resto tem de ter um pai;
* dois irmãos não podem ter o mesmo nome;
* nenhuma unidade pode ficar debaixo de si própria, direta ou indiretamente;
* uma unidade com conteúdo não desaparece por engano.

Quem não usa estrutura nenhuma não tem de a criar: a tabela vazia é um estado
válido, e o resto da aplicação funciona sem ela.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Sequence

from core import eventos
from core.log import obter_logger

logger = obter_logger(__name__)

#: Separador usado ao escrever um caminho legível.
SEPARADOR_CAMINHO = " > "


class TipoUnidade(str, Enum):
    """O que uma unidade é.

    O tipo é descritivo: a estrutura vive na relação pai/filho, não aqui. Só
    :attr:`EMPRESA` tem uma regra própria — é raiz.
    """

    EMPRESA = "empresa"
    DEPARTAMENTO = "departamento"
    EQUIPA = "equipa"


# --------------------------------------------------------------------- erros


class OrganizacaoError(Exception):
    """Erro base da estrutura da organização."""

    chave_mensagem = "organizacao_erro"


class UnidadeNaoEncontradaError(OrganizacaoError):
    """A unidade indicada não existe."""

    chave_mensagem = "unidade_nao_encontrada"


class NomeDuplicadoError(OrganizacaoError):
    """Já existe uma unidade com esse nome no mesmo sítio."""

    chave_mensagem = "unidade_nome_duplicado"


class EstruturaInvalidaError(OrganizacaoError):
    """A relação pedida não é possível: uma empresa com pai, ou um ciclo."""

    chave_mensagem = "unidade_estrutura_invalida"


class UnidadeComConteudoError(OrganizacaoError):
    """A unidade tem sub-unidades e não pode ser removida assim."""

    chave_mensagem = "unidade_com_conteudo"


# -------------------------------------------------------------------- modelo


@dataclass(frozen=True)
class Unidade:
    """Um nó da estrutura."""

    id: int
    nome: str
    tipo: TipoUnidade
    pai_id: Optional[int]
    ativa: bool
    criada_em: str

    @property
    def e_raiz(self) -> bool:
        """Se não tem nada acima dela."""
        return self.pai_id is None


_COLUNAS = "id, nome, tipo, pai_id, ativa, criada_em"


def _para_unidade(linha) -> Unidade:
    return Unidade(
        id=linha[0],
        nome=linha[1],
        tipo=TipoUnidade(linha[2]),
        pai_id=linha[3],
        ativa=bool(linha[4]),
        criada_em=linha[5],
    )


def _conectar():
    import banco_de_dados

    banco_de_dados.criar_tabela()
    return banco_de_dados.conectar()


# -------------------------------------------------------------------- leitura


def obter(unidade_id: int) -> Optional[Unidade]:
    """Uma unidade pelo id, ou ``None``."""
    with _conectar() as conexao:
        linha = conexao.execute(
            f"SELECT {_COLUNAS} FROM unidades WHERE id = ?", (unidade_id,)
        ).fetchone()
    return _para_unidade(linha) if linha else None


def exigir(unidade_id: int) -> Unidade:
    """A unidade, ou :class:`UnidadeNaoEncontradaError`."""
    unidade = obter(unidade_id)
    if unidade is None:
        raise UnidadeNaoEncontradaError(f"Unidade {unidade_id} não existe.")
    return unidade


def listar(incluir_inativas: bool = False) -> List[Unidade]:
    """Toda a estrutura, dos pais para os filhos e por nome."""
    consulta = f"SELECT {_COLUNAS} FROM unidades"
    if not incluir_inativas:
        consulta += " WHERE ativa = 1"
    consulta += " ORDER BY COALESCE(pai_id, 0), nome COLLATE NOCASE"
    with _conectar() as conexao:
        return [_para_unidade(linha) for linha in conexao.execute(consulta)]


def raizes(incluir_inativas: bool = False) -> List[Unidade]:
    """As unidades sem pai — tipicamente as empresas."""
    return [u for u in listar(incluir_inativas) if u.e_raiz]


def filhos(unidade_id: int, incluir_inativas: bool = False) -> List[Unidade]:
    """Os filhos diretos, por nome."""
    consulta = f"SELECT {_COLUNAS} FROM unidades WHERE pai_id = ?"
    if not incluir_inativas:
        consulta += " AND ativa = 1"
    consulta += " ORDER BY nome COLLATE NOCASE"
    with _conectar() as conexao:
        return [
            _para_unidade(linha) for linha in conexao.execute(consulta, (unidade_id,))
        ]


def descendentes(
    unidade_id: int, incluir_propria: bool = True, incluir_inativas: bool = False
) -> List[Unidade]:
    """A sub-árvore inteira, a qualquer profundidade.

    É a pergunta que as permissões por âmbito fazem: *o que é que esta pessoa
    alcança a partir daqui?* Resolvida no banco, numa consulta, para o custo
    não crescer com o tamanho da empresa.
    """
    consulta = f"""
        WITH RECURSIVE arvore(id) AS (
            SELECT id FROM unidades WHERE id = ?
            UNION ALL
            SELECT u.id FROM unidades u JOIN arvore a ON u.pai_id = a.id
        )
        SELECT {_COLUNAS} FROM unidades
        WHERE id IN (SELECT id FROM arvore)
    """
    parametros: List = [unidade_id]
    if not incluir_propria:
        consulta += " AND id <> ?"
        parametros.append(unidade_id)
    if not incluir_inativas:
        consulta += " AND ativa = 1"
    consulta += " ORDER BY COALESCE(pai_id, 0), nome COLLATE NOCASE"

    with _conectar() as conexao:
        return [_para_unidade(linha) for linha in conexao.execute(consulta, parametros)]


def ancestrais(unidade_id: int) -> List[Unidade]:
    """Da raiz até ao pai, sem incluir a própria unidade."""
    cadeia: List[Unidade] = []
    atual = obter(unidade_id)
    vistos = set()
    while atual is not None and atual.pai_id is not None:
        if atual.pai_id in vistos:  # pragma: no cover - defensivo
            logger.error("Ciclo detetado acima da unidade %s.", unidade_id)
            break
        vistos.add(atual.pai_id)
        atual = obter(atual.pai_id)
        if atual is not None:
            cadeia.append(atual)
    return list(reversed(cadeia))


def caminho(unidade_id: int) -> str:
    """O caminho legível, ex.: ``"Acme > Engenharia > Plataforma"``."""
    unidade = obter(unidade_id)
    if unidade is None:
        return ""
    nomes = [u.nome for u in ancestrais(unidade_id)] + [unidade.nome]
    return SEPARADOR_CAMINHO.join(nomes)


def empresa_de(unidade_id: int) -> Optional[Unidade]:
    """A raiz a que esta unidade pertence."""
    unidade = obter(unidade_id)
    if unidade is None:
        return None
    if unidade.e_raiz:
        return unidade
    cadeia = ancestrais(unidade_id)
    return cadeia[0] if cadeia else None


class EmpresaForaDoAlcanceError(OrganizacaoError):
    """Tentou-se escolher uma empresa que esta sessão não pode ver."""

    chave_mensagem = "empresa_fora_do_alcance"


#: A empresa escolhida nesta sessão, e **por quem**.
#:
#: O nome vai junto de propósito. Sem ele, a escolha da Ana sobrevivia ao
#: fim da sessão dela e passava a valer para quem entrasse a seguir — uma
#: fuga silenciosa, e do tipo que só aparece na máquina de um cliente com
#: duas pessoas a partilhar um computador.
_escolha: Optional[tuple] = None


def _empresa_da_conta() -> Optional[int]:
    """A empresa a que a conta em sessão pertence, pela estrutura.

    É o que **fixa** o alcance: quem está dentro de uma empresa não escolhe
    nenhuma, porque já só pode ver a sua.
    """
    from core import permissoes, utilizadores

    conta = utilizadores.obter(permissoes.sessao().utilizador)
    if conta is None or conta.unidade_id is None:
        return None
    empresa = empresa_de(conta.unidade_id)
    return empresa.id if empresa is not None else None


def empresas_ao_alcance() -> List[Unidade]:
    """As empresas que esta sessão pode ver — a lista do seletor.

    Vazia quando não há nada para escolher: uma empresa ou nenhuma. Com uma
    entrada só quando a conta pertence a uma empresa — e aí não há escolha
    nenhuma a fazer, que é o que a interface usa para não mostrar o seletor.

    **Esta lista é o limite.** :func:`escolher_empresa` não aceita nada que
    não esteja aqui, e é essa a diferença entre um filtro e um buraco: um
    seletor que alargasse o alcance seria uma forma de ver os dados de outro
    cliente carregando num menu.
    """
    try:
        todas = raizes()
        if len(todas) < 2:
            return []
        fixa = _empresa_da_conta()
        if fixa is not None:
            return [u for u in todas if u.id == fixa]
        return todas
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha a listar as empresas ao alcance.")
        return []


def empresa_escolhida() -> Optional[int]:
    """A empresa escolhida nesta sessão, ou ``None`` para "todas".

    Revalida sempre, em vez de confiar no que foi guardado: a escolha pode
    ter sido feita por outra pessoa, ou a empresa pode ter sido removida
    entretanto. Uma escolha que deixou de ser válida vale o mesmo que nenhuma.
    """
    if _escolha is None:
        return None
    from core import permissoes

    quem, empresa_id = _escolha
    if quem != permissoes.sessao().utilizador:
        return None
    if not any(u.id == empresa_id for u in empresas_ao_alcance()):
        return None
    return empresa_id


def escolher_empresa(empresa_id: Optional[int]) -> None:
    """Estreita a vista a uma empresa. ``None`` volta a todas as que alcança.

    Raises:
        EmpresaForaDoAlcanceError: a empresa não está em
            :func:`empresas_ao_alcance`. **Só estreita, nunca alarga** — e
            recusa em vez de ignorar, porque ignorar deixava a interface a
            mostrar um nome e os dados de outro.
    """
    global _escolha
    from core import eventos, permissoes

    if empresa_id is None:
        _escolha = None
    else:
        empresa_id = int(empresa_id)
        if not any(u.id == empresa_id for u in empresas_ao_alcance()):
            raise EmpresaForaDoAlcanceError(
                f"A empresa {empresa_id} não está ao alcance desta sessão."
            )
        _escolha = (permissoes.sessao().utilizador, empresa_id)

    logger.info("Empresa escolhida: %s", empresa_id)
    eventos.publicar(eventos.EMPRESA_ESCOLHIDA, origem="organizacao",
                     empresa=empresa_id)


def limpar_escolha() -> None:
    """Esquece a escolha. Estado global: os testes têm de o repor."""
    global _escolha
    _escolha = None


def empresa_da_sessao() -> Optional[int]:
    """A empresa de quem está em sessão — ``None`` quando não há isolamento.

    **O único sítio onde se decide se o isolamento entre empresas se aplica.**
    Estava dentro do serviço de tarefas, e mudou-se para aqui quando os
    plugins passaram a precisar da mesma resposta: duas implementações da
    mesma decisão divergem, e a que divergisse seria uma fuga de dados.

    Devolve ``None`` — ou seja, **sem isolamento** — em três casos, e os três
    protegem uma instalação que hoje funciona:

    * **há uma empresa ou nenhuma.** Filtrar não mudava o que se vê, e
      mudaria o que acontece. O isolamento começa a valer no dia em que a
      segunda empresa é criada;
    * **quem está em sessão não tem unidade.** Não pertence a empresa
      nenhuma: limitá-lo à "sua" deixava-o sem nada. É o caso de quem
      instala e administra sem se pôr no organigrama;
    * **a estrutura não responde.** Um erro a ler a organização não pode
      esconder dados — deixa tudo como estava e fica no registo.
    """
    try:
        if len(raizes()) < 2:
            return None
        fixa = _empresa_da_conta()
        if fixa is not None:
            return fixa
        # Quem não está na estrutura vê tudo — e pode estreitar a vista a uma
        # empresa de cada vez. A escolha só entra por aqui: é o que faz as
        # tarefas e os dados dos módulos seguirem-na sem saberem que ela
        # existe.
        return empresa_escolhida()
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha a determinar a empresa da sessão.")
        return None


def unidades_da_empresa_da_sessao() -> Sequence[int]:
    """As unidades da empresa em sessão — vazio quando não há isolamento.

    Devolve um tuplo vazio, e não uma lista, no caso de não haver isolamento:
    é o mesmo valor que o âmbito das tarefas já usava como omissão, e manter
    o tipo faz deste refactor uma mudança que nenhum teste tem de acompanhar.
    """
    empresa = empresa_da_sessao()
    if empresa is None:
        return ()
    try:
        return [u.id for u in descendentes(empresa)]
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha a listar as unidades da empresa da sessão.")
        return ()


def esta_sob(unidade_id: int, ancestral_id: int) -> bool:
    """Se ``unidade_id`` está em qualquer nível abaixo de ``ancestral_id``.

    Uma unidade está sob si própria: quem manda numa unidade manda nela.
    """
    if unidade_id == ancestral_id:
        return True
    return any(u.id == ancestral_id for u in ancestrais(unidade_id))


# -------------------------------------------------------------------- escrita


def _validar_lugar(tipo: TipoUnidade, pai_id: Optional[int]) -> None:
    if tipo == TipoUnidade.EMPRESA:
        if pai_id is not None:
            raise EstruturaInvalidaError("Uma empresa não tem unidade acima dela.")
        return
    if pai_id is None:
        raise EstruturaInvalidaError(
            f"Uma unidade do tipo {tipo.value!r} tem de pertencer a alguma coisa."
        )
    exigir(pai_id)


def _exigir_nome_livre(
    nome: str, pai_id: Optional[int], excluir: Optional[int] = None
) -> None:
    """Dois irmãos com o mesmo nome tornam a estrutura ilegível."""
    parametros: List = []
    if pai_id is None:
        consulta = "SELECT 1 FROM unidades WHERE pai_id IS NULL"
    else:
        consulta = "SELECT 1 FROM unidades WHERE pai_id = ?"
        parametros.append(pai_id)
    consulta += " AND nome = ? COLLATE NOCASE"
    parametros.append(nome)
    if excluir is not None:
        consulta += " AND id <> ?"
        parametros.append(excluir)

    with _conectar() as conexao:
        if conexao.execute(consulta, parametros).fetchone():
            raise NomeDuplicadoError(f"Já existe {nome!r} neste sítio.")


def criar(
    nome: str,
    tipo: TipoUnidade = TipoUnidade.DEPARTAMENTO,
    pai_id: Optional[int] = None,
) -> Unidade:
    """Cria uma unidade.

    Raises:
        ValueError: se o nome for vazio.
        EstruturaInvalidaError: empresa com pai, ou sub-unidade sem pai.
        NomeDuplicadoError: se já existir um irmão com o mesmo nome.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("A unidade precisa de um nome.")
    tipo = TipoUnidade(tipo)
    _validar_lugar(tipo, pai_id)
    _exigir_nome_livre(nome, pai_id)

    agora = datetime.now().isoformat(timespec="seconds")
    with _conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO unidades (nome, tipo, pai_id, ativa, criada_em) "
            "VALUES (?, ?, ?, 1, ?)",
            (nome, tipo.value, pai_id, agora),
        )
        novo_id = cursor.lastrowid

    logger.info("Unidade criada: %s (%s)", nome, tipo.value)
    eventos.publicar(
        eventos.UNIDADE_CRIADA,
        origem="organizacao",
        id=novo_id,
        unidade=nome,
        tipo=tipo.value,
    )
    return exigir(novo_id)


def renomear(unidade_id: int, nome: str) -> Unidade:
    """Muda o nome, mantendo o lugar."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("A unidade precisa de um nome.")
    unidade = exigir(unidade_id)
    _exigir_nome_livre(nome, unidade.pai_id, excluir=unidade_id)

    with _conectar() as conexao:
        conexao.execute("UPDATE unidades SET nome = ? WHERE id = ?", (nome, unidade_id))
    eventos.publicar(
        eventos.UNIDADE_ALTERADA,
        origem="organizacao",
        id=unidade_id,
        unidade=nome,
        antes={"nome": unidade.nome},
        depois={"nome": nome},
    )
    return exigir(unidade_id)


def mover(unidade_id: int, novo_pai_id: Optional[int]) -> Unidade:
    """Muda a unidade de lugar, com a sub-árvore inteira atrás dela.

    Raises:
        EstruturaInvalidaError: se o destino estiver dentro da própria
            sub-árvore — uma unidade não pode ficar debaixo de si própria.
    """
    unidade = exigir(unidade_id)
    _validar_lugar(unidade.tipo, novo_pai_id)

    if novo_pai_id is not None:
        dentro = {u.id for u in descendentes(unidade_id, incluir_inativas=True)}
        if novo_pai_id in dentro:
            raise EstruturaInvalidaError(
                "Uma unidade não pode passar a estar debaixo de si própria."
            )

    _exigir_nome_livre(unidade.nome, novo_pai_id, excluir=unidade_id)
    with _conectar() as conexao:
        conexao.execute(
            "UPDATE unidades SET pai_id = ? WHERE id = ?", (novo_pai_id, unidade_id)
        )
    logger.info("Unidade %s movida para %s.", unidade_id, novo_pai_id)
    eventos.publicar(
        eventos.UNIDADE_ALTERADA,
        origem="organizacao",
        id=unidade_id,
        pai_id=novo_pai_id,
        antes={"pai_id": unidade.pai_id},
        depois={"pai_id": novo_pai_id},
    )
    return exigir(unidade_id)


def definir_ativa(unidade_id: int, ativa: bool = True) -> Unidade:
    """Desativa (ou reativa) uma unidade sem apagar o histórico.

    Uma equipa que deixou de existir não devia desaparecer dos registos do que
    fez. Desativar é a resposta certa quase sempre; :func:`remover` é para
    quando a unidade foi um engano.
    """
    anterior = exigir(unidade_id)
    with _conectar() as conexao:
        conexao.execute(
            "UPDATE unidades SET ativa = ? WHERE id = ?",
            (1 if ativa else 0, unidade_id),
        )
    eventos.publicar(
        eventos.UNIDADE_ALTERADA,
        origem="organizacao",
        id=unidade_id,
        ativa=ativa,
        antes={"ativa": anterior.ativa},
        depois={"ativa": bool(ativa)},
    )
    return exigir(unidade_id)


def remover(unidade_id: int) -> None:
    """Apaga uma unidade vazia.

    Raises:
        UnidadeComConteudoError: se tiver sub-unidades. Apagar em cascata a
            estrutura de uma empresa nunca é o que alguém queria fazer num
            clique; mova ou desative primeiro.
    """
    exigir(unidade_id)
    restantes = filhos(unidade_id, incluir_inativas=True)
    if restantes:
        raise UnidadeComConteudoError(
            f"A unidade tem {len(restantes)} sub-unidade(s). "
            "Mova-as ou remova-as primeiro."
        )

    with _conectar() as conexao:
        conexao.execute("DELETE FROM unidades WHERE id = ?", (unidade_id,))
    logger.info("Unidade removida: %s", unidade_id)
    eventos.publicar(eventos.UNIDADE_REMOVIDA, origem="organizacao", id=unidade_id)
