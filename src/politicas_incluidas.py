"""As políticas de acesso que vêm com a aplicação.

Uma política responde à pergunta que o papel não responde: não *"podes
concluir tarefas?"*, mas *"podes concluir **esta**?"*. O mecanismo está em
:mod:`core.permissoes`; o que vive aqui são as regras concretas sobre
tarefas, que o núcleo não conhece nem deve conhecer.

Todas as que estão aqui **recusam**; nenhuma concede. É a propriedade que
torna seguro deixar um plugin registar as suas.
"""

from __future__ import annotations

from typing import Optional

from core import permissoes
from core.log import obter_logger
from core.permissoes import Pedido, Sessao

logger = obter_logger(__name__)

#: A funcionalidade que liga a segregação de funções. Nasce **desligada**.
#:
#: Tem de nascer desligada porque numa boa parte das instalações a pessoa que
#: cria a tarefa é a mesma que a faz, e ligá-la por omissão tirava a toda a
#: gente a capacidade de fechar o próprio trabalho — uma funcionalidade nova
#: não pode mudar o que já funcionava.
SEGREGACAO = "segregacao_de_funcoes"

#: O tipo de objeto a que estas políticas se aplicam.
TAREFA = "tarefa"


def quem_cria_nao_conclui(sessao: Sessao, pedido: Pedido) -> Optional[str]:
    """Recusa a conclusão de uma tarefa a quem a criou.

    É o controlo clássico de **segregação de funções**: quem levanta o
    trabalho não é quem certifica que ficou feito. Serve auditoria interna,
    conformidade e qualquer processo em que "concluída" seja uma afirmação
    sobre a realidade e não um risco pessoal.

    Duas decisões que valem a pena dizer em voz alta:

    * **Não há exceção para o administrador.** Um controlo de segregação que
      o dono da instalação contorna não é um controlo. O caminho para fechar
      uma tarefa própria é outra pessoa fechá-la, ou desligar a
      funcionalidade — e desligá-la fica registado, que é precisamente o que
      um auditor quer poder ver.
    * **As tarefas sem dono não são abrangidas.** São as anteriores às
      contas; ninguém as criou, por isso ninguém está a certificar o seu
      próprio trabalho ao fechá-las.
    """
    dono = pedido.atributo("dono") or ""
    if dono and dono == sessao.utilizador:
        return "politica_quem_cria_nao_conclui"
    return None


def registar_incluidas() -> None:
    """Põe as políticas da aplicação a valer.

    Idempotente: o registo é por nome. Chamada no momento em que
    :mod:`tarefas_servico` é importado — ver lá a razão de não ficar à espera
    de a interface arrancar.
    """
    permissoes.registar_politica(
        "tarefas.quem_cria_nao_conclui",
        acoes={"concluir"},
        tipos={TAREFA},
        avaliar=quem_cria_nao_conclui,
        funcionalidade=SEGREGACAO,
    )
