"""Ponto de entrada da exportação de relatórios."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Tuple

from core import funcionalidades
from core.log import obter_logger
from core.permissoes import Permissao, exigir
from reporting import exportadores
from reporting.modelo import Relatorio

logger = obter_logger(__name__)


def formatos_disponiveis() -> Tuple[str, ...]:
    """Formatos que podem ser gerados, na ordem a mostrar ao utilizador."""
    return exportadores.FORMATOS


def nome_sugerido(relatorio: Relatorio, formato: str) -> str:
    """Nome de arquivo sugerido, com data e hora para não sobrescrever nada."""
    base = "".join(
        caractere if caractere.isalnum() or caractere in " -_" else "_"
        for caractere in relatorio.titulo
    ).strip().replace(" ", "_")
    carimbo = (relatorio.gerado_em or datetime.now()).strftime("%Y%m%d_%H%M")
    return f"{base or 'relatorio'}_{carimbo}{exportadores.extensao(formato)}"


def exportar(relatorio: Relatorio, destino: Path, formato: str = "") -> Path:
    """Grava o relatório no formato pedido.

    O formato é deduzido da extensão do destino quando não é indicado.

    Raises:
        FuncionalidadeDesligadaError: se a instalação não tiver relatórios.
        PermissaoNegadaError: se a sessão não puder exportar relatórios.
        ValueError: se o formato for desconhecido.
    """
    # Duas perguntas diferentes, por esta ordem: a instalação tem isto? E
    # depois, esta pessoa pode? Esconder o botão não chega — um plugin ou um
    # agendamento chegam aqui por outro caminho.
    funcionalidades.exigir("relatorios")
    exigir(Permissao.RELATORIOS_EXPORTAR)

    destino = Path(destino)
    escolhido = formato or destino.suffix
    modulo = exportadores.obter(escolhido)

    relatorio.validar()
    caminho = modulo.exportar(relatorio, destino)
    logger.info(
        "Relatório exportado: %s (%s, %d bytes)",
        caminho,
        modulo.DESCRICAO,
        caminho.stat().st_size,
    )
    return caminho
