#!/usr/bin/env bash
# Estado dos mapas do código (MAPA.md), com o git como detetor de mudanças.
#
#   mapa.sh estado    que mapas estão desatualizados e porquê
#   mapa.sh marcar    regista o HEAD atual como o commit em que os mapas batem
#
# O MAPA.md da raiz guarda a linha `<!-- mapa: <sha> -->`. Cada pasta com um
# MAPA.md é dona dos ficheiros abaixo dela até à próxima pasta com MAPA.md.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
RAIZ_MAPA="MAPA.md"

sha_registado() {
  [ -f "$RAIZ_MAPA" ] && sed -n 's/^<!-- mapa: \([0-9a-f]\{7,40\}\) -->$/\1/p' "$RAIZ_MAPA" | head -1
}

# Pastas com mapa, da mais funda para a mais rasa (a mais funda ganha).
pastas_com_mapa() {
  git ls-files --cached --others --exclude-standard -- '*MAPA.md' 'MAPA.md' \
    | xargs -r -n1 dirname | sort -u | awk '{ print length($0) "\t" $0 }' | sort -rn | cut -f2
}

dono() { # ficheiro → pasta do mapa responsável
  local f="$1" p
  while IFS= read -r p; do
    if [ "$p" = "." ] || [[ "$f" == "$p/"* ]]; then echo "$p"; return; fi
  done < <(pastas_com_mapa)
  echo "(sem mapa)"
}

case "${1:-estado}" in
  estado)
    sha="$(sha_registado || true)"
    if [ ! -f "$RAIZ_MAPA" ]; then
      echo "Não há $RAIZ_MAPA: o repositório ainda não foi mapeado."; exit 3
    fi
    if [ -z "$sha" ]; then
      echo "$RAIZ_MAPA não tem a linha <!-- mapa: <sha> -->: corra 'mapa.sh marcar' depois de o rever."; exit 3
    fi
    if ! git cat-file -e "$sha^{commit}" 2>/dev/null; then
      echo "O commit $sha do mapa não existe neste clone (clone raso?): git fetch --unshallow, ou reveja tudo."; exit 3
    fi
    # Contra a árvore de trabalho: o que ainda não foi commitado também conta.
    mudados="$(git diff --name-only "$sha" -- . ':!*MAPA.md'; git ls-files --others --exclude-standard -- . ':!*MAPA.md')"
    if [ -z "$mudados" ]; then
      echo "Mapas em dia com $(git rev-parse --short HEAD) (registado: ${sha:0:7})."; exit 0
    fi
    echo "Mudou desde ${sha:0:7}:"
    while IFS= read -r f; do [ -n "$f" ] && printf '%s\t%s\n' "$(dono "$f")" "$f"; done <<< "$mudados" \
      | sort | awk -F'\t' '
          $1 != atual { if (atual != "") printf "\n"; atual = $1; printf "## %s\n", $1 }
          { printf "  %s\n", $2 }'
    echo
    echo "Atualize os MAPA.md acima (e o da raiz, se a responsabilidade de uma pasta mudou); depois 'mapa.sh marcar'."
    exit 1
    ;;
  marcar)
    [ -f "$RAIZ_MAPA" ] || { echo "Não há $RAIZ_MAPA para marcar." >&2; exit 2; }
    # O SHA registado tem de descrever código commitado: com alterações por
    # commitar, os mapas estariam a descrever algo que nenhum commit tem.
    if [ -n "$(git status --porcelain -- . ':!*MAPA.md')" ]; then
      echo "Há alterações por commitar fora dos MAPA.md: commite-as primeiro." >&2; exit 2
    fi
    novo="$(git rev-parse HEAD)"
    if grep -q '^<!-- mapa: ' "$RAIZ_MAPA"; then
      sed -i "s/^<!-- mapa: .* -->$/<!-- mapa: $novo -->/" "$RAIZ_MAPA"
    else
      printf '\n<!-- mapa: %s -->\n' "$novo" >> "$RAIZ_MAPA"
    fi
    echo "Mapas marcados em ${novo:0:7}."
    ;;
  *)
    echo "Uso: mapa.sh [estado|marcar]" >&2; exit 2 ;;
esac
