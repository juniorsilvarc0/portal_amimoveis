# CLAUDE.md — Portal AM Imóveis

## Projeto

Sistema web unificado da AM Imóveis (Andreia Miranda Imóveis) servindo habitação PMCMV, propostas comerciais, financiamento imobiliário, **CRM completo de vendas (Salesforce-style)** e cadastros auxiliares. API REST + frontend vanilla em JS, sob um único domínio canônico.

## URL Produção

https://portal.amimoveis.tec.br

Redirects 301 ativos (30 dias pós-cutover):
- `habitacao.amimoveis.tec.br/*` → `portal.amimoveis.tec.br/habitacao`
- `proposta.amimoveis.tec.br/*` → `portal.amimoveis.tec.br/proposta`

Admin padrão: `admin@roper.com` — senha definida via `ADMIN_PASSWORD` no `.env` (ver `.env.example`). Nunca commitar credenciais.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + **FastAPI 0.115** + Pydantic v2 + psycopg2 |
| Runtime | Uvicorn workers via Gunicorn (2 workers) + Tini como PID 1 |
| Auth | JWT (HS256, 24h) via python-jose + bcrypt (fallback scrypt p/ hashes legados werkzeug) |
| PDF | Jinja2 + Playwright/Chromium (auto-scale para 1 página A4) |
| Banco | PostgreSQL 16 (Alpine) |
| Frontend | HTML + CSS + **JS vanilla** (sem build), DM Sans, componentes reutilizáveis (DataGrid, Modal, Sidebar) |
| Docs API | Swagger UI em `/docs`, ReDoc em `/redoc`, OpenAPI em `/openapi.json` |
| Deploy | Docker Swarm + Traefik (SSL Let's Encrypt) |

## Comandos

```bash
# Dev local
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
pytest                                   # 15 passing, 14 DB-skipped sem TEST_DATABASE_URL
uvicorn app.main:app --reload --port 8000

# Build + deploy produção
docker build -f Dockerfile.portal -t habitacao-portal:latest .
docker stack deploy -c docker-compose.yml habitacao
docker service update --force habitacao_portal   # puxa a nova imagem

# Logs
docker service logs habitacao_portal --tail 50
docker service logs habitacao_db --tail 20

# Backup
docker exec $(docker ps -qf name=habitacao_db) pg_dump -U habitacao -Fc habitacao > ~/backups/habitacao_$(date +%Y%m%d_%H%M).dump

# Smoke-test produção
curl -sk https://portal.amimoveis.tec.br/healthz           # app rodando
curl -sk https://portal.amimoveis.tec.br/readyz            # DB reachable
curl -sk -X POST https://portal.amimoveis.tec.br/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"senha\":\"$ADMIN_PASSWORD\"}"
```

**IMPORTANTE:** `docker stack deploy` nem sempre recria o container com imagem `:latest` mesmo rebuilt. Sempre rode `docker service update --force habitacao_portal` após o deploy.

### Explorar a aplicação VIVA (API + banco)

Para inspecionar o funcionamento real (não só o código), use o helper `scripts/explore.sh` (roda no host mordor):

```bash
scripts/explore.sh token                       # Bearer token JWT (admin, 24h)
scripts/explore.sh get /clientes               # GET autenticado (path sob /api/v1)
scripts/explore.sh get "/crm/opportunities/kanban?pipeline_id=3"
scripts/explore.sh routes                      # lista TODOS os ~220 endpoints (openapi.json)
scripts/explore.sh db "SELECT * FROM crm_pipelines;"   # Postgres de prod, READ-ONLY (bloqueia escrita)
```

Acesso total = role **Administrador** (`is_system`). A senha do admin vem do `.env` (`ADMIN_PASSWORD`) — o `explore.sh` lê de lá; nunca hardcode. Swagger interativo em `/docs` (Authorize + Bearer).

## Estrutura

```
habitacao/
├── app/                            # código do portal (FastAPI)
│   ├── main.py                     # FastAPI app, lifespan, middlewares, router mount
│   ├── config.py                   # Pydantic Settings
│   ├── auth/
│   │   ├── jwt.py                  # bcrypt + scrypt fallback + python-jose
│   │   ├── dependencies.py         # get_current_user, require_role (legado)
│   │   ├── recursos.py             # catálogo RBAC: 21 recursos × 4 ações (FONTE ÚNICA)
│   │   ├── permissions.py          # require_permission(recurso,acao), require_admin, user_can
│   │   └── router.py               # /api/v1/auth/{login,me,refresh,logout}
│   ├── routers/                    # 1 arquivo por recurso
│   │   ├── clientes.py             # + lookup por CPF, /{id}/full, /{id}/notas, PATCH inline
│   │   ├── habitacao.py            # + /{id}/pdf, /{id}/xlsx (export Excel)
│   │   ├── propostas.py            # + /{id}/pdf, pagamentos nested
│   │   ├── parentescos.py          # declaração CAIXA + /{id}/pdf
│   │   ├── recibos.py              # recibo + /{id}/pdf (cliente opcional, logo dinâmica)
│   │   ├── financiamentos.py
│   │   ├── {cidades,agencias,gerentes,parceiros,imoveis,correspondentes,corretores}.py
│   │   ├── logos.py                # upload BYTEA + serve imagem (p/ PDFs)
│   │   ├── settings.py             # app_settings chave/valor (feature flags)
│   │   ├── rbac.py                 # /api/v1/perfis — perfis + matriz de permissões
│   │   ├── crm.py                  # módulo CRM completo (ver skill crm-module)
│   │   ├── usuarios.py             # admin-only
│   │   ├── lookup.py               # dropdowns leves + contadores (+ públicos)
│   │   └── pages.py                # serve HTML pages
│   ├── schemas/                    # Pydantic v2 (Create/Update/Read) — ConfigDict
│   ├── db/
│   │   ├── connection.py           # pool psycopg2 + run_init_sql()
│   │   └── *_repo.py               # um repositório por tabela
│   └── services/
│       ├── pdf_service.py          # gerar_pdf_{habitacao,proposta,parentesco,recibo}
│       ├── excel_service.py        # gerar_xlsx_habitacao (openpyxl)
│       ├── webhook_dispatcher.py   # disparo assíncrono de webhooks CRM (thread daemon)
│       └── crm_importer.py         # import CSV de leads
├── templates/                      # Jinja2 (somente PDFs)
│   ├── ficha_habitacional.html
│   ├── proposta_imoveis.html
│   ├── parentesco.html
│   └── recibo.html
├── static/
│   ├── css/layout.css
│   ├── js/
│   │   ├── api.js (+ api.can RBAC), datagrid.js, modal.js, sidebar.js, masks.js, cpf_lookup.js, forms.js
│   ├── login.html, portal_dashboard.html
│   ├── clientes.html, clientes_form.html, cliente_detail.html (Chatter/notas)
│   ├── habitacao*.html, proposta*.html, financiamento*.html, recibos_*.html, parentesco_*.html
│   ├── crm_*.html, perfis_*.html, logos_list.html, corretor_publico.html (página PÚBLICA)
│   └── logoAM.png, logoAndreiaMirandab.png
├── tests/                          # pytest (28 passed / 14 skipped sem DB; inclui test_rbac)
├── scripts/
│   └── migrate_to_v2.py            # migração fichas→schema v2 (histórica)
├── init_v2.sql                     # SCHEMA CANÔNICO — fonte única de verdade
├── requirements.txt
├── Dockerfile.portal               # multi-stage, usuário não-root, tini
├── docker-compose.yml              # portal + db + Traefik + redirects legados
├── .env                            # JWT_SECRET + ADMIN_PASSWORD (não commitar!)
└── pytest.ini
```

## Modelo de dados (32 tabelas)

`init_v2.sql` cria **32 tabelas**. Grupos: auth/RBAC (4: usuarios, rbac_roles, rbac_role_permissions, app_settings), cadastros auxiliares (7), núcleo de clientes (3: clientes, conjuges, cliente_notas), documentos+suporte (6: habitacao_fichas, propostas, proposta_pagamentos, recibos, parentescos, logos), financiamento (1), CRM (11, inclui crm_opp_documentos). 3 ENUMs: `tipo_parceiro`, `modalidade_imovel`, `status_analise`. Sem triggers — `updated_at` via DEFAULT; migrações idempotentes em blocos `DO $$`.

```
-- Auth & RBAC -------------------------------------------------------------
usuarios(email UNIQUE, senha_hash bcrypt, perfil admin|usuario LEGADO,
         role_id → rbac_roles, ativo)
rbac_roles(nome UNIQUE, descricao, is_system, ativo)   # is_system=Administrador protegido
rbac_role_permissions(role_id, recurso, ver, criar, editar, excluir; UNIQUE(role_id,recurso))
app_settings(key PK, value, updated_at)                # feature flags chave/valor

-- Cadastros auxiliares ----------------------------------------------------
cidades(nome, uf UNIQUE)
agencias(nome, bairro, numero, cidade_id → cidades)
gerentes(nome, agencia_id → agencias)
parceiros(nome, tipo ENUM CONSTRUTORA|IMOBILIARIA|AUTONOMO, cidade_id)
imoveis(nome, construtora_id → parceiros, cidade_id)
correspondentes(nome, cidade_id)
corretores(nome, cpf, creci, cidade_id, ...)           # self-cadastro público opcional

-- Clientes ----------------------------------------------------------------
clientes(cpf UNIQUE parcial, cpf_pendente BOOLEAN, nome, rg, nascimento,
         nacionalidade, estado_civil, regime_bens, profissao, email,
         telefones, endereco, cidade_id, proprietario_id/criado_por/modificado_por → usuarios)
conjuges(cliente_id UNIQUE → clientes ON DELETE CASCADE, nome, cpf, ...)   # 1:1 opcional
cliente_notas(cliente_id → clientes, corpo, criado_por_id → usuarios)      # Chatter

-- Documentos --------------------------------------------------------------
recibos(cliente_id NULLABLE, logo_id → logos, cidade_id, valor_recebido,
        formas_pagamento JSONB, ...)                    # cliente OPCIONAL
logos(nome, arquivo BYTEA, content_type)               # imagens p/ cabeçalho de PDF
parentescos(cliente_id → clientes, grau_parentesco, ...)  # declaração CAIXA Lei 14.620/2023

habitacao_fichas(cliente_id → clientes, empreendimento, imovel_id,
                 titular_* / conjuge_* snapshot de rendimentos,
                 relacionamento caixa, financiamento, imóvel, taxas,
                 construtora_id, construtora_nome fallback,
                 legacy_ficha_id — rastreabilidade da migração)

propostas(cliente_id → clientes, imovel_id, empreendimento, unidade, ...)
proposta_pagamentos(proposta_id → propostas ON DELETE CASCADE,
                    ordem, descricao, quantidade, valor_parcela,
                    valor_total, forma, vencimento)

financiamentos(cliente_id → clientes, imovel_id, gerente_id, parceiro_id,
               correspondente_id, modalidade ENUM, renda, valor_financiamento,
               analise ENUM PENDENTE|EM_ANALISE|APROVADO|REPROVADO|CANCELADO)

-- CRM (Salesforce-style) — 11 tabelas (inclui crm_opp_documentos) -----------
crm_pipelines(nome, descricao, is_default, ativo)
  └─ crm_stages(pipeline_id, nome, ordem, probabilidade, cor, tipo aberto|ganho|perdido)
crm_campaigns(nome, tipo, status, data_inicio, data_fim, orcamento)
crm_leads(nome, email, telefone, whatsapp, cpf_cnpj, cidade_id,
          origem, campaign_id, status novo|contatado|qualificado|convertido|descartado,
          score, interesse, imovel_interesse_id, valor_estimado,
          proprietario_id, cliente_id, data_conversao)
crm_opportunities(nome, cliente_id, lead_id, pipeline_id, stage_id, imovel_id,
                  valor, probabilidade, data_previsao, data_fechamento,
                  proprietario_id, campaign_id, status aberta|ganha|perdida,
                  motivo_perda, proposta_id)
crm_activities(tipo tarefa|ligacao|reuniao|email|whatsapp|nota,
               assunto, descricao, data_atividade, status, prioridade,
               lead_id, opportunity_id, cliente_id, proprietario_id)
crm_opp_notas(opportunity_id → crm_opportunities, titulo, corpo, criado_por_id)
crm_opp_documentos(opportunity_id → crm_opportunities, nome, status, arquivo BYTEA, ...)  # card 10/aba Documentos
crm_stage_history(opportunity_id, stage_id_from, stage_id_to, usuario_id, motivo)
crm_webhooks(nome, url, eventos csv, secret HMAC, ativo)
crm_webhook_logs(webhook_id, evento, payload, status_code, response_body, erro)
```

`init_v2.sql` é a **fonte única de verdade** do schema. Aplicado idempotentemente no startup da app via `run_init_sql()` (lifespan handler).

## API REST — convenções

Todos os endpoints versionados em `/api/v1/*`. Autenticação Bearer JWT exceto `/auth/login`.

**Padrão CRUD uniforme**:
```
GET    /api/v1/{recurso}                 ?page=&per_page=&sort=&search=&filtros...
POST   /api/v1/{recurso}                 body: Pydantic Create
GET    /api/v1/{recurso}/{id}
PUT    /api/v1/{recurso}/{id}            body: Pydantic Update
DELETE /api/v1/{recurso}/{id}
```

Listagem devolve `{data: [...], meta: {page, per_page, total, total_pages}}`.

Endpoints especiais:
- `GET /api/v1/clientes?cpf={cpf}` / `GET /api/v1/clientes/por-cpf/{cpf}` — lookup rápido por CPF
- `GET /api/v1/clientes/{id}/full` — visão Salesforce (cliente + notas + processos relacionados)
- `GET|POST /api/v1/clientes/{id}/notas` + `PATCH /api/v1/clientes/{id}` — Chatter e edição inline
- `GET /api/v1/habitacao/{id}/pdf` — PDF via Playwright · `GET /api/v1/habitacao/{id}/xlsx` — export Excel
- `GET /api/v1/{propostas,parentescos,recibos}/{id}/pdf` — PDFs (Playwright + Jinja)
- `POST /api/v1/logos` (multipart) + `GET /api/v1/logos/{id}/imagem` (público, serve BYTEA)
- `POST /api/v1/corretores` — **público** (gate por `app_settings.corretores_publico_ativo`)
- `GET /api/v1/settings/public/{key}` — leitura pública (whitelist) · `PUT /api/v1/settings/{key}` (admin)
- `GET /api/v1/perfis` + `/recursos` + CRUD — gestão de perfis RBAC e matriz de permissões
- `GET /api/v1/lookup/{recurso}` / `/contadores` / `/cidades-publico` — dropdowns + dashboard
- `GET /healthz` — app ready · `GET /readyz` — DB reachable
- CRM: ver seção CRM abaixo e `.claude/skills/crm-module/SKILL.md`

## CRM (Salesforce-style)

Módulo de vendas completo sob `/api/v1/crm/*` e UI sob `/crm/*`. Veja `.claude/skills/crm-module/SKILL.md` para detalhes. **A página de detalhe da oportunidade** (`/crm/opportunities/{id}` — 13 cards estilo Salesforce, edição inline, setinhas verdes, faixa de SLA; edição é inline, sem página `/editar`) tem skill próprio: `.claude/skills/crm-opportunity-page/SKILL.md`. **O fluxo Pipeline → Stages → Oportunidades → Kanban** (config de funis, board drag-drop, jornada Venda→Pós-Venda, lista/criação de opp, mudança de etapa; inclui o gotcha "opp some do kanban") tem skill próprio: `.claude/skills/crm-pipeline-kanban/SKILL.md`.

**Recursos:** Leads, Opportunities (com Pipeline Kanban drag-drop, **notas** `crm_opp_notas`, **histórico de stage** `crm_stage_history` embutido no `/{id}`, visão `/{id}/full`, `PATCH` inline), Activities (tarefas/ligações/reuniões + timeline), Campaigns, Pipelines configuráveis (etapas com edição + reordenação drag-drop), Webhooks de saída (HMAC-SHA256), Import CSV. **10 tabelas `crm_*`.**

**Modelo de relacionamento (2026-05-12):** Cliente é central (1 por CPF). Um Cliente pode ter N Leads (cada campanha = um lead novo). Opportunity sempre tem `cliente_id` (NOT NULL); `lead_id` é metadata opcional de origem. Ver `.claude/skills/crm-module/SKILL.md`.

**Integrações nativas:**
- Auto-vínculo Lead→Cliente por CPF: ao criar Lead, se CPF já existir em Clientes, vincula automaticamente e status vira `reativado`
- `GET /api/v1/crm/leads/lookup-cliente?cpf_cnpj=...` — lookup helper para UI mostrar badge "Cliente já cadastrado"
- `POST /api/v1/crm/leads/{id}/convert` — idempotente: se já tem cliente_id, só muda status; senão cria/upsert cliente
- `POST /api/v1/crm/opportunities/{id}/gerar-proposta` — gera Proposta pré-preenchida a partir da oportunidade

**Webhooks disparados automaticamente:** `lead.created|updated|converted|deleted`, `opportunity.created|updated|stage_changed|won|lost|deleted|pos_venda_iniciada`, `activity.created|completed`. Implementação assíncrona em thread daemon (`app/services/webhook_dispatcher.py`).

**Pipelines vinculados Venda→Pós-Venda (Fase 2):** `crm_pipelines.tipo` (venda/pos_venda/generico) + `pipeline_pos_venda_id`. Ao ganhar na pipeline de venda, a MESMA oportunidade é promovida para a pós-venda vinculada (não duplica, não some da venda). `crm_opportunities.pos_venda_pipeline_id/pos_venda_stage_id/pos_venda_iniciada_em`. Ver skill `crm-opportunity-page` e memória.

**Automação por etapa + SLA (Fase 3, qualquer pipeline):** cada `crm_stages` tem `sla_dias` + tarefa automática (`auto_tarefa_assunto/descricao/tipo/prazo_dias`, `auto_notificar`). Ao entrar numa etapa, o motor cria a "próxima ação" (activity `auto`, com `stage_id`) — card 11 do detalhe. Card 5 alerta SLA estourado/cliente parado. Configurável no form de etapa em `/crm/pipelines`.

**Pipeline default seedado no startup** com 7 stages: Prospecção → Qualificação → Visita → Proposta → Negociação → Ganho / Perdido.

## Perfis — RBAC dinâmico (granular)

**Não há mais perfis fixos admin/editor/leitor.** A autorização é por **perfis customizáveis** (`rbac_roles`) com **matriz recurso × ação** (`ver`/`criar`/`editar`/`excluir`). Gerenciável em `/perfis` (UI tipo Salesforce). Ver memória `project_rbac_module` e (se existir) skill `rbac-module`.

- **Catálogo** em `app/auth/recursos.py` — 21 recursos (clientes, habitacao, proposta, parentesco, recibo, financiamento, crm_*, cad_*, logos, usuarios) × 4 ações. **FONTE ÚNICA** usada por seed, enforcement e UI.
- **Enforcement** (`app/auth/permissions.py`): `Depends(require_permission("<recurso>","<acao>"))` nos routers; `require_admin` p/ settings. Mapa método→ação: GET=ver, POST=criar, PUT/PATCH=editar, DELETE=excluir; PDF/XLSX/ações especiais=ver/editar conforme o caso.
- **Perfis seedados no startup** (`rbac_repo.seed_roles_e_migrar`): "Administrador" (`is_system`, tudo `True`, protegido contra edição/exclusão) e "Somente Leitura" (`ver` em tudo). Usuários sem `role_id` são migrados.
- **JWT** carrega `role_id, role_nome, is_admin`; login e `/auth/me` retornam o dict `permissoes` completo. Mudanças de permissão propagam sem re-login (re-resolvidas por request).
- **Frontend**: `api.can(recurso, acao)` (em `api.js`) gate de botões/páginas; `sidebar.js` esconde itens por `can(recurso,'ver')`.
- **Sempre públicos/abertos** (só `get_current_user` ou sem auth): `lookup/*`, lookup de cliente por CPF, `logos` GET, `corretores` POST (gate por flag), `settings/public/*`, CRM `dashboard`.

Ao adicionar recurso novo: registre a key em `app/auth/recursos.py` (seed recria perms no próximo startup), use `require_permission` no router e `api.can` na página.

## Segurança

- `JWT_SECRET` obrigatório em produção via `.env` (chmod 600, **não commitar**). Se não setado, o app gera um aleatório por processo — invalidando tokens entre reinícios.
- Security headers aplicados em todas as respostas: HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy.
- Senhas bcrypt (custo padrão) + fallback leitura de `scrypt:`/`pbkdf2:` (werkzeug legado).
- Rate limit in-memory no login (10 tentativas / 60s por IP).
- CORS restrito a `portal.*`, `habitacao.*`, `proposta.*`, e dev local.
- Templates Jinja com `autoescape=True`.

## Regras

- PDF DEVE caber em 1 página A4 (auto-scale via Playwright em `app/services/pdf_service.py`).
- Margens PDF: 15mm laterais, 10mm topo/base. Viewport: 680px.
- CPF normalizado (só dígitos) em todo o pipeline. Formatação `000.000.000-00` só no render do PDF.
- Postgres isolado na rede `habitacao-internal`. Hostname canônico `habitacao_db` (não usar `db` — VIP do Swarm).
- Healthcheck do DB via `pg_isready` + do portal via `/healthz`. Readiness profundo em `/readyz`.

## Infraestrutura

- Servidor: mordor (172.30.0.49)
- DNS: `portal.amimoveis.tec.br` + `habitacao.*` + `proposta.*` → 177.93.132.151
- Redes: `earthnet` (externa, Traefik) + `habitacao-internal` (overlay)
- Volume: `habitacao-pgdata` (dados postgres persistentes)
- SSL: Let's Encrypt via Traefik (automático)
- Redirects legados em Traefik (30 dias pós-cutover)

## Backup & recovery

Backups guardados em `~/backups/` (host mordor):
- `habitacao_YYYYMMDD_HHMM.dump` — pg_dump custom (restore via `pg_restore`)
- `habitacao_v2_data_YYYYMMDD_HHMM.sql` — `--data-only --column-inserts` (restore via `psql -f`)

Para restaurar do zero num banco vazio:
```bash
DB=$(docker ps -qf name=habitacao_db)
docker exec -i $DB psql -U habitacao -d habitacao < init_v2.sql
docker exec -i $DB psql -U habitacao -d habitacao < backup_data.sql
docker service update --force habitacao_portal
```

## Histórico de migração

- **Fase 0-1**: Backup + DNS + validação de restore.
- **Fase 2-5**: Flask → FastAPI com schema v2 em paralelo, frontend vanilla, PDF service preservado.
- **Fase 6 (cutover)**: Flask removido, Traefik redirects 301, tabelas legadas renomeadas.
- **Save-wipe-restore**: DROP SCHEMA + init_v2.sql + restore de dump limpo. Zero rastro do legado.
- **Hardening profissional**: JWT_SECRET real via .env, security headers, lifespan handler, Pydantic ConfigDict, Dockerfile multi-stage, cleanup completo.
- **Fase 7 (pendente, T+30 dias)**: se zero hits nos redirects → remover routers Traefik legados.
