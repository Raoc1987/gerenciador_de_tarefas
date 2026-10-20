// A chave que deixa libertar a reserva de uma pergunta ao Copiloto quando o
// modelo não responde (supabase/migrations/20261020000000_copiloto_libertar.sql).
// A chave fica no servidor; à base vai só o hash, e quem pergunta nunca a vê.

import { createHash, randomUUID } from "node:crypto";

export function hashDaChave(chave: string): string {
  return createHash("sha256").update(chave, "utf8").digest("hex");
}

export function novaChaveDeReserva(): { chave: string; hash: string } {
  const chave = randomUUID();
  return { chave, hash: hashDaChave(chave) };
}
