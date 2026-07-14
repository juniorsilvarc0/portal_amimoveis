# Portal AM Imóveis

Sistema web unificado da **AM Imóveis** (Andreia Miranda Imóveis): habitação PMCMV, propostas
comerciais, financiamento imobiliário, documentos em PDF (recibo, declaração de parentesco),
**CRM de vendas** e cadastros auxiliares — sob um único domínio.

🔗 **Produção:** https://portal.amimoveis.tec.br · **API:** `/docs` (Swagger) · `/redoc`

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 · FastAPI 0.115 · Pydantic v2 · psycopg2 |
| Banco | PostgreSQL 16 |
| Auth | JWT (HS256) + bcrypt · RBAC granular (perfis × recurso × ação) |
| PDF | Jinja2 + Playwright/Chromium (auto-scale, 1 página A4) |
| Frontend | HTML + CSS + **JS vanilla** (sem build) |
| Deploy | Docker Swarm + Traefik (SSL Let's Encrypt) |

## Módulos

- **Clientes** — cadastro central (1 pessoa → N processos), com notas/Chatter
- **Habitação** — fichas PMCMV + export PDF e XLSX
- **Propostas** — proposta comercial com pagamentos parcelados + PDF
- **Financiamento** — acompanhamento de análise
- **Documentos** — recibo e declaração de parentesco (CAIXA), em PDF
- **CRM** — leads, oportunidades, pipelines configuráveis com **Kanban drag-and-drop**,
  jornada Venda → Pós-Venda, atividades, campanhas, SLA/automação por etapa, webhooks, import CSV
- **Perfis** — RBAC customizável (21 recursos × ver/criar/editar/excluir)

## Rodando localmente

Requer **Python 3.12** (3.13+ quebra `psycopg2-binary` e `greenlet`) e um PostgreSQL 16.

```bash
git clone git@github.com:juniorsilvarc0/portal_amimoveis.git
cd portal_amimoveis

# Postgres local (ou use um nativo)
docker run -d --name pg16 -p 5432:5432 \
  -e POSTGRES_DB=habitacao -e POSTGRES_USER=habitacao -e POSTGRES_PASSWORD=devpass \
  postgres:16-alpine

python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # sem --with-deps

cp .env.example .env && chmod 600 .env   # ajuste DATABASE_URL p/ localhost
set -a; . ./.env; set +a                 # necessário: connection.py lê os.environ

uvicorn app.main:app --reload --port 8000
```

O schema é criado sozinho: o *lifespan* aplica o `init_v2.sql` (idempotente) e faz o seed do admin,
dos perfis RBAC e do pipeline CRM padrão. **Um banco vazio basta** — nenhum seed manual.

Valide com `curl localhost:8000/readyz` → `{"status":"ready"}`. Testes: `pytest`.

## Deploy

A imagem é **sempre buildada no servidor** (amd64) — nunca no Mac (arm64), sob pena de
`exec format error`. Um comando, a partir do seu clone:

```bash
./scripts/remote-deploy.sh      # push + build/deploy remoto + smoke-test + auto-rollback
```

## Configuração

Todos os segredos vêm de variáveis de ambiente — veja **`.env.example`**. O `.env` **nunca**
é versionado.

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | conexão com o Postgres |
| `JWT_SECRET` | assinatura dos tokens (obrigatório em produção) |
| `ADMIN_PASSWORD` | senha do admin criado no seed inicial |
| `POSTGRES_PASSWORD` | senha do serviço de banco (Swarm) |

## Estrutura

```
app/          API REST (/api/v1) — routers, schemas Pydantic, repos, services
init_v2.sql   schema canônico (fonte única de verdade, idempotente no startup)
static/       frontend vanilla (DataGrid, Modal, Sidebar) + páginas
templates/    Jinja2 — apenas os PDFs
scripts/      deploy.sh (servidor) · remote-deploy.sh (Mac) · explore.sh (API/DB viva)
tests/        pytest
```

## Licença

Software proprietário — AM Imóveis. Todos os direitos reservados.
