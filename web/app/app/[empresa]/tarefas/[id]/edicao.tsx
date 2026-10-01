"use client";

import { useState, useTransition } from "react";
import { ROTULO_ESTADO, ROTULO_PRIORIDADE, type Tarefa } from "@/lib/dominio/tarefas";
import { apagarTarefa } from "../acoes";
import { FormularioTarefa, type Pessoa } from "../formulario-tarefa";
import { Aviso, Botao, Selo } from "@/components/ui";

export function EdicaoTarefa({
  empresaId, tarefa, pessoas, eu, podeEditar, podeAtribuir, podeApagar,
}: {
  empresaId: string;
  tarefa: Tarefa;
  pessoas: Pessoa[];
  eu: string;
  podeEditar: boolean;
  podeAtribuir: boolean;
  podeApagar: boolean;
}) {
  const [editar, setEditar] = useState(false);
  const [erro, setErro] = useState<string>();
  const [aApagar, iniciar] = useTransition();

  if (editar) {
    return (
      <FormularioTarefa
        empresaId={empresaId}
        tarefa={tarefa}
        pessoas={pessoas}
        eu={eu}
        podeAtribuir={podeAtribuir}
        aoConcluir={() => setEditar(false)}
        aoCancelar={() => setEditar(false)}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{tarefa.titulo}</h1>
        <div className="flex gap-2">
          {podeEditar && <Botao variante="secundario" onClick={() => setEditar(true)}>Editar</Botao>}
          {podeApagar && (
            <Botao
              variante="perigo"
              disabled={aApagar}
              onClick={() => {
                if (!confirm("Apagar esta tarefa? Fica registado na auditoria, mas não se recupera.")) return;
                iniciar(async () => {
                  const r = await apagarTarefa(empresaId, tarefa.id);
                  if (r?.erro) setErro(r.erro);
                });
              }}
            >
              Apagar
            </Botao>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Selo tom={tarefa.estado === "concluida" ? "sucesso" : "marca"}>{ROTULO_ESTADO[tarefa.estado]}</Selo>
        <Selo tom={tarefa.prioridade === "urgente" ? "perigo" : tarefa.prioridade === "alta" ? "aviso" : "neutro"}>
          Prioridade {ROTULO_PRIORIDADE[tarefa.prioridade].toLowerCase()}
        </Selo>
        {tarefa.etiquetas.map((e) => <Selo key={e}>{e}</Selo>)}
      </div>
      {tarefa.descricao ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{tarefa.descricao}</p>
      ) : (
        <p className="text-sm text-texto-2">Sem descrição.</p>
      )}
      <Aviso>{erro}</Aviso>
    </div>
  );
}
