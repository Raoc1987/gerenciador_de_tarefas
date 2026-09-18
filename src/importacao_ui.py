"""Tela *Configurações → Importar*.

Quatro passos, na ordem em que uma pessoa pensa: que ficheiro, para onde, que
coluna é o quê, e — antes de qualquer coisa ser escrita — **o que vai
acontecer**.

O passo da pré-visualização não é uma cortesia. Uma importação é das poucas
ações que escreve centenas de linhas de uma vez; sem ver primeiro, o único
remédio para um mapeamento errado é apagar tudo à mão.
"""

from __future__ import annotations

from aparencia import cores, fonte
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Dict, List, Optional

from core.log import obter_logger
from importacao import leitura, motor
from importacao.leitura import ImportacaoError, Tabela
from importacao.motor import Destino, Previsao
from language_manager import carregar_texto

logger = obter_logger(__name__)

COR_NEUTRA = cores()["texto_suave"]
COR_ERRO = cores()["mau"]
COR_BOA = cores()["bom"]

TIPOS = [("CSV / Excel", "*.csv *.xlsx *.txt *.tsv"), ("Todos", "*.*")]

#: Linhas mostradas na pré-visualização. Ver dez chega para perceber se o
#: mapeamento está certo; ver trezentas não acrescenta nada e esconde o resumo.
PRE_VISUALIZAR = 10


class JanelaImportacao(tk.Toplevel):
    """Assistente de importação."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("importar"))
        self.geometry("760x600")
        self.transient(master)

        self.tabela: Optional[Tabela] = None
        self.previsao: Optional[Previsao] = None
        self._seletores: Dict[str, ttk.Combobox] = {}

        corpo = ttk.Frame(self, padding=14)
        corpo.pack(fill=tk.BOTH, expand=True)

        # --- 1. ficheiro
        ttk.Label(corpo, text=carregar_texto("importar_passo_ficheiro"),
                  font=fonte("destaque", negrito=True)).pack(anchor=tk.W)
        linha = ttk.Frame(corpo)
        linha.pack(fill=tk.X, pady=(2, 0))
        self.botao_escolher = ttk.Button(
            linha, text=carregar_texto("escolher_ficheiro"), command=self.escolher
        )
        self.botao_escolher.pack(side=tk.LEFT)
        self.rotulo_ficheiro = ttk.Label(linha, foreground=COR_NEUTRA)
        self.rotulo_ficheiro.pack(side=tk.LEFT, padx=(10, 0))

        # --- 2. destino
        ttk.Label(corpo, text=carregar_texto("importar_passo_destino"),
                  font=fonte("destaque", negrito=True)).pack(anchor=tk.W, pady=(12, 2))
        self.destino_var = tk.StringVar()
        self.seletor_destino = ttk.Combobox(
            corpo, textvariable=self.destino_var, state="readonly", width=38
        )
        self.seletor_destino.pack(anchor=tk.W)
        self.seletor_destino.bind("<<ComboboxSelected>>", lambda _: self.mapear())

        # --- 3. colunas
        ttk.Label(corpo, text=carregar_texto("importar_passo_colunas"),
                  font=fonte("destaque", negrito=True)).pack(anchor=tk.W, pady=(12, 2))
        self.mapa_frame = ttk.Frame(corpo)
        self.mapa_frame.pack(fill=tk.X)

        # --- 4. previsão
        ttk.Label(corpo, text=carregar_texto("importar_passo_previsao"),
                  font=fonte("destaque", negrito=True)).pack(anchor=tk.W, pady=(12, 2))
        self.tabela_previsao = ttk.Treeview(corpo, show="headings", height=8)
        self.tabela_previsao.pack(fill=tk.BOTH, expand=True)

        self.mensagem = ttk.Label(corpo, wraplength=710, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, pady=(8, 0))

        acoes = ttk.Frame(corpo)
        acoes.pack(fill=tk.X, pady=(10, 0))
        self.botao_prever = ttk.Button(
            acoes, text=carregar_texto("importar_prever"), command=self.prever
        )
        self.botao_prever.pack(side=tk.LEFT, padx=(0, 6))
        self.botao_importar = ttk.Button(
            acoes, text=carregar_texto("importar_aplicar"), command=self.importar
        )
        self.botao_importar.pack(side=tk.LEFT)
        self.botao_importar.state(["disabled"])
        ttk.Button(acoes, text=carregar_texto("fechar"), command=self.destroy).pack(
            side=tk.RIGHT
        )

        self._carregar_destinos()

    # ---------------------------------------------------------------- apoio

    def _dizer(self, texto: str, cor: str = COR_BOA) -> None:
        self.mensagem.configure(text=texto, foreground=cor)

    def _carregar_destinos(self) -> None:
        self._destinos = {
            carregar_texto(d.chave_titulo, d.nome): d for d in motor.disponiveis()
        }
        self.seletor_destino.configure(values=sorted(self._destinos))
        if self._destinos:
            self.seletor_destino.current(0)
        else:
            # Sem destinos, o assistente não tem para onde importar. Dizê-lo é
            # melhor do que deixar carregar em botões que não fazem nada.
            self._dizer(carregar_texto("importar_sem_destinos"), COR_ERRO)
            self.botao_escolher.state(["disabled"])
            self.botao_prever.state(["disabled"])

    def destino(self) -> Optional[Destino]:
        """O destino escolhido."""
        return self._destinos.get(self.destino_var.get())

    def mapa(self) -> Dict[str, str]:
        """O mapeamento que está no ecrã, sem os campos deixados em branco."""
        return {
            campo: seletor.get()
            for campo, seletor in self._seletores.items()
            if seletor.get()
        }

    # ---------------------------------------------------------------- passos

    def escolher(self, caminho: Optional[str] = None) -> bool:
        """Lê o ficheiro e propõe um mapeamento."""
        caminho = caminho or filedialog.askopenfilename(
            parent=self, title=carregar_texto("importar"), filetypes=TIPOS
        )
        if not caminho:
            return False

        try:
            self.tabela = leitura.ler(caminho)
        except ImportacaoError as erro:
            self.tabela = None
            self.rotulo_ficheiro.configure(text="")
            self._dizer(f"{carregar_texto(erro.chave_mensagem)} {erro}", COR_ERRO)
            self.botao_importar.state(["disabled"])
            return False

        self.rotulo_ficheiro.configure(
            text=carregar_texto(
                "importar_ficheiro_lido",
                nome=Path(caminho).name,
                linhas=len(self.tabela),
                colunas=len(self.tabela.cabecalho),
            )
        )
        self._dizer("")
        self.mapear()
        return True

    def mapear(self) -> None:
        """Desenha um seletor por campo, já com a sugestão."""
        for filho in self.mapa_frame.winfo_children():
            filho.destroy()
        self._seletores = {}
        self.botao_importar.state(["disabled"])

        destino = self.destino()
        if destino is None or self.tabela is None:
            return

        sugerido = motor.sugerir_mapa(self.tabela, destino)
        colunas = [""] + [c for c in self.tabela.cabecalho if c]

        for indice, campo in enumerate(destino.campos):
            rotulo = carregar_texto(campo.chave_titulo, campo.nome)
            if campo.obrigatorio:
                rotulo += " *"
            ttk.Label(self.mapa_frame, text=rotulo).grid(row=indice, column=0, sticky=tk.W)

            seletor = ttk.Combobox(
                self.mapa_frame, state="readonly", width=28, values=colunas
            )
            seletor.set(sugerido.get(campo.nome, ""))
            seletor.grid(row=indice, column=1, padx=(10, 0), pady=2, sticky=tk.W)
            self._seletores[campo.nome] = seletor

            if campo.exemplo:
                ttk.Label(
                    self.mapa_frame, text=f"ex.: {campo.exemplo}", foreground=COR_NEUTRA
                ).grid(row=indice, column=2, padx=(10, 0), sticky=tk.W)

    def prever(self) -> Optional[Previsao]:
        """Mostra o que vai acontecer, sem escrever nada."""
        destino, tabela = self.destino(), self.tabela
        if destino is None or tabela is None:
            self._dizer(carregar_texto("importar_escolha_ficheiro"), COR_NEUTRA)
            return None

        self.previsao = motor.prever(tabela, destino, self.mapa())
        self._desenhar_previsao(destino, self.previsao)

        if self.previsao.aceites:
            self.botao_importar.state(["!disabled"])
            cor = COR_BOA if self.previsao.tudo_bem else COR_ERRO
            self._dizer(
                carregar_texto(
                    "importar_resumo",
                    aceites=len(self.previsao.aceites),
                    problemas=len(self.previsao.problemas),
                ),
                cor,
            )
        else:
            self.botao_importar.state(["disabled"])
            self._dizer(carregar_texto("importar_nada_entra"), COR_ERRO)
        return self.previsao

    def _desenhar_previsao(self, destino: Destino, previsao: Previsao) -> None:
        colunas = ["linha"] + [c.nome for c in destino.campos] + ["problema"]
        self.tabela_previsao.configure(columns=colunas)
        for coluna in colunas:
            titulo = {
                "linha": carregar_texto("importar_coluna_linha"),
                "problema": carregar_texto("importar_coluna_problema"),
            }.get(coluna) or carregar_texto(f"campo_{coluna}", coluna)
            self.tabela_previsao.heading(coluna, text=titulo, anchor=tk.W)
            self.tabela_previsao.column(coluna, width=110 if coluna != "problema" else 230)

        for linha in self.tabela_previsao.get_children():
            self.tabela_previsao.delete(linha)
        self.tabela_previsao.tag_configure("problema", foreground=COR_ERRO)

        # Os problemas primeiro: é o que precisa de decisão.
        for problema in previsao.problemas[:PRE_VISUALIZAR]:
            valores = [problema.linha] + [""] * len(destino.campos) + [problema.motivo]
            self.tabela_previsao.insert("", tk.END, values=valores, tags=("problema",))
        for aceite in previsao.aceites[:PRE_VISUALIZAR]:
            valores = (
                [aceite.linha]
                + [aceite.dados.get(c.nome, "") for c in destino.campos]
                + [""]
            )
            self.tabela_previsao.insert("", tk.END, values=valores)

    def importar(self) -> Optional[motor.Resultado]:
        """Aplica o que a pré-visualização mostrou."""
        destino, tabela = self.destino(), self.tabela
        if destino is None or tabela is None:
            return None

        try:
            resultado = motor.importar(tabela, destino, self.mapa())
        except Exception as erro:
            logger.exception("Falha na importação.")
            self._dizer(f"{carregar_texto('importacao_erro')} {erro}", COR_ERRO)
            return None

        self._dizer(
            carregar_texto(
                "importar_concluida",
                criados=resultado.criados,
                problemas=len(resultado.problemas),
            ),
            COR_ERRO if resultado.houve_falhas else COR_BOA,
        )
        # Importar duas vezes por engano é fácil quando o botão continua ativo.
        self.botao_importar.state(["disabled"])
        return resultado
