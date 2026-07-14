#!/usr/bin/env bash
# Deploy do Portal AM Imóveis — roda NO SERVIDOR (mordor), em /home/ubuntu/habitacao.
#
#   ./scripts/deploy.sh                -> puxa origin/main, builda, deploya, valida
#   ./scripts/deploy.sh --skip-tests   -> pula o pytest (hotfix urgente)
#   ./scripts/deploy.sh --rollback     -> volta pra imagem anterior (sem rebuild)
#
# Por que buildar aqui e não no Mac: o servidor é amd64 e o Mac (Apple Silicon) é
# arm64 — imagem buildada no Mac dá "exec format error" em produção. Aqui é nativo.
set -Eeuo pipefail

REPO_DIR="/home/ubuntu/habitacao"
STACK="habitacao"
SERVICE="habitacao_portal"
IMAGE="habitacao-portal"
PREV_TAG_FILE="$REPO_DIR/.deploy_prev_tag"
BASE="https://portal.amimoveis.tec.br"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }
trap 'die "falhou na linha $LINENO"' ERR

cd "$REPO_DIR"

SKIP_TESTS=0; ROLLBACK=0
for a in "$@"; do
  case "$a" in
    --skip-tests) SKIP_TESTS=1 ;;
    --rollback)   ROLLBACK=1 ;;
    *) die "flag desconhecida: $a" ;;
  esac
done

# --------------------------------------------------------------- smoke-test
# /healthz sozinho NÃO prova nada: o lifespan engole exceção do init_v2.sql e a app
# sobe mesmo com o banco quebrado. Por isso: readyz (DB) + login + GET autenticado.
smoke() {
  log "Validando o rollout"
  local i ok=0
  for i in $(seq 1 30); do
    if curl -fsk --max-time 5 "$BASE/healthz" >/dev/null 2>&1 \
    && curl -fsk --max-time 5 "$BASE/readyz"  >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
  done
  [ "$ok" = 1 ] || { echo "  /healthz ou /readyz FALHOU"; return 1; }
  echo "  /healthz OK · /readyz OK (banco alcançável)"

  local tok
  tok=$(curl -fsk --max-time 10 -X POST "$BASE/api/v1/auth/login" \
        -H 'Content-Type: application/json' \
        -d "{\"email\":\"admin@roper.com\",\"senha\":\"${ADMIN_PASSWORD}\"}" \
        | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
  [ -n "$tok" ] || { echo "  login FALHOU"; return 1; }
  curl -fsk --max-time 10 -H "Authorization: Bearer $tok" \
       "$BASE/api/v1/lookup/contadores" >/dev/null || { echo "  GET autenticado FALHOU"; return 1; }
  echo "  login + GET autenticado OK"
}

# --------------------------------------------------------------- rollback
if [ "$ROLLBACK" = 1 ]; then
  [ -f "$PREV_TAG_FILE" ] || die "sem $PREV_TAG_FILE — nada para reverter."
  PREV="$(cat "$PREV_TAG_FILE")"
  docker image inspect "$IMAGE:$PREV" >/dev/null 2>&1 \
    || die "imagem $IMAGE:$PREV não existe mais (podada). Reverta com: git checkout <sha> && ./scripts/deploy.sh"
  set -a; . ./.env; set +a
  log "ROLLBACK -> $IMAGE:$PREV"
  docker tag "$IMAGE:$PREV" "$IMAGE:latest"
  docker service update --force "$SERVICE" >/dev/null
  smoke && { echo; echo "ROLLBACK OK -> $PREV"; exit 0; }
  die "rollback subiu mas não passou no smoke-test. Ver: docker service logs $SERVICE --tail 100"
fi

# --------------------------------------------------------------- 1. git
log "1/6 Repositório"
# docker build empacota o WORKING TREE, não o commit. Sujo aqui = deploy de algo
# que não está no git. Nunca edite código direto no servidor.
[ -z "$(git status --porcelain)" ] \
  || die "working tree SUJO no servidor — o build empacotaria código fora do git.
       Rode: git status / git checkout -- . (edite no Mac, não aqui)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || die "HEAD está em '$BRANCH'; deploy só a partir de main."
git pull --ff-only origin main
SHA="$(git rev-parse --short HEAD)"
echo "  HEAD = $SHA — $(git log -1 --pretty=%s)"

# --------------------------------------------------------------- 2. .env
log "2/6 Carregando .env"
[ -f .env ] || die ".env não existe. cp .env.example .env && chmod 600 .env"
set -a; . ./.env; set +a          # exporta: o compose usa ${POSTGRES_PASSWORD:?}
: "${POSTGRES_PASSWORD:?ausente no .env}"
: "${JWT_SECRET:?ausente no .env}"
: "${ADMIN_PASSWORD:?ausente no .env}"
case "${DATABASE_URL:-}" in
  *'${'*) die 'DATABASE_URL contém ${...} literal — env_file NÃO interpola. Escreva o valor expandido.' ;;
esac

# --------------------------------------------------------------- 3. testes
if [ "$SKIP_TESTS" = 0 ] && [ -x venv/bin/pytest ]; then
  log "3/6 pytest (gate)"
  venv/bin/pytest -q | tail -1
else
  log "3/6 pytest PULADO"
fi

# --------------------------------------------------------------- 4. build
log "4/6 docker build ($IMAGE:$SHA)"
# guarda a versão que está em produção AGORA, para o --rollback
CUR="$(docker image inspect "$IMAGE:latest" --format '{{index .Config.Labels "git_sha"}}' 2>/dev/null || true)"
if [ -n "$CUR" ] && [ "$CUR" != "<no value>" ] && [ "$CUR" != "$SHA" ]; then
  echo "$CUR" > "$PREV_TAG_FILE"
  echo "  em produção hoje: $CUR (guardado p/ --rollback)"
fi
docker build -f Dockerfile.portal --label "git_sha=$SHA" -t "$IMAGE:$SHA" -t "$IMAGE:latest" . >/dev/null
echo "  imagem $IMAGE:$SHA pronta"

# --------------------------------------------------------------- 5. deploy
log "5/6 stack deploy + service update --force"
docker stack deploy -c docker-compose.yml "$STACK" 2>&1 | grep -vi "could not be accessed" || true
# OBRIGATÓRIO: o compose aponta pra tag :latest sem digest; sem --force o Swarm
# não percebe que a imagem mudou e mantém o container antigo rodando.
docker service update --force "$SERVICE" >/dev/null

# --------------------------------------------------------------- 6. validação
log "6/6 Smoke-test"
if ! smoke; then
  echo; echo "SMOKE-TEST FALHOU — últimos logs:"
  docker service logs "$SERVICE" --tail 30 2>/dev/null || true
  if [ -f "$PREV_TAG_FILE" ] && docker image inspect "$IMAGE:$(cat "$PREV_TAG_FILE")" >/dev/null 2>&1; then
    echo; echo ">>> revertendo automaticamente para $(cat "$PREV_TAG_FILE")"
    docker tag "$IMAGE:$(cat "$PREV_TAG_FILE")" "$IMAGE:latest"
    docker service update --force "$SERVICE" >/dev/null
    smoke && echo "ROLLBACK automático OK." || echo "ROLLBACK FALHOU — intervenção manual!"
  fi
  die "deploy de $SHA rejeitado."
fi

# --------------------------------------------------------------- housekeeping
# Disco em ~76%. Cada imagem tem ~1.2GB (Chromium). Mantém as 5 últimas tags.
docker image prune -f >/dev/null 2>&1 || true
docker images "$IMAGE" --format '{{.Tag}}\t{{.CreatedAt}}' \
  | grep -v '^latest' | sort -k2 -r | tail -n +6 | cut -f1 \
  | xargs -r -I{} docker rmi "$IMAGE:{}" >/dev/null 2>&1 || true

echo
echo "════════════════════════════════════════════════"
echo "  DEPLOY OK · $SHA · $(git log -1 --pretty=%s)"
echo "  $BASE"
echo "  reverter: ./scripts/deploy.sh --rollback"
echo "════════════════════════════════════════════════"
