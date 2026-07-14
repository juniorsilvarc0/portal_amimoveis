# CONTEXTO ATUAL DO PROJETO — Portal AM Imóveis

> Documento mestre de retomada (varredura de código 2026-06-22, **revisado 2026-07-01**). Fonte de verdade do schema: `init_v2.sql`. Reflete o **código real**. `CLAUDE.md` foi atualizado em 2026-06-30 e **hoje está alinhado** (RBAC granular, 32 tabelas, CRM com 11 tabelas incl. `crm_opp_documentos`, pós-venda/SLA) — a antiga divergência de RBAC/contagem de tabelas foi resolvida. Estado atual: **32 tabelas**, app FastAPI 2.0.0 com **21 routers**, CRM com **59 endpoints** e **11 tabelas**.

---

## 1. Visão geral

Portal AM Imóveis (Andreia Miranda Imóveis) é um sistema web unificado de gestão imobiliária: documentos (habitação PMCMV, propostas, financiamento, recibo, termo de parentesco), **CRM Salesforce-style** completo, RBAC granular e cadastros auxiliares, sob o domínio canônico `https://portal.amimoveis.tec.br`. Stack: **FastAPI 0.115 + Pydantic v2 + psycopg2** (app `app/main.py`, versão 2.0.0, 21 routers montados) sobre **PostgreSQL 16**, servido por **Gunicorn (2 UvicornWorker) + Tini**; PDF via **Jinja2 + Playwright/Chromium**; frontend **HTML/CSS/JS vanilla sem build** (singletons em `window`); deploy em **Docker Swarm + Traefik**. Auth é **JWT HS256/24h** (python-jose + bcrypt, fallback scrypt/pbkdf2 werkzeug). Cliente é a entidade central do domínio (1 por CPF), referenciada por todos os documentos e pelo CRM.

---

## 2. Módulos & funcionalidades atuais

| Módulo | Router / arquivos | O que faz |
|---|---|---|
| **Clientes** | `routers/clientes.py`, `db/clientes_repo.py`, `db/conjuges_repo.py`, `db/cliente_notas_repo.py` | Entidade central. CRUD + lookup por CPF (3 formas), cônjuge 1:1, notas (Chatter), `/{id}/full` (relacionamentos aninhados), PATCH parcial, `upsert_por_cpf`. CPF normalizado (só dígitos). Update é parcial (não nulifica ausentes). |
| **Habitação** | `routers/habitacao.py`, `db/habitacao_repo.py`, `templates/ficha_habitacional.html` | Ficha PMCMV (snapshot textual de rendimentos titular/cônjuge, ~46 campos flat). PDF (Playwright) **e XLSX** (único export XLSX do sistema). `COALESCE(parceiro.nome, construtora_nome)`. |
| **Proposta** | `routers/propostas.py`, `db/propostas_repo.py`, `templates/proposta_imoveis.html` | Proposta de compra com pagamentos nested (replace-all em transação única). PDF. Snapshot de corretor (nome/creci) + `corretor_id` FK. |
| **Financiamento** | `routers/financiamentos.py`, `db/financiamentos_repo.py` | CRUD com filtros (analise, modalidade, cidade_id, parceiro_id, cliente_id), JOINs de nomes. Valores `NUMERIC(15,2)`. **Sem PDF/XLSX** (ponto de extensão). |
| **Recibo** | `routers/recibos.py`, `db/recibos_repo.py`, `templates/recibo.html` | Recibo PDF com **logo dinâmica via data URI base64**, valor por extenso (num2words), toggle CPF/CNPJ, múltiplas formas de pagamento (JSONB), **cliente opcional**. |
| **Parentesco** | `routers/parentescos.py`, `db/parentescos_repo.py`, `templates/parentesco.html` | Termo/declaração CAIXA de parentesco (Lei 14.620/2023). PDF com logo CAIXA estática. cliente_id obrigatório. |
| **CRM** | `routers/crm.py` (59 endpoints), 9 repos `crm_*`, `services/webhook_dispatcher.py`, `services/crm_importer.py`, `services/excel_service.py` (relatório contábil) | Pipelines/Stages (Kanban drag-drop, **SLA + tarefa automática por etapa**), **pipelines Venda→Pós-Venda vinculadas** (promoção automática ao ganhar), Campaigns, Leads (auto-vínculo por CPF), Opportunities (~118 colunas, notas, **documentos/checklist BYTEA**, gerar-proposta, stage move, full, detalhe 13-card Salesforce), Activities, Webhooks HMAC, Import CSV, Dashboard, **relatório contábil XLSX**. |
| **RBAC** | `auth/recursos.py`, `auth/permissions.py`, `db/rbac_repo.py`, `routers/rbac.py`, `schemas/rbac.py` | Perfis customizáveis + matriz recurso×ação (21 recursos × ver/criar/editar/excluir). Enforcement `require_permission`. |
| **Logos** | `routers/logos.py`, `db/logos_repo.py` | Upload/list/delete de logomarcas (BYTEA). `GET /{id}/imagem` serve bytes **público** (sem auth). Usadas no recibo. |
| **Settings** | `routers/settings.py`, `db/settings_repo.py` | KV `app_settings`. Leitura pública whitelist (`corretores_publico_ativo`); GET/PUT de qualquer chave via `require_admin`. Helpers `get_bool/set_bool`. |
| **Corretores** | `routers/corretores.py`, `db/corretores_repo.py` | Cadastro com **autocadastro público** (POST sem auth, gated por setting `corretores_publico_ativo`). Campos de brinde (tamanho_camisa, chocolate_preferido, bebida_preferida). |
| **Cadastros aux** | `cidades/agencias/gerentes/parceiros/imoveis/correspondentes.py` | CRUD uniforme idêntico (molde de `cidades_repo.py`). Recurso de permissão prefixado `cad_*`. |
| **Usuários** | `routers/usuarios.py`, `db/usuarios_repo.py` | CRUD admin. Soft delete (`ativo=FALSE`) — **único repo com soft delete**. Sync de perfil legado por role. |
| **Auth** | `auth/router.py`, `auth/jwt.py`, `auth/dependencies.py` | `/login` (rate-limit 10/60s/IP), `/me`, `/refresh`. Resolve role do banco em tempo real em `/me` e `/refresh`. |

---

## 3. Modelo de dados (32 tabelas; fonte: `init_v2.sql`)

`init_v2.sql` é a **fonte única**, aplicada idempotentemente no startup via `run_init_sql()` (CREATE IF NOT EXISTS + blocos `DO $$ ... EXCEPTION` para ALTER in-place). **Não há Alembic** — migrações são ALTERs com `EXCEPTION WHEN others THEN NULL` (silenciam erros).

**Núcleo / Sistema**
- `usuarios` — perfil CHECK `admin|usuario` (não ENUM), `role_id` FK→rbac_roles ON DELETE SET NULL, `ativo` (soft delete).
- `rbac_roles` — nome UNIQUE, `is_system` (Administrador protegido), ativo.
- `rbac_role_permissions` — `role_id` FK CASCADE, recurso, `ver/criar/editar/excluir` bool, UNIQUE(role_id, recurso).
- `app_settings` — KV (key PK, value); seed `corretores_publico_ativo='true'`.

**Cadastros auxiliares** (FKs de cidade tipicamente ON DELETE RESTRICT)
- `cidades` (nome+uf UNIQUE), `agencias`, `gerentes`, `parceiros` (tipo ENUM), `imoveis`, `correspondentes`, `corretores`.

**Cliente e documentos** (FK cliente→documento sempre **ON DELETE RESTRICT** — não dá pra apagar cliente com documentos)
- `clientes` — `cpf` CHAR(11) NOT NULL com **UNIQUE PARCIAL** (`clientes_cpf_valid_idx WHERE cpf_pendente=false`, permite múltiplos CPF pendente); expansão Salesforce (tipo_pessoa, codigo_sap/crm, nome_mae/pai, proprietario_id/criado_por_id/modificado_por_id).
- `cliente_notas` — Chatter, FK CASCADE.
- `conjuges` — 1:1 (cliente_id UNIQUE, CASCADE).
- `habitacao_fichas` — snapshot **TEXT** de quase todos campos financeiros; `construtora_nome` fallback; `legacy_ficha_id`.
- `propostas` (`valor_total`/datas TEXT) + `proposta_pagamentos` (CASCADE).
- `financiamentos` — modalidade ENUM, analise ENUM, valores NUMERIC.
- `parentescos`, `recibos` (cliente_id **nullable** pós-migração, logo_id FK, `formas_pagamento` JSONB), `logos` (arquivo BYTEA).

**CRM** (11 tabelas)
- `crm_pipelines` (is_default único garantido em código; **`tipo` venda|pos_venda|generico + `pipeline_pos_venda_id`** para vincular funil de venda ao de pós-venda), `crm_stages` (CASCADE, tipo aberto|ganho|perdido, cor default #065676; **`sla_dias` + tarefa automática `auto_tarefa_assunto/descricao/tipo/prazo_dias` + `auto_notificar`**).
- `crm_campaigns`.
- `crm_leads` — `cpf_cnpj` (idx parcial), `cliente_id` FK SET NULL (auto-link), status `novo|contatado|qualificado|convertido|reativado|descartado`.
- `crm_opportunities` — **`cliente_id` INT NOT NULL ON DELETE RESTRICT** (toda opp exige cliente); `lead_id` SET NULL (metadata de origem); `proposta_id` SET NULL; **~118 colunas Salesforce-like** (PAC, Emcash, entrada_facilitada, pagadoria, rating, negociação especial, simulação banco/plataforma, FGTS/MCMV/MRV, equipe via FKs usuarios + bloco "Pós-Venda PHB": imovel_*, venda_*, ef_*, pac_*, comissao_*, contabil_*, construtora_nome). **Jornada dupla**: `pipeline_id`/`stage_id` = venda; `pos_venda_pipeline_id`/`pos_venda_stage_id`/`pos_venda_iniciada_em` = pós-venda (promoção automática ao atingir etapa tipo `ganho` numa pipeline com link).
- `crm_opp_notas` (CASCADE) — Chatter da oportunidade.
- `crm_opp_documentos` (CASCADE) — documentos/checklist da oportunidade (card 10 + aba Documentos): `arquivo` BYTEA nullable, nome_arquivo, content_type, tamanho, status pendente|enviado|assinado|concluido, criado_por_id.
- `crm_activities` — polimórfica (lead_id/opportunity_id/cliente_id todos nullable+CASCADE, sem CHECK garantindo ≥1); **`stage_id` + `auto`** (tarefa automática gerada pelo motor de etapa).
- `crm_stage_history` (CASCADE).
- `crm_webhooks` (eventos CSV), `crm_webhook_logs` (payload JSONB, CASCADE).

**ENUMs Postgres nativos (3)**: `tipo_parceiro` (CONSTRUTORA|IMOBILIARIA|AUTONOMO), `modalidade_imovel` (CASA|APARTAMENTO|TERRENO|COMERCIAL), `status_analise` (PENDENTE|EM_ANALISE|APROVADO|REPROVADO|CANCELADO). `usuarios.perfil` é **CHECK** (admin|usuario), não ENUM. Enums do CRM são TEXT sem CHECK (validação só na app).

**Seed embutido**: pipeline default "Vendas Imobiliárias" (is_default=TRUE) com 7 stages (Prospecção 10% → Qualificação 25% → Visita 40% → Proposta 60% → Negociação 80% → Ganho 100%/ganho → Perdido 0%/perdido), só se `crm_pipelines` vazio.

---

## 4. Superfície de API

Tudo sob `/api/v1/*`, Bearer JWT (exceto `/auth/login` e endpoints públicos). Listagem retorna `{data:[...], meta:{page, per_page, total, total_pages}}` (o envelope é montado **nos routers**; repos retornam tupla `(rows, total)`). Autorização majoritariamente via `require_permission(recurso, acao)`.

**Convenção de recurso de permissão (gotcha)**: documentos usam **singular** (`proposta`, `parentesco`, `financiamento`, `recibo`) mesmo com path plural; cadastros usam prefixo **`cad_`** (`cad_cidades`...). Registrar recurso novo em `auth/recursos.py` senão `require_permission` nega acesso.

**Endpoints especiais (não-CRUD)**:
- Clientes: `GET ?cpf=`, `GET /por-cpf/{cpf}`, `GET /{id}/full`, `PATCH /{id}`, `GET|POST /{id}/notas`, `DELETE /notas/{nota_id}`.
- Habitação: `GET /{id}/pdf` + `GET /{id}/xlsx`. Propostas/Parentescos/Recibos: `GET /{id}/pdf`. Financiamentos: sem PDF.
- Corretores: `POST` público (gated). Logos: `GET /{id}/imagem` público. Settings: `GET /public/{key}` público.
- Perfis/RBAC (`/api/v1/perfis`): CRUD + `GET /perfis/recursos` (catálogo). Lookup: `/lookup/cidades-publico` (público) + `/lookup/contadores`.
- **CRM (59 endpoints)**: `pipelines/default`, `stages/reorder`, `leads/lookup-cliente`, `leads/{id}/convert`, `opportunities/kanban` (detecta pipeline `tipo` venda/pós-venda), `opportunities/{id}/stage`, `opportunities/{id}/full` (devolve `fase_ativa`, pipeline/stage ativos, notas, documentos, próxima ação, SLA), `opportunities/{id}/notas`, `PATCH opportunities/{id}`, `opportunities/{id}/gerar-proposta`, **`opportunities/{id}/documentos` (GET/POST multipart) + `opportunities/documentos/{doc_id}` (PUT/DELETE) + `.../arquivo` (anexar/download)**, `activities/{id}/concluir`, `webhooks/{id}/logs`, `webhooks/{id}/test`, `import/leads` (CSV multipart ≤10MB), `dashboard`, **`relatorio/contabil` (XLSX via openpyxl, filtros mês/ano/imóvel/proprietário/comissão/pipeline)**. **Ordem de rotas sensível**: literais antes de `/{id}`.
- Health/Docs: `GET /healthz`, `GET /readyz` (SELECT 1), `/docs`, `/redoc`, `/openapi.json`.
- Pages (`routers/pages.py`): servem HTML sem auth no backend — proteção real é client-side + nos routers de API.

---

## 5. Subsistema de PDF/XLSX

Núcleo: `app/services/pdf_service.py` (Jinja2 + Playwright/Chromium headless). Motor genérico `_gerar_pdf` (async) + wrapper síncrono `gerar_pdf`; 4 funções de alto nível: **`gerar_pdf_habitacao`, `gerar_pdf_proposta`, `gerar_pdf_parentesco`, `gerar_pdf_recibo`**. Cada uma usa um mapper `_map_*_to_template` que achata o schema v2 para campos flat dos templates.

**Helpers de formatação**: `_format_data_br`, `_format_cpf`, `_format_cnpj`, `_format_doc` + `_doc_label` (toggle CPF/CNPJ por contagem de dígitos), `_format_valor_br`, `_valor_por_extenso` (num2words), `_formas_pagamento_breakdown`.

**XLSX**: `app/services/excel_service.py` (openpyxl) → `gerar_xlsx_habitacao` (importa `_map_habitacao_to_template` do pdf_service p/ paridade PDF↔XLSX) **e `gerar_xlsx_relatorio_contabil`** (relatório contábil consolidado de vendas/comissões do CRM, alimentado por `crm_opportunities_repo.relatorio_contabil(filtros)`).

**Templates** (`templates/`): `ficha_habitacional.html` (sem logo), `proposta_imoveis.html` (logo estática, brand #E5094B), `recibo.html` (**logo dinâmica `data:` base64**), `parentesco.html` (logo CAIXA estática). Todos têm container raiz `id=wrap` para auto-scale.

**Regras**: PDF DEVE caber em 1 página A4 (auto-scale via Playwright). Margens 15mm laterais, 10mm topo/base, viewport 680px. CPF só-dígitos no pipeline, formatação só no render.

**Fragilidades**: detecção de 2ª página por contagem de `b'/Type /Page\n'` (frágil); cada PDF abre/fecha um Chromium (sem pool, gargalo sob carga); pagamentos fora do key_map de 8 itens são descartados silenciosamente.

---

## 6. Frontend

Vanilla JS sem build. Cada página é HTML standalone que carrega scripts globais **em ordem fixa**: `api.js → sidebar.js → masks.js → [forms.js] → [modal.js] → [datagrid.js] → script da página`.

**Componentes compartilhados** (`static/js/`)
- `api.js` — `window.api`: get/post/put/patch/del/upload, login/me/logout/requireAuth, **`api.can(recurso, acao)`** (RBAC client-side: admin→tudo true, senão lê `localStorage('usuario').permissoes`), `downloadPdf/downloadFile`. Base `/api/v1`, token+usuario em localStorage, 401→logout.
- `sidebar.js` — `renderSidebar(container, path, user)`. Árvore em `buildMenuItems()`: Dashboard, Clientes, grupo **CRM**, grupo **Documentos** (Habitação/Proposta/Termo de Parentesco/Recibo), Financiamento, grupo **Cadastros**, Usuários/Perfis. Cada item filtrado por `api.can(recurso,'ver')`.
- `datagrid.js` — `DataGrid` (lista paginada server-side, busca debounced, sort, filtros, export CSV, mobile→cards). **Gotcha**: lê `result.total` no nível raiz, mas backend devolve `meta.total`.
- `modal.js` — `Modal` + estáticos `alert/confirm/prompt` (`Modal.prompt` adicionado 2026-06-22, anti-double-submit).
- `forms.js` — `FIELD_CATALOG` declarativo (`data-field`), `field/renderPlaceholders/init/readForm/fillForm/validate/isValidCPF`. UPPERCASE no blur.
- `masks.js` — máscaras + `autoMask(root)` via `data-mask`. `cpf_lookup.js` — `attachCpfLookup(...)`.

**Contrato de página nova** (copiar `static/cidades.html`): link CSS+DM Sans → estrutura `.app-layout > aside#sidebar + .main-content > .page-area` → scripts na ordem → IIFE `await api.requireAuth()`; `renderSidebar(...)`; gate `if(!api.can('<recurso>','ver')){location.href='/';return;}`; esconder botões de escrita via `api.can`. **RBAC client-side é cosmético; autorização real é no backend.**

**`layout.css`** tokens `:root`: `--primary #E5094B`, `--secondary #065676`, `--sidebar-width 240px/64px`.

**Páginas** (41 HTMLs em `pages.py`): forms compartilham 1 HTML entre novo/editar. Páginas de detalhe Salesforce: `cliente_detail.html`, `crm_opportunity_detail.html`. Pública: `corretor_publico.html`. **Inconsistência**: criação de cliente usa `cliente_detail.html` (`/cliente/novo`) mas edição usa `clientes_form.html` clássico (migração incompleta).

---

## 7. RBAC & Auth

**Modelo**: matriz recurso×ação sobreposta ao perfil legado binário (`admin|usuario`) que **persiste** no banco e nos tokens (convivência transicional).

**Catálogo (fonte única `auth/recursos.py`)** — `RECURSOS`: 21 keys `{key, label, grupo}`, `ACOES=('ver','criar','editar','excluir')`. As 21 keys: `clientes, habitacao, proposta, parentesco, recibo, financiamento, crm_leads, crm_opportunities, crm_activities, crm_campaigns, crm_pipelines, crm_webhooks, cad_cidades, cad_agencias, cad_gerentes, cad_parceiros, cad_imoveis, cad_correspondentes, cad_corretores, logos, usuarios`. O recurso **`usuarios`** governa CRUD de usuários **E** de perfis RBAC.

**Enforcement** (`auth/permissions.py`): `require_permission(recurso, acao)` faz **1 query por request** (sem cache no token) → mudar a matriz de um perfil propaga **na hora**. Admin (`is_system`) retorna tudo True sem ler o banco. `require_admin` exige is_system.

**`is_admin ≡ role.is_system`** — definido no login. Permissões **não** ficam no token (só `role_id/role_nome/is_admin`); por isso **trocar o role_id de um usuário só reflete no próximo login**.

**Seed (startup)**: "Administrador" (is_system, **tudo True reaplicado a todo startup** — editar permissões dele é fútil) + "Somente Leitura" (só ver, gravado só na criação). Ordem no lifespan: `run_init_sql` → `seed_admin_se_necessario` → `seed_roles_e_migrar`.

---

## 8. Infra & Deploy

**`Dockerfile.portal`** multi-stage: builder (venv) → runtime `python:3.12-slim` (Chromium, usuário não-root `portal`). `CMD gunicorn -k uvicorn.workers.UvicornWorker -w 2 --timeout 90 app.main:app`. Tini PID 1.

**`docker-compose.yml`** (Swarm): service `portal` (image `:latest`, env_file `.env`, redes `earthnet`+`habitacao-internal`, Traefik labels + redirects 301 legados) e `db` (`postgres:16-alpine`, volume `habitacao-pgdata`, `endpoint_mode: dnsrr`).

**Gotchas críticos**:
- **`docker stack deploy` nem sempre recria com `:latest` → SEMPRE `docker service update --force habitacao_portal`.**
- Hostname do banco DEVE ser `habitacao_db` (nunca `db` — VIP do Swarm; por isso `dnsrr`).
- `JWT_SECRET` via `.env`; se ausente, gera aleatório por processo → invalida tokens entre workers/restarts.
- **`static/` é baked na imagem (sem volume mount) → mudança em HTML/JS/CSS exige rebuild + deploy.**

**Testes** (`tests/`): 37 funções em 7 arquivos. Só `test_repos.py` (marker `db`) exige banco. `test_rbac.py` (13, mais recente). Cobertura rasa nos repos CRM/financiamento/propostas/recibo.

**Deploy**: `docker build -f Dockerfile.portal -t habitacao-portal:latest .` → `docker stack deploy -c docker-compose.yml habitacao` → `docker service update --force habitacao_portal` → smoke `/healthz` `/readyz`.

---

## 9. O que é NOVO/recente

- **Detalhe da oportunidade reescrito — layout "Pós-Venda PHB" (2026-06-30)**: `crm_opportunity_detail.html` com **13 cards** em `grid-template-areas` (`tabs/main/rail/full`), edição 100% inline (PATCH), setinhas verdes (`.caminho`) + faixa de SLA. A página `/crm/opportunities/{id}/editar` foi **REMOVIDA** (redirect 302 pro detalhe). Guia no skill `crm-opportunity-page`. `crm_opportunities` foi de ~88→**~118 colunas**.
- **Pipelines Venda→Pós-Venda vinculadas (Fase 2, 2026-06-30)**: `crm_pipelines.tipo` + `pipeline_pos_venda_id`; ao ganhar na venda, a MESMA opp é promovida à pós-venda (`pos_venda_*`), não duplica nem some da venda. Webhook `opportunity.pos_venda_iniciada`.
- **Automação + SLA por etapa (Fase 3, 2026-06-30, qualquer pipeline)**: `crm_stages.sla_dias` + tarefa automática; o motor cria a "próxima ação" (activity `auto` c/ `stage_id`) ao entrar numa etapa — card 11; card 5 alerta SLA estourado. Pipelines reais configuradas: PÓS-VENDA PHB (19 etapas), PÓS-VENDA THE (10 etapas), ATENDIMENTO PHB (venda, vinculada).
- **Documentos da oportunidade (2026-06-30)**: tabela `crm_opp_documentos` + `crm_opp_documentos_repo` + endpoints `/opportunities/{id}/documentos` (upload BYTEA, checklist, download); card 10 + aba Documentos + card 13 anexos contábeis.
- **Relatório contábil XLSX (2026-06-30)**: `GET /crm/relatorio/contabil` → `excel_service.gerar_xlsx_relatorio_contabil` (consolidado de vendas/comissões, filtros mês/ano/imóvel/proprietário/comissão/pipeline).
- **RBAC granular** (jun/2026) substitui na prática os perfis fixos admin/editor/leitor. **CLAUDE.md atualizado 2026-06-30** — já descreve tudo acima.
- **Notas/Chatter**: `cliente_notas` + `crm_opp_notas`.
- **Páginas de detalhe Salesforce**: `cliente_detail.html`, `crm_opportunity_detail.html` + `/{id}/full`, `PATCH`, `gerar-proposta`.
- **Recibo** (logos BYTEA, num2words, formas múltiplas JSONB), **Parentesco** (termo CAIXA), **Habitação XLSX**.
- **Autocadastro público de corretores** + settings públicos.
- `modal.js` com `Modal.prompt` (2026-06-22).

---

## 10. Gaps, TODOs e pontos de extensão

**Documentação**: ✅ resolvido — `CLAUDE.md` foi atualizado em 2026-06-30 (RBAC granular, 32 tabelas, CRM 11 tabelas, pós-venda/SLA/documentos). Os skills `crm-module`/`crm-opportunity-page`/`rbac-module` também foram atualizados. Manter este CONTEXT.md em sincronia a cada varredura.

**Pontos de extensão óbvios**:
- **Financiamento sem PDF/XLSX** — candidato a documento de financiamento.
- XLSX existe só p/ Habitação (export de ficha) e p/ o relatório contábil do CRM; proposta/recibo/parentesco não têm.
- Várias rotas de `pages.py` caem no fallback "Em construção".
- `corretor_publico.html` sem captcha/anti-spam.

**Riscos de consistência**:
- **`crm_opportunities`/`leads`/`activities` fazem overwrite total no UPDATE** (None inclusos) — um `PUT` que não reenvie um campo **o zera**. Coexistem 3 estratégias de update (parcial em clientes/usuarios/corretores; COALESCE em stages/pipelines/webhooks/campaigns; overwrite total no CRM core).
- `OpportunityBase.cliente_id` Optional no Pydantic mas NOT NULL no banco (validação manual → risco 500 vs 422).
- Enums do CRM são `str` sem `Literal` (sem enforcement Pydantic).
- Valores monetários/datas em habitação/proposta são `Optional[str]` (inviabiliza agregação SQL).
- `habitacao_fichas` duplica `conjuge_nome/cpf` inline além da tabela `conjuges`.

**Auth/RBAC**: trocar role não reflete até novo login; "Somente Leitura" não reconcilia no startup; `PUT /settings/{key}` aceita qualquer chave sem whitelist; rate limiter in-memory.

**Infra**: sem Alembic (ALTERs silenciam erros); webhooks fire-and-forget sem retry/fila; `crm_importer` insere 1 a 1 sem transação em lote; credenciais de banco em texto plano no compose; hard delete generalizado.

---

## 11. Como adicionar um recurso novo (padrão end-to-end)

1. **Schema** — `CREATE TABLE IF NOT EXISTS` (+ ALTERs via `DO $$ ... EXCEPTION`) em **`init_v2.sql`**.
2. **Repo** — `app/db/<recurso>_repo.py` no molde de `cidades_repo.py`: `listar(...)→(rows, total)`, `obter`, `criar→id`, `atualizar→bool`, `deletar→bool`.
3. **Schema Pydantic** — `app/schemas/<recurso>.py` com `Base → Create/Update/Read` (`ConfigDict(from_attributes=True)`). Decidir update parcial vs full-replace.
4. **Router** — `app/routers/<recurso>.py` CRUD uniforme, cada endpoint com `Depends(require_permission('<key>', '<acao>'))`. Envelope `{data, meta}`.
5. **Registrar recurso RBAC** — adicionar key em **`app/auth/recursos.py`** (senão `require_permission` nega). Convenção: documentos singular, cadastros `cad_`.
6. **Montar router** — `app.include_router(...)` em `app/main.py` (ordem: literais antes de `/{id}`).
7. **Frontend** — HTML(s) em `static/` (copiar `cidades.html`), scripts na ordem, gate por `api.can`.
8. **Sidebar** — entrada em `buildMenuItems()` de `static/js/sidebar.js`.
9. **Pages** — rotas em `app/routers/pages.py`.
10. **PDF (se documento)** — skills `/novo-documento` ou `/documento-pdf`: template Jinja, mapper + `gerar_pdf_<recurso>`, endpoint `/{id}/pdf` (1 página A4, container `id=wrap`).
11. **CRM (se aplicável)** — webhook via `webhook_dispatcher.disparar(evento, dados)`.
12. **Testes** — sem DB (monkeypatch/dependency_overrides) + marker `db` se possível.
13. **Deploy** — build → stack deploy → `docker service update --force habitacao_portal` → smoke-test.

---

**Arquivos-chave**: `app/main.py`, `init_v2.sql`, `app/auth/recursos.py`, `app/auth/permissions.py`, `app/routers/crm.py`, `app/services/pdf_service.py`, `static/js/api.js`, `static/js/sidebar.js`, `docker-compose.yml`, `Dockerfile.portal`. Skills: `crm-module`, `crm-pipeline-kanban` (fluxo pipeline/stages/oportunidades/kanban + jornada venda→pós-venda), `crm-opportunity-page` (detalhe 13 cards), `rbac-module`, `documento-pdf`, `novo-documento`.
