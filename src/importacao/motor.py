"""Importar: para onde, com que colunas, e o que vai acontecer antes de acontecer.

Cada parte da aplicação **regista um destino**: que campos aceita, como se
valida uma linha, e como se cria. O motor não sabe o que é uma tarefa nem um
item de inventário — é o mesmo padrão da pesquisa e dos indicadores.

**Nunca se importa às cegas.** O fluxo é sempre: ler, mapear as colunas,
**prever**, e só então aplicar. A previsão corre as mesmas validações que a
importação, sem escrever nada — quem importa vê o que vai entrar, o que vai
ficar de fora, e porquê, antes de decidir.

Uma linha má não cancela as boas. Uma importação de 300 linhas que falha
inteira por causa de uma data mal escrita obriga a corrigir e repetir tudo;
importar 299 e dizer qual falhou é mais útil, e é o que uma pessoa faria.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core.log import obter_logger
from importacao.leitura import Tabela

logger = obter_logger(__name__)


@dataclass(frozen=True)
class Campo:
    """Um campo que um destino aceita."""

    nome: str
    chave_titulo: str = ""
    obrigatorio: bool = False
    exemplo: str = ""
    chave: bool = False
    """Se este campo identifica a linha, e não se pode repetir.

    Um destino valida contra o que já está guardado, e no momento da previsão
    ainda nada foi escrito — por isso duas linhas iguais **no mesmo ficheiro**
    passavam as duas e a segunda falhava só ao escrever. A previsão dizia 3 e
    entravam 2, e uma previsão que mente é pior do que não a haver.
    """

    def __post_init__(self) -> None:
        if not self.chave_titulo:
            object.__setattr__(self, "chave_titulo", f"campo_{self.nome}")


@dataclass(frozen=True)
class Destino:
    """Para onde se pode importar.

    Attributes:
        validar: recebe uma linha já mapeada e devolve os problemas dela.
            Devolver lista vazia é dizer "esta linha entra".
        criar: escreve a linha. Só é chamado depois de ``validar`` passar.
    """

    nome: str
    campos: Tuple[Campo, ...]
    validar: Callable[[Dict[str, str]], List[str]]
    criar: Callable[[Dict[str, str]], None]
    chave_titulo: str = ""
    permissao: Optional[str] = None
    dono: str = ""

    def obrigatorios(self) -> List[Campo]:
        return [campo for campo in self.campos if campo.obrigatorio]


@dataclass(frozen=True)
class Problema:
    """Uma linha que não entra, e a razão."""

    linha: int
    """Número da linha no ficheiro, contando o cabeçalho como 1."""

    motivo: str


@dataclass(frozen=True)
class Aceite:
    """Uma linha que passa, e de onde veio."""

    linha: int
    dados: Dict[str, str]


@dataclass
class Previsao:
    """O que vai acontecer se a importação for aplicada."""

    aceites: List[Aceite] = field(default_factory=list)
    problemas: List[Problema] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.aceites) + len(self.problemas)

    @property
    def tudo_bem(self) -> bool:
        return not self.problemas


@dataclass
class Resultado:
    """O que aconteceu depois de aplicar."""

    criados: int = 0
    problemas: List[Problema] = field(default_factory=list)

    @property
    def houve_falhas(self) -> bool:
        return bool(self.problemas)


_DESTINOS: Dict[str, Destino] = {}


# ------------------------------------------------------------------ registo


def registar(
    nome: str,
    campos: Sequence[Campo],
    validar: Callable[[Dict[str, str]], List[str]],
    criar: Callable[[Dict[str, str]], None],
    chave_titulo: str = "",
    permissao: Optional[str] = None,
    dono: str = "",
) -> Destino:
    """Põe um destino à disposição de quem importa.

    Raises:
        ValueError: nome vazio, sem campos, funções que não são chamáveis, ou
            — vindo de um módulo — nome fora do espaço de nomes desse módulo.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Um destino precisa de um nome.")
    if not campos:
        raise ValueError(f"O destino {nome!r} não declara campos nenhuns.")
    if not callable(validar) or not callable(criar):
        raise ValueError(f"O destino {nome!r} precisa de validar e criar.")
    if dono and not nome.startswith(f"{dono}."):
        raise ValueError(
            f"O módulo {dono!r} tem de prefixar os seus destinos com {dono + '.'!r}."
        )

    destino = Destino(
        nome, tuple(campos), validar, criar, chave_titulo or f"destino_{nome}",
        permissao, dono,
    )
    _DESTINOS[nome] = destino
    logger.info("Destino de importação registado: %s", nome)
    return destino


def esquecer_por_dono(dono: str) -> int:
    """Tira os destinos de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [nome for nome, d in _DESTINOS.items() if d.dono == dono]
    for nome in saem:
        _DESTINOS.pop(nome, None)
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _DESTINOS.clear()


def obter(nome: str) -> Optional[Destino]:
    return _DESTINOS.get((nome or "").strip())


def disponiveis() -> List[Destino]:
    """Os destinos que a sessão pode usar.

    Um destino que exige uma permissão que a sessão não tem **não aparece**:
    oferecer para depois recusar é pior do que não oferecer.
    """
    from core import permissoes

    return [
        _DESTINOS[nome]
        for nome in sorted(_DESTINOS)
        if _DESTINOS[nome].permissao is None
        or permissoes.pode(_DESTINOS[nome].permissao)
    ]


# --------------------------------------------------------------- mapeamento


def _simples(texto: str) -> str:
    """Sem acentos, sem maiúsculas, sem separadores — para comparar nomes."""
    sem_acentos = unicodedata.normalize("NFKD", str(texto or ""))
    limpo = "".join(c for c in sem_acentos if not unicodedata.combining(c))
    return "".join(c for c in limpo.lower() if c.isalnum())


def sugerir_mapa(tabela: Tabela, destino: Destino) -> Dict[str, str]:
    """Adivinha que coluna do ficheiro corresponde a cada campo.

    Compara sem acentos nem maiúsculas, e aceita que um contenha o outro —
    "Descrição da tarefa" serve para o campo "descricao". Uma sugestão errada
    corrige-se num clique; a alternativa é obrigar a mapear tudo à mão sempre,
    o que faz desistir à terceira coluna.

    Returns:
        ``{campo: coluna}``, só com o que foi possível adivinhar.
    """
    colunas = {_simples(coluna): coluna for coluna in tabela.cabecalho if coluna}
    mapa: Dict[str, str] = {}
    usadas = set()

    for campo in destino.campos:
        alvo = _simples(campo.nome)
        escolhida = colunas.get(alvo)
        if escolhida is None:
            for simples, original in colunas.items():
                if original in usadas:
                    continue
                if alvo and (alvo in simples or simples in alvo):
                    escolhida = original
                    break
        if escolhida is not None and escolhida not in usadas:
            mapa[campo.nome] = escolhida
            usadas.add(escolhida)
    return mapa


def _aplicar_mapa(linha: Dict[str, str], mapa: Dict[str, str]) -> Dict[str, str]:
    return {campo: (linha.get(coluna) or "").strip() for campo, coluna in mapa.items()}


# ----------------------------------------------------------------- previsão


def prever(tabela: Tabela, destino: Destino, mapa: Dict[str, str]) -> Previsao:
    """Diz o que vai acontecer, sem escrever nada.

    Corre as mesmas validações que a importação. Um destino cuja validação
    rebente é tratado como "esta linha não entra", com o erro na mensagem —
    um destino partido não pode passar por validação bem sucedida.
    """
    previsao = Previsao()
    em_falta = [
        campo.nome for campo in destino.obrigatorios() if campo.nome not in mapa
    ]
    if em_falta:
        previsao.problemas.append(
            Problema(0, f"Faltam colunas obrigatórias: {', '.join(sorted(em_falta))}.")
        )
        return previsao

    chaves = [campo.nome for campo in destino.campos if campo.chave]
    vistas: Dict[str, int] = {}

    for indice, bruta in enumerate(tabela.como_dicionarios(), start=2):
        dados = _aplicar_mapa(bruta, mapa)

        repetida = None
        for campo in chaves:
            valor = (dados.get(campo) or "").strip().lower()
            if not valor:
                continue
            if valor in vistas:
                repetida = f"{campo} repetido no ficheiro (já na linha {vistas[valor]})."
                break
            vistas[valor] = indice
        if repetida:
            previsao.problemas.append(Problema(indice, repetida))
            continue

        try:
            motivos = list(destino.validar(dados) or [])
        except Exception as erro:
            logger.exception("O destino %r falhou a validar.", destino.nome)
            motivos = [str(erro)]
        if motivos:
            previsao.problemas.append(Problema(indice, "; ".join(motivos)))
        else:
            previsao.aceites.append(Aceite(indice, dados))
    return previsao


def importar(tabela: Tabela, destino: Destino, mapa: Dict[str, str]) -> Resultado:
    """Aplica a importação: cria o que passa e reporta o que não passa.

    Cada linha é criada por si. Uma que rebente a meio é reportada e as
    seguintes continuam — uma importação de 300 linhas não pode ficar refém de
    uma data mal escrita na linha 7.

    Raises:
        PermissaoNegadaError: se a sessão não puder usar este destino.
    """
    if destino.permissao is not None:
        from core import permissoes

        permissoes.exigir(destino.permissao)

    previsao = prever(tabela, destino, mapa)
    resultado = Resultado(problemas=list(previsao.problemas))

    for aceite in previsao.aceites:
        try:
            destino.criar(aceite.dados)
            resultado.criados += 1
        except Exception as erro:
            # A previsão disse que passava e a escrita falhou: o destino tem
            # uma regra que só se vê ao escrever. O número da linha vem da
            # previsão, para quem corrige saber onde ir.
            logger.exception("Falha a criar a partir da importação.")
            resultado.problemas.append(Problema(aceite.linha, str(erro)))

    logger.info(
        "Importação para %s: %d criados, %d problemas.",
        destino.nome,
        resultado.criados,
        len(resultado.problemas),
    )
    return resultado
