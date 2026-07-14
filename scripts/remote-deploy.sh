#!/usr/bin/env bash
# Deploy a partir do MAC: valida, faz push e dispara o build/deploy NO SERVIDOR.
#
#   ./scripts/remote-deploy.sh                 # push + deploy + smoke-test
#   ./scripts/remote-deploy.sh --skip-tests    # hotfix (pula pytest no servidor)
#
# Host do servidor: configure um alias no ~/.ssh/config do Mac (recomendado)
#
#   Host mordor
#       HostName 172.30.0.49       # ou o IP/host que o seu Mac alcança
#       User ubuntu
#       IdentityFile ~/.ssh/id_ed25519
#
# ...ou exporte MORDOR_HOST=usuario@ip
set -euo pipefail

HOST="${MORDOR_HOST:-mordor}"
REPO_DIR="${MORDOR_REPO:-/home/ubuntu/habitacao}"

[ -z "$(git status --porcelain)" ] || {
  echo "✗ working tree sujo — commite antes de deployar."; git status -s; exit 1; }

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || { echo "✗ você está em '$BRANCH'; deploy só de main."; exit 1; }

echo "==> git push origin main"
git push origin main

echo "==> deploy remoto em $HOST"
# -t: mostra a saída do deploy.sh ao vivo no terminal do Mac
ssh -t "$HOST" "cd '$REPO_DIR' && ./scripts/deploy.sh $*"
