#!/usr/bin/env bash
# Explorador da aplicação VIVA (Portal AM Imóveis).
# Para uma sessão do Claude Code (ou dev) inspecionar o FUNCIONAMENTO REAL —
# API autenticada + banco read-only — sem ter que redescobrir credenciais.
#
#   scripts/explore.sh token                         # imprime um Bearer token (admin, 24h)
#   scripts/explore.sh get /clientes                 # GET autenticado (path sob /api/v1)
#   scripts/explore.sh get "/crm/opportunities/kanban?pipeline_id=3"
#   scripts/explore.sh routes                        # lista TODOS os endpoints (do /openapi.json)
#   scripts/explore.sh db "SELECT * FROM crm_pipelines;"   # query READ-ONLY no Postgres de prod
#
# Credenciais: NUNCA hardcoded aqui. Vêm de env ou do .env local (gitignored).
#   PORTAL_ADMIN_EMAIL / PORTAL_ADMIN_SENHA  (senão lê ADMIN_PASSWORD do .env)
# Overrides por env: PORTAL_BASE, PORTAL_ADMIN_EMAIL, PORTAL_ADMIN_SENHA
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${PORTAL_BASE:-https://portal.amimoveis.tec.br}"
EMAIL="${PORTAL_ADMIN_EMAIL:-admin@roper.com}"
SENHA="${PORTAL_ADMIN_SENHA:-}"
if [ -z "$SENHA" ] && [ -f "$ROOT/.env" ]; then
  SENHA="$(grep -E '^ADMIN_PASSWORD=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
fi
[ -n "$SENHA" ] || { echo "Defina PORTAL_ADMIN_SENHA (ou ADMIN_PASSWORD no .env)." >&2; exit 1; }

_token() {
  curl -sk -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"senha\":\"$SENHA\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])"
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  token)
    _token ;;
  get)
    curl -sk "$BASE/api/v1${1:?uso: get <path>, ex: /clientes}" \
      -H "Authorization: Bearer $(_token)" ;;
  routes)
    curl -sk "$BASE/openapi.json" | python3 -c \
"import sys,json
for p,ms in sorted(json.load(sys.stdin)['paths'].items()):
    for m in ms: print(m.upper().ljust(6), p)" ;;
  db)
    DB=$(docker ps -qf name=habitacao_db)
    [ -n "$DB" ] || { echo 'container habitacao_db nao encontrado (rode no host mordor).' >&2; exit 1; }
    # SET read-only na MESMA sessao psql => exploracao nao consegue gravar/apagar.
    printf '%s\n%s\n' 'SET default_transaction_read_only = on;' "${1:?uso: db \"<SQL>\"}" \
      | docker exec -i "$DB" psql -U habitacao -d habitacao ;;
  *)
    sed -n '2,15p' "$0" ;;
esac
