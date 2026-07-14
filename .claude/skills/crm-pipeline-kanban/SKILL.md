---
name: crm-pipeline-kanban
description: Guia do FLUXO Pipeline → Stages → Oportunidades → Kanban do CRM (Portal AM Imóveis) — configuração de funis, board Kanban drag-drop, jornada dupla Venda→Pós-Venda (promoção automática), lista e criação de oportunidade, mudança de etapa e SLA/automação. Usar SEMPRE que mexer no kanban, em pipelines/etapas, na lista/criação de oportunidade, no roteamento de stage (venda vs pós-venda) ou depurar "oportunidade some do kanban". Para a PÁGINA DE DETALHE da oportunidade (13 cards, edição inline), ver o skill `crm-opportunity-page`.
---

# crm-pipeline-kanban — o fluxo Pipeline · Stages · Oportunidades · Kanban

Cobre a **espinha dorsal do funil de vendas**: como pipelines, etapas (stages) e oportunidades se ligam, como o **Kanban** as agrupa, e como a **jornada Venda→Pós-Venda** funciona. É o "cola" entre os três recursos.

> **Divisão de skills:** este skill = fluxo/kanban/pipelines/lista+criação. O skill **`crm-opportunity-page`** = a página de DETALHE da oportunidade (13 cards, edição inline, SLA, documentos). O skill **`crm-module`** = CRM inteiro (leads, activities, campaigns, webhooks, import). Memória: [[project_crm_module]].

---

## Arquivos

| O quê | Onde |
|---|---|
| **Kanban (board drag-drop)** | `static/crm_kanban.html` (seletor de pipeline + pan-scroll + drag→`/stage`) |
| **Pipelines + etapas (config)** | `static/crm_pipelines.html` (lista de funis, etapas com reorder drag-drop, forms via `Modal.prompt`/custom) |
| **Lista de oportunidades** | `static/crm_opportunities.html` (DataGrid; ações Abrir/Gerar Proposta/Excluir) |
| **Criação de oportunidade** | `static/crm_opportunity_form.html` (**só `/novo`**; edição é inline no detalhe) |
| Detalhe da oportunidade | `static/crm_opportunity_detail.html` → ver skill `crm-opportunity-page` |
| Repos | `app/db/crm_pipelines_repo.py`, `crm_stages_repo.py`, `crm_opportunities_repo.py` |
| Endpoints | `app/routers/crm.py` (`/pipelines/*`, `/stages/*`, `/opportunities/*`) |
| Schema | `init_v2.sql` — `crm_pipelines`, `crm_stages`, `crm_opportunities` (~118 cols) |

---

## Modelo de dados (o essencial)

```
crm_pipelines(id, nome, descricao, is_default, ativo,
              tipo 'venda'|'pos_venda'|'generico',
              pipeline_pos_venda_id → crm_pipelines)   # link venda→pós-venda
  └─ crm_stages(id, pipeline_id, nome, ordem, probabilidade, cor,
                tipo 'aberto'|'ganho'|'perdido',
                sla_dias, auto_tarefa_assunto/descricao/tipo/prazo_dias, auto_notificar)

crm_opportunities(
   ...,
   pipeline_id  → crm_pipelines,  stage_id  → crm_stages,      # JORNADA DE VENDA (primária)
   pos_venda_pipeline_id → crm_pipelines, pos_venda_stage_id → crm_stages,  # JORNADA DE PÓS-VENDA
   pos_venda_iniciada_em,  status 'aberta'|'ganha'|'perdida', ...)
```

**`cliente_id` é NOT NULL** (toda opp exige Cliente). `_SELECT_FULL` no repo usa **`JOIN crm_pipelines` + `JOIN crm_stages`** (INNER) — uma opp com `pipeline_id`/`stage_id` inválido **não aparece nem na lista nem no kanban**. Os JOINs de pós-venda/cliente/imóvel/usuários são LEFT.

---

## Jornada dupla Venda → Pós-Venda (regra central)

A **MESMA oportunidade** pode viver em duas jornadas simultâneas, sem duplicar:

- **`pipeline_id`/`stage_id`** = jornada de **VENDA** (sempre presente).
- **`pos_venda_pipeline_id`/`pos_venda_stage_id`** = jornada de **PÓS-VENDA** (só depois de promovida).

**Promoção automática** (em `crm_opportunities_repo.mudar_stage`): ao atingir uma etapa `tipo='ganho'` numa pipeline de venda que tem `pipeline_pos_venda_id` setado E ainda não promovida (`pos_venda_pipeline_id IS NULL`), o motor seta `pos_venda_*` = 1ª etapa da pós-venda, registra `crm_stage_history` e dispara webhook `opportunity.pos_venda_iniciada`. A opp **continua na coluna Ganho da venda** e **aparece também** na pós-venda.

**Fase ativa** (`/opportunities/{id}/full`): `pos_venda` se `pos_venda_pipeline_id` setado, senão `venda`. `active_pipeline_id/stage_id` e `stages` são os da fase ativa.

**⚠️ Caso especial (importante): pós-venda como pipeline PRIMÁRIA.** Uma opp pode ser criada/importada DIRETO num funil `pos_venda` (então `pipeline_id` = pós-venda e `pos_venda_pipeline_id` = NULL). O kanban precisa tratar isso (ver bug corrigido abaixo). `mudar_stage` já trata: com `pos_venda_pipeline_id` NULL, a etapa move pela jornada de VENDA (`stage_id`), mesmo a pipeline sendo tipo pós-venda.

---

## Kanban — como agrupa (`GET /opportunities/kanban?pipeline_id=`)

```python
por_pos = pipeline["tipo"] == "pos_venda"
stages = crm_stages_repo.listar_por_pipeline(pipeline_id)      # colunas do board
opps   = crm_opportunities_repo.listar_kanban(pipeline_id, por_pos_venda=por_pos)
for opp in opps:
    # promovida PARA esta pós-venda → coluna = pos_venda_stage_id
    # senão (venda, ou pós-venda PRIMÁRIA) → coluna = stage_id
    sid = opp["pos_venda_stage_id"] if (por_pos and opp["pos_venda_pipeline_id"] == pipeline_id) else opp["stage_id"]
    if sid in by_stage: by_stage[sid].append(opp)     # <-- opps fora das colunas são DESCARTADAS
```

`listar_kanban(pipeline_id, por_pos_venda)`:
- **venda**: `WHERE o.pipeline_id = P` · `ORDER BY s.ordem`.
- **pós-venda**: `WHERE (o.pos_venda_pipeline_id = P OR o.pipeline_id = P)` · `ORDER BY COALESCE(ps.ordem, s.ordem)` — inclui **promovidas** E **primárias**.

**Board = 1 pipeline por vez.** Uma opp aparece só nas pipelines às quais pertence (venda e/ou pós-venda). Frontend (`crm_kanban.html`): `<select>` carrega `/crm/pipelines?ativo=true` (default = `is_default`); trocar de pipeline re-renderiza (aí o scroll reseta, ok). Drag do card → **move otimista no DOM** (card muda de coluna na hora, `refreshColumnStats()` atualiza contador/total/placeholder "Vazio" das colunas afetadas) + `POST /opportunities/{id}/stage {stage_id}` em background (rollback se falhar). **NÃO faz `renderKanban()` no drop** — isso zerava o `scrollLeft` e "pulava" pro início da rolagem horizontal (UX corrigida 2026-07-01). Pan-to-scroll horizontal no board (arrastar área vazia); cards têm drag próprio.

### 🐞 Bug de referência (corrigido 2026-07-01) — "opps somem do kanban"
Antes, a pós-venda filtrava só `pos_venda_pipeline_id = P` e agrupava só por `pos_venda_stage_id`. Opps criadas DIRETO num funil de pós-venda (`pos_venda_pipeline_id` NULL, `pipeline_id = P`) **apareciam na lista mas sumiam do kanban** (filtro devolvia 0 linhas). Caso real: 8 opps em "PÓS-VENDA PHB". Fix = filtro `OR` + resolução de coluna por opp (acima). **Ao mexer no kanban, teste os 3 casos: venda pura, promovida (venda+pós), e pós-venda primária.**

---

## Mudança de etapa (`POST /opportunities/{id}/stage`) — roteamento

`mudar_stage(id, stage_id_to)` decide a jornada pela pipeline da **etapa destino**:
- `is_pos = (opp.pos_venda_pipeline_id IS NOT NULL) AND (stage_destino.pipeline_id == opp.pos_venda_pipeline_id)`.
- **`is_pos`** → move `pos_venda_stage_id`, registra histórico, cria tarefa automática. Não mexe em `status`.
- **senão (venda)** → move `stage_id`; `status` deriva de `stage.tipo` (`ganho`→`ganha`, `perdido`→`perdida`, senão `aberta`); seta `data_fechamento`/`motivo_perda`; cria tarefa automática; **promove** se `ganho` + pipeline com link + ainda não promovida.
- Sempre chama `_criar_tarefa_automatica` (idempotente: não duplica tarefa `auto` PENDENTE da mesma etapa) — é a "Próxima Ação" (card 11 do detalhe).

Webhooks disparados: `opportunity.stage_changed` (+ `won`/`lost` conforme status, + `pos_venda_iniciada` se promoveu).

---

## Pipelines & Stages (config em `/crm/pipelines`)

**Pipelines** (`crm_pipelines_repo`, permissão `crm_pipelines`):
- `criar`/`atualizar` garantem **`is_default` único** (ao marcar um, desmarca os outros).
- `atualizar` protege `nome/is_default/ativo/tipo` com `COALESCE` (não zera se ausente), mas **`descricao` e `pipeline_pos_venda_id` são sobrescritos** (ausente ⇒ NULL). Reenvie-os no PUT.
- `obter_default()` = `is_default=TRUE AND ativo=TRUE`. `DELETE` é hard delete (cuidado: apaga stages em cascade e pode dar FK error se houver opps).

**Stages** (`crm_stages_repo`, permissão `crm_pipelines`):
- `listar_por_pipeline` = **`ORDER BY ordem, id`** (o desempate por `id` evita que editar uma etapa com `ordem` empatada a jogue pro fim — não remover).
- `criar` sem `ordem` (ou 0) → **anexa ao fim** (`MAX(ordem)+1`). `atualizar` é **parcial** (só `_CAMPOS_EDIT`).
- **Reordenação**: `POST /stages/reorder {pipeline_id, stage_ids:[...]}` → grava `ordem = índice+1` na ordem da lista. Frontend faz drag-drop e envia a lista completa de ids.
- Form de etapa tem seção **"Automação da etapa"**: `sla_dias`, `auto_tarefa_tipo/assunto/descricao/prazo_dias`, `auto_notificar` (ver Fase 3 no skill `crm-opportunity-page`).

Endpoints: `GET/POST /pipelines`, `GET /pipelines/default`, `GET/PUT/DELETE /pipelines/{id}` (o GET traz `stages`), `GET/POST /stages`, `PUT/DELETE /stages/{id}`, `POST /stages/reorder`.

---

## Oportunidades — lista e criação

**Lista** (`crm_opportunities.html`, DataGrid, endpoint `/crm/opportunities`): busca (nome/cliente), filtros (`status, pipeline_id, stage_id, proprietario_id, cliente_id`), envelope `{data, meta}`. Ações por linha: **Abrir** (→ detalhe), **Gerar Proposta** (`POST /opportunities/{id}/gerar-proposta`), **Excluir**. Botão "Ver Kanban".

**Criação** (`crm_opportunity_form.html`, só `/crm/opportunities/novo`): campos + **cascata pipeline→stage** (`loadStages()` recarrega `/crm/stages?pipeline_id=` ao trocar pipeline), select de cliente (obrigatório), campanha, etc. `POST /opportunities` exige **`nome, pipeline_id, stage_id, cliente_id`**; seta `criado_por_id/modificado_por_id`, aplica a tarefa automática da etapa inicial (`aplicar_automacao_etapa_atual`) e dispara `opportunity.created`.
> A **edição** de oportunidade é 100% inline no detalhe (`PATCH /opportunities/{id}`). `/crm/opportunities/{id}/editar` é redirect 302 pro detalhe (`pages.py`). `PUT /opportunities/{id}` existe (faz merge `{...atual, ...campos não-nulos}`) mas a UI não usa mais.

---

## Estado em produção (2026-07-01)

4 pipelines: **1 Vendas Imobiliárias** (venda, `is_default`, → pós-venda 2) · **2 PÓS-VENDA THE** (pos_venda) · **3 PÓS-VENDA PHB** (pos_venda) · **4 ATENDIMENTO PHB** (venda, → pós-venda 3). Stages: p1=7, p2=10, p3=19, p4=12. Ver [[project_crm_module]] (Fases 2/3).

---

## Gotchas (checklist ao mexer)

- **Kanban descarta em silêncio** opps cujo `sid` (coluna resolvida) não está entre as stages do pipeline. Se "sumiu do kanban": cheque `pipeline_id`/`stage_id`/`pos_venda_*` da opp vs as stages da pipeline vista (query direta no `habitacao_db`).
- **Pós-venda pode ser pipeline primária** — sempre trate os 2 modos (promovida vs primária) no kanban e em qualquer agregação por etapa.
- **Ordem de rotas** em `crm.py`: literais antes de `/{id}` (`/opportunities/kanban` ANTES de `/opportunities/{id}`; `/pipelines/default` antes de `/pipelines/{id}`). Já está certo — não reordenar por engano.
- **`ORDER BY ordem, id`** nas stages — manter o desempate.
- **`is_default` único** — não criar 2 defaults; `obter_default` pega o 1º.
- **PUT de pipeline** sobrescreve `descricao`/`pipeline_pos_venda_id` — reenvie-os.
- **Permissões**: pipelines E stages usam o recurso **`crm_pipelines`**; oportunidades usam **`crm_opportunities`** (ver skill `rbac-module`).
- **Deploy**: `docker build -f Dockerfile.portal` → `docker stack deploy` → `docker service update --force habitacao_portal` (ver [[feedback_deploy]]). `static/` é baked na imagem — mudança de HTML/JS exige rebuild.

## Como diagnosticar dados (read-only)
```bash
DB=$(docker ps -qf name=habitacao_db)
docker exec -i $DB psql -U habitacao -d habitacao -c \
 "SELECT o.id, o.status, o.pipeline_id, s.pipeline_id AS stage_pl, o.stage_id,
         o.pos_venda_pipeline_id AS pv_pl, o.pos_venda_stage_id AS pv_st
    FROM crm_opportunities o LEFT JOIN crm_stages s ON s.id=o.stage_id ORDER BY o.id;"
```
NUNCA alterar dados reais em teste — só leitura/diagnóstico (ver [[feedback_never_delete]]).
