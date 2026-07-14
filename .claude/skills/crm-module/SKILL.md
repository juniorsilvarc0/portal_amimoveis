---
name: crm-module
description: Guia do módulo CRM (Salesforce-style) do Portal AM Imóveis — Leads, Opportunities, Pipeline Kanban, Activities, Campaigns, Webhooks, Import CSV. Usar quando o usuário pedir mudanças em qualquer recurso CRM ou criar novas integrações.
---

# crm-module — CRM Salesforce-style integrado ao Portal AM Imóveis

O módulo CRM adiciona uma camada completa de gestão de vendas ao portal, integrada nativamente com **Clientes**, **Propostas**, **Recibos** e **Imóveis**. Inspirado no modelo conceitual do Salesforce, mas 100% custom.

---

## Modelo de dados (11 tabelas)

> Inclui `crm_opp_documentos` (documentos da oportunidade — card 10 + aba Documentos; ver skill `crm-opportunity-page`).

```
crm_pipelines       — funis configuráveis (1 default)
                      tipo: venda | pos_venda | generico ; pipeline_pos_venda_id (vínculo venda→pós-venda)
  └ crm_stages      — etapas com ordem, probabilidade, cor, tipo (aberto|ganho|perdido)
                      ORDER BY ordem, id (desempate por id; editar etapa NÃO reordena).
                      criar() atribui MAX(ordem)+1. PUT /stages/{id} edita; POST /stages/reorder.
                      AUTOMAÇÃO por etapa: sla_dias (prazo) + auto_tarefa_assunto/descricao/tipo/prazo_dias
                      + auto_notificar. Ao entrar na etapa, o motor cria a "próxima ação" (activity auto).
                      Ver skill crm-opportunity-page.

crm_campaigns       — origem dos leads (Meta Ads, indicação, site...)

crm_leads           — prospects ainda não convertidos
  ├ FK cliente_id (preenchido após convert)
  ├ FK campaign_id, cidade_id, imovel_interesse_id
  └ status: novo | contatado | qualificado | convertido | reativado | descartado

crm_opportunities   — negociações em andamento
  ├ FK cliente_id (NOT NULL — Cliente é obrigatório desde 2026-05-12), lead_id (opcional),
  │    pipeline_id, stage_id, imovel_id, campaign_id, proprietario_id, proposta_id
  └ status: aberta | ganha | perdida

crm_opp_notas       — notas (título + corpo) de uma oportunidade, com criado_por_id

crm_activities      — tarefas, ligações, reuniões, e-mails, WhatsApp, notas
  └ FK lead_id, opportunity_id, cliente_id, proprietario_id

crm_stage_history   — auditoria de movimentação no funil (insert-only)

crm_webhooks        — notificações de saída (URL + secret HMAC)
crm_webhook_logs    — histórico de disparos com status_code, response_body, erro
```

Schema canônico em `init_v2.sql` (linhas das tabelas `crm_*`). Pipeline padrão é seedado se não existir nenhum.

---

## API REST — `/api/v1/crm/*`

Todos protegidos por JWT. **Autorização via RBAC granular** (`require_permission("<recurso>","<acao>")`, NÃO mais `require_role("admin")`): recursos `crm_leads`, `crm_opportunities`, `crm_activities`, `crm_campaigns`, `crm_pipelines` (cobre pipelines+stages), `crm_webhooks`. GET=ver, POST=criar, PUT/PATCH=editar, DELETE=excluir; ações especiais (convert/stage/gerar-proposta)=editar; import CSV=`crm_leads.criar`; `dashboard` só exige autenticação. Ver [[project_rbac_module]] e skill `rbac-module`.

| Recurso | Endpoints |
|---|---|
| **Pipelines** | GET/POST/PUT/DELETE `/pipelines`, GET `/pipelines/default`, GET `/pipelines/{id}` (com stages) |
| **Stages** | GET/POST/PUT/DELETE `/stages`, POST `/stages/reorder` (reordena via lista de ids; ordem 1..n) |
| **Campaigns** | GET/POST/PUT/DELETE `/campaigns` (paginado) |
| **Leads** | GET/POST/PUT/DELETE `/leads` (paginado), GET `/leads/{id}` (com timeline), GET `/leads/lookup-cliente?cpf_cnpj=`, **POST `/leads/{id}/convert`** |
| **Opportunities** | GET/POST/PUT/DELETE `/opportunities` (paginado), `PATCH /opportunities/{id}` (inline 1 campo), GET `/opportunities/kanban`, GET `/opportunities/{id}/full` (opp+cliente+notas+stage_history+timeline), POST `/opportunities/{id}/stage`, **POST `/opportunities/{id}/gerar-proposta`** |
| **Opp. Notas** | GET/POST `/opportunities/{id}/notas`, PUT/DELETE `/opportunities/notas/{nota_id}` |
| **Activities** | GET/POST/PUT/DELETE `/activities`, POST `/activities/{id}/concluir` |
| **Webhooks** | GET/POST/PUT/DELETE `/webhooks`, GET `/webhooks/{id}/logs`, POST `/webhooks/{id}/test` |
| **Import** | POST `/import/leads` (multipart CSV) |
| **Dashboard** | GET `/dashboard` (métricas agregadas) |

---

## Modelo de relacionamento (decidido em 2026-05-12)

**Cliente é central. Lead é evento de captação. Opportunity é negociação.**

```
Cliente (1 por CPF)
  ├─ Lead #1  (origem: site, jan)      ──► status: convertido
  ├─ Lead #2  (origem: meta_ads, mar)  ──► status: reativado
  ├─ Lead #3  (origem: indicacao, jul) ──► status: novo
  │
  ├─ Opportunity #1  (lead_id: 1)
  └─ Opportunity #2  (lead_id: 3)
```

**Regras:**
- **1 Cliente : N Leads** — mesmo CPF pode gerar múltiplos Leads ao longo do tempo (cada campanha que ele responde)
- **Auto-vínculo por CPF** — ao criar Lead, se CPF/CNPJ já existir em Clientes, `cliente_id` é preenchido automaticamente e status default vira `reativado`
- **`opp.cliente_id` é OBRIGATÓRIO** — Cliente é central. Sem Cliente, não há Opportunity.
- **`opp.lead_id` é OPCIONAL** — metadata de origem (qual Lead originou a Opp). Pode ser null se Opp foi criada manualmente (ex.: cliente existente indicou outro imóvel)
- **Cliente pode ser criado direto** (sem passar por Lead) — via formulário de Cliente, Habitação, Proposta, Recibo. Continua válido.

## Integrações com módulos existentes

### Lead → Cliente (conversão idempotente)
`POST /api/v1/crm/leads/{id}/convert` faz:
1. **Se o lead já tem `cliente_id`** (auto-vinculado por CPF): apenas atualiza status. NÃO cria cliente duplicado.
2. **Senão**: `clientes_repo.upsert_por_cpf` (se CPF válido ≥11 dígitos) ou cria novo com `cpf_pendente=True`
3. Marca o lead como `convertido` (registra `data_conversao` e `cliente_id`)
4. Opcionalmente cria uma **Opportunity** no pipeline default (`body.criar_opportunity = true` por padrão), passando `lead_id` para preservar atribuição
5. Dispara webhook `lead.converted`

### Lookup helper: `GET /api/v1/crm/leads/lookup-cliente?cpf_cnpj=...`
Usado pelo form de Lead em tempo real. Retorna `{cliente, leads_anteriores, ja_foi_cliente}` se houver match, senão `{cliente: null}`. UI mostra badge "Cliente já cadastrado: NOME (#X)" abaixo do campo CPF.

### Opportunity → Proposta
`POST /api/v1/crm/opportunities/{id}/gerar-proposta` cria uma **Proposta** pré-preenchida (módulo já existente) com os dados da oportunidade (cliente, imóvel, valor) e vincula via `proposta_id`. Retorna `edit_url` para o usuário editar/personalizar.

### Activities ↔ Cliente / Lead / Opportunity
Cada activity tem FKs para os 3, mas tipicamente só um é preenchido. Endpoint `GET /api/v1/crm/leads/{id}` e `/opportunities/{id}` retornam `activities` (timeline ordenada por data DESC).

---

## Webhooks de saída

Cada webhook tem:
- **URL** destino (qualquer HTTPS)
- **Eventos** assinados (csv: `lead.created,opportunity.won,...`) ou `*` para tudo
- **Secret HMAC-SHA256** opcional (header `X-CRM-Signature: sha256=...`)
- **Logs** automáticos de cada disparo

Envio **assíncrono em thread daemon** (não bloqueia request). Implementado em `app/services/webhook_dispatcher.py`.

**Eventos disparados automaticamente:**
- `lead.created`, `lead.updated`, `lead.converted`, `lead.deleted`
- `opportunity.created`, `opportunity.updated`, `opportunity.stage_changed`, `opportunity.won`, `opportunity.lost`, `opportunity.deleted`
- `activity.created`, `activity.completed`

**Payload format:**
```json
{
  "evento": "opportunity.won",
  "timestamp": "2026-05-12T14:30:00Z",
  "data": { ...objeto completo... }
}
```

---

## Import CSV

`POST /api/v1/crm/import/leads` aceita CSV (multipart `arquivo`). Implementação em `app/services/crm_importer.py`:
- Detecta separador automaticamente (`, ; | tab`)
- UTF-8 com fallback Latin-1
- Mapa de colunas flexível: aceita `nome` ou `name`, `whatsapp` ou `wpp` ou `celular`, etc.
- Retorna `{sucesso, falhas: [{linha, erro}], total}`

---

## Frontend

| Página | URL | Função |
|---|---|---|
| Dashboard | `/crm` | Métricas + ações rápidas |
| Leads | `/crm/leads` | Lista + busca + convert |
| Lead form | `/crm/leads/novo` ou `/crm/leads/{id}/editar` | CRUD |
| Opportunities | `/crm/opportunities` | Lista |
| Kanban | `/crm/kanban` | Drag-drop entre stages |
| **Opportunity detalhe** | `/crm/opportunities/{id}` | **13 cards, edição inline, setinhas verdes, SLA — ver skill `crm-opportunity-page`** |
| Opportunity criar | `/crm/opportunities/novo` | Criação (form). `/{id}/editar` foi REMOVIDO → redirect 302 pro detalhe (edição é inline) |
| Activities | `/crm/activities` | Lista global |
| Activity form | `/crm/activities/nova` ou `.../editar` | CRUD |
| Campaigns | `/crm/campaigns` | CRUD via modal |
| Pipelines | `/crm/pipelines` | Config funis + stages |
| Webhooks | `/crm/webhooks` | Config + teste + logs |
| Import | `/crm/import` | Upload CSV |

Submenu **CRM** no sidebar (`static/js/sidebar.js`).

---

## Convenções importantes

1. **NUNCA criar opportunity sem `cliente_id`** — desde 2026-05-12, Cliente é OBRIGATÓRIO em Opportunity (`crm_opportunities.cliente_id NOT NULL`). Use `/crm/leads/{id}/convert` para criar opp a partir de Lead.
2. **NUNCA criar opportunity sem pipeline_id E stage_id** — são obrigatórios. Use o pipeline default via `/pipelines/default` se nada for fornecido.
2. **stage.tipo dita o status da opportunity**: mover para stage `ganho` muda status para `ganha`; `perdido` → `perdida`; qualquer outro → `aberta`. Logic em `crm_opportunities_repo.mudar_stage`.
3. **Lead.convert é idempotente** — se já tem `cliente_id`, não duplica. Pode chamar várias vezes.
4. **Webhooks são best-effort** — falhas não quebram a request principal, só viram log.
5. **Pipeline default é único** — ao marcar `is_default=true` num novo pipeline, os outros são automaticamente desmarcados.
6. **Activities polimórficas** — uma activity tem `lead_id` OU `opportunity_id` OU `cliente_id` (nullable em todos), mas tipicamente só um preenchido.

---

## Como adicionar um novo recurso CRM

1. Adicionar tabela em `init_v2.sql` (com FKs apropriadas)
2. Criar `app/db/crm_<recurso>_repo.py` no padrão (use crm_leads_repo.py como template)
3. Adicionar schemas em `app/schemas/crm.py`
4. Adicionar endpoints em `app/routers/crm.py`
5. Criar páginas frontend `static/crm_<recurso>.html` e `crm_<recurso>_form.html`
6. Adicionar item no sidebar (`static/js/sidebar.js`)
7. Registrar rotas em `app/routers/pages.py`
8. Disparar webhooks relevantes via `webhook_dispatcher.disparar("<recurso>.<evento>", dados)`

---

## Arquivos-referência

| O quê | Onde |
|---|---|
| Schema canônico | `init_v2.sql` (seção CRM) |
| Repo modelo | `app/db/crm_leads_repo.py` |
| Repo com história | `app/db/crm_opportunities_repo.py` |
| Schemas Pydantic | `app/schemas/crm.py` |
| Router | `app/routers/crm.py` |
| Webhook dispatcher | `app/services/webhook_dispatcher.py` |
| Importer CSV | `app/services/crm_importer.py` |
| Frontend Kanban | `static/crm_kanban.html` |
| Sidebar | `static/js/sidebar.js` |

---

## Smoke tests rápidos

```bash
TOKEN=$(curl -sk -X POST https://portal.amimoveis.tec.br/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"senha\":\"$ADMIN_PASSWORD\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Pipeline default
curl -sk -H "Authorization: Bearer $TOKEN" https://portal.amimoveis.tec.br/api/v1/crm/pipelines/default

# Criar lead
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  https://portal.amimoveis.tec.br/api/v1/crm/leads \
  -d '{"nome":"TESTE CRM","whatsapp":"86999999999","origem":"site"}'

# Converter em cliente + criar opportunity
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  https://portal.amimoveis.tec.br/api/v1/crm/leads/1/convert -d '{}'

# Dashboard
curl -sk -H "Authorization: Bearer $TOKEN" https://portal.amimoveis.tec.br/api/v1/crm/dashboard
```
