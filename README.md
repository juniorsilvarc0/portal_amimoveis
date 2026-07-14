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

## Rodando localmente (recomendado: tudo em Docker)

Não precisa de Python no host — a imagem já é `python:3.12-slim`. Isso evita a armadilha do
Python 3.13+, que quebra `psycopg2-binary` e `greenlet`.

```bash
git clone git@github.com:juniorsilvarc0/portal_amimoveis.git
cd portal_amimoveis

cp .env.example .env && chmod 600 .env   # preencha os segredos (é gitignored)

docker compose -f docker-compose.dev.yml up -d --build
```

Pronto: app em **http://localhost:8000** (Swagger em `/docs`), Postgres em **localhost:5432**.

O schema é criado sozinho: o *lifespan* aplica o `init_v2.sql` (idempotente) e faz o seed do admin,
dos perfis RBAC e do pipeline CRM padrão. **Um banco vazio basta** — nenhum seed manual.

| Tarefa | Comando |
|---|---|
| Logs da app | `docker compose -f docker-compose.dev.yml logs -f portal` |
| Testes | `docker compose -f docker-compose.dev.yml exec portal pytest -q` |
| Shell no banco | `docker compose -f docker-compose.dev.yml exec habitacao_db psql -U habitacao habitacao` |
| Parar | `docker compose -f docker-compose.dev.yml down` |
| Parar e **apagar o banco** | `docker compose -f docker-compose.dev.yml down -v` |

`app/`, `templates/` e `static/` entram por *bind mount*: editar no host reflete na hora
(o `uvicorn` roda com `--reload`). Só mexer em `requirements.txt` ou no `Dockerfile.portal`
exige `--build` de novo.

Valide com `curl localhost:8000/readyz` → `{"status":"ready"}`. Note que `/healthz` responde 200
mesmo com o banco fora do ar — **quem prova que a app está viva é `/readyz`**.

> **Testes `db` escrevem no banco.** `TEST_DATABASE_URL` aponta para o banco de dev, e
> `tests/test_repos.py` faz upsert de cliente. Se você restaurou uma cópia de produção aqui,
> rodar a suíte suja essa cópia — `down -v` + restore reseta.

### Trabalhando com uma cópia dos dados de produção

```bash
# dump direto do servidor para o Mac (não escreve nada no servidor)
mkdir -p backups
ssh mordor 'docker exec $(docker ps -qf name=habitacao_db) \
  pg_dump -U habitacao -Fc --no-owner --no-privileges habitacao' > backups/prod.dump

docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d habitacao_db
docker compose -f docker-compose.dev.yml exec -T habitacao_db \
  pg_restore -U habitacao -d habitacao --no-owner --no-privileges < backups/prod.dump
docker compose -f docker-compose.dev.yml up -d portal
```

Depois do restore, **dois cuidados**:

1. A tabela `usuarios` vem com os hashes de senha **reais** — o seed do admin não roda (já existe
   admin), então o `ADMIN_PASSWORD` do seu `.env` não vale. Redefina a senha só no banco local:
   ```bash
   H=$(docker compose -f docker-compose.dev.yml exec -T portal \
       python -c "from app.auth.jwt import hash_password; print(hash_password('devadmin123'))")
   docker compose -f docker-compose.dev.yml exec -T habitacao_db psql -U habitacao -d habitacao \
     -c "UPDATE usuarios SET senha_hash='$H' WHERE email='admin@roper.com';"
   ```
2. `crm_webhooks` vem com as **URLs reais**, e o dispatcher não tem kill-switch de ambiente:
   mexer numa oportunidade aqui dispara POST de verdade lá fora. Desative-os no local:
   ```bash
   docker compose -f docker-compose.dev.yml exec -T habitacao_db psql -U habitacao -d habitacao \
     -c "UPDATE crm_webhooks SET ativo=false;"
   ```

`backups/` é gitignored — a cópia contém PII real (CPF, endereços). Não versione, não compartilhe.

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
