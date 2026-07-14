---
name: crm-opportunity-page
description: Guia da PÁGINA DE OPORTUNIDADES do CRM (Portal AM Imóveis) — detalhe estilo Salesforce com 13 cards, layout grid-template-areas, edição inline, setinhas verdes e faixa de SLA. Usar SEMPRE que for mexer no detalhe/lista/kanban/criação de oportunidade, adicionar campo/card, ou trabalhar nos pipelines Venda→Pós-Venda.
---

# crm-opportunity-page — a página de Oportunidade do CRM

Documenta como a **página de detalhe da oportunidade** (`/crm/opportunities/{id}`) deve ser. Layout fechado e aprovado pelo usuário em 2026-06-30. Ver também o skill `crm-module` e a memória [[project_crm_module]].

> **Regra de ouro:** a oportunidade é editada **inline no detalhe** (lápis em cada campo). **NÃO existe página de edição separada** — `/crm/opportunities/{id}/editar` é um **redirect 302** para o detalhe (`app/routers/pages.py`). `/crm/opportunities/novo` (criação) continua existindo via `crm_opportunity_form.html`.

---

## Arquivos

| O quê | Onde |
|---|---|
| **Detalhe (13 cards)** | `static/crm_opportunity_detail.html` (~776 linhas, tudo inline: HTML+CSS+JS) |
| Lista | `static/crm_opportunities.html` (DataGrid; ações: Abrir→detalhe, Gerar Proposta, Excluir) |
| Kanban (drag-drop) | `static/crm_kanban.html` (clique no card → detalhe) |
| Criação | `static/crm_opportunity_form.html` (só `/novo`) |
| Repo | `app/db/crm_opportunities_repo.py` (`_SELECT_FULL`, `_CAMPOS`) |
| Endpoints | `app/routers/crm.py` (`/opportunities/*`) |
| Schema | `init_v2.sql` — `crm_opportunities` tem **~118 colunas flat**; `crm_stages.sla_dias` |

---

## Backend

- **`crm_opportunities` é uma tabela WIDE (~118 colunas flat)** — campos adicionados via blocos `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` em `init_v2.sql` (idempotente no startup). NÃO criar tabela satélite por enquanto; segue o padrão flat.
- **`_CAMPOS`** (repo): lista branca das colunas graváveis. Edição inline só funciona para chaves que estão aqui. Ao adicionar coluna nova: adicione em `init_v2.sql` E em `_CAMPOS`.
- **`_SELECT_FULL`**: traz `o.*` + JOINs. Inclui campos do cliente para o Card 1 (`cl.whatsapp1/telefone_fixo/email/estado_civil/nascimento AS cliente_*`), pipeline/stage, e emails dos responsáveis (`*_email`).
- **`GET /opportunities/{id}/full`** devolve: `{...opp, stages, stage_history, entrou_na_etapa_em, propostas_relacionadas, notas, activities}`. `entrou_na_etapa_em` = data do último `crm_stage_history` cujo `stage_id_to` = stage atual (fallback `updated_at`). Cada item de `stages` traz `sla_dias`.
- **`PATCH /opportunities/{id}`** — usado pela edição inline (1 campo por vez). **`POST /opportunities/{id}/stage`** — muda etapa (clique nas setinhas). **Notas**: `GET/POST /opportunities/{id}/notas`, `PUT/DELETE /opportunities/notas/{nota_id}`. **`POST /opportunities/{id}/gerar-proposta`**.

---

## Layout do detalhe (fiel ao mockup "Pós-Venda PHB")

### Header (largura cheia)
Breadcrumb (`Oportunidades › pipeline › nome`) · ícone + **título + badge de status** (aberta→"Em andamento" âmbar, ganha→verde, perdida→vermelho) · subtítulo `empreendimento – unidade • pipeline` · à direita: `Proprietário/Corretor` + avatar e os botões **Alterar Proprietário** + **Mais ações** (stubs por ora). **SEM botão Editar.**

### Gráfico de etapas — setinhas verdes (`.caminho`) — NÃO MEXER NO ESTILO
Chevrons via `clip-path: polygon(...)`. `done` = verde `#22c55e` + `✓`; `current` = verde escuro `#16a34a`; `future` = cinza. `%` da probabilidade embaixo do nome. **O usuário NÃO quer as caixas brancas com check do mockup — manter as setinhas verdes.** Clique numa etapa → confirma → `POST /stage`.

### Faixa de SLA
`Entrou na etapa em: <data>` · `Tempo na etapa: <n> dias` · `SLA da etapa: <sla_dias>` · badge: `NO PRAZO` (verde) / `ATRASADO` (vermelho) / `SLA não definido` (cinza). SLA vem de `crm_stages.sla_dias` (configurável por etapa).

### Abas
`Visão Geral · Atividades (n) · Documentos (n) · Contábil / Fechamento · Histórico (n) · Notas (n)`.

### Corpo — `.opp-body` com **grid-template-areas** (ESSENCIAL)
```css
.opp-body.has-rail { grid-template-columns: minmax(0,1fr) 300px;
  grid-template-areas: "tabs rail" "main rail" "full full"; }   /* Visão Geral */
.opp-body.no-rail  { grid-template-columns: 1fr;
  grid-template-areas: "tabs" "main" "full"; }                  /* outras abas */
```
- **`tabs`** (esq, linha 1) — as abas ficam DENTRO do corpo, na coluna esquerda.
- **`rail`** (dir, abrange linhas 1-2) = `.opp-rail` com **Card 4 (Linha do Tempo)** + **Card 5 (Alertas)**. Começa **no nível das abas** (foi o ajuste-chave: a lateral sobe até as abas).
- **`main`** (esq, linha 2) = Cards **1,2,3 / 6 / 7,8**.
- **`full`** (largura cheia, linha 3) = Cards **9,10,11,12 / 13 / Automações / Legenda**.
- A lateral é curta de propósito → a zona `full` usa a largura toda. **NÃO** usar uma coluna lateral de página inteira (ela colapsava pro fim na largura viewport−navbar — bug já corrigido).
- Breakpoints: `<900px` vira 1 coluna (ordem tabs→rail→main→full); `vg-4` vira 2 colunas `<1000px`; grids `minmax(0,1fr)` para nunca estourar.

### Render flow (JS)
`render()` (faz fetch `/full`) → `renderHead()` (header+setinhas+SLA, handlers via `attachHeadHandlers`) + `renderBody()`. `renderBody()` monta `.opp-body` (rail só se `activeTab==='visao'`) + `renderTabs()` + `<div class="opp-main">mainFor(tab)</div>` + `<div class="opp-full">fullFor(tab)</div>`. Troca de aba e edição inline chamam **`rebuildBody()`** (substitui `.opp-body` sem refetch) → `attachBodyHandlers()`.

---

## Os 13 cards (card → colunas)

| # | Card | Tipo | Campos (coluna no `crm_opportunities`, salvo cliente_* via JOIN) |
|---|---|---|---|
| 1 | Dados do Cliente | **read-only** (`ro()`) | cliente_nome, cliente_cpf, telefone (whatsapp1‖telefone_fixo), cliente_email, cliente_estado_civil, cliente_nascimento + `possui_dependentes` (editável). Link "ver cadastro" → `/clientes/{id}` |
| 2 | Dados do Imóvel | editável | empreendimento_nome (‖imovel_nome), unidade, imovel_endereco, imovel_bairro, imovel_cidade_uf, imovel_cep, imovel_tipo |
| 3 | Dados da Venda | editável | valor_imovel, valor_entrada, venda_forma_entrada, venda_valor_parcela_entrada, venda_data_primeira_parcela, data_contrato, numero_contrato |
| 4 | Linha do Tempo da Etapa | derivado (sidebar) | `entrou_na_etapa_em` + `sla_dias` da etapa (entrou, prazo=entrou+sla, dias restantes) |
| 5 | Alertas e Lembretes | derivado (sidebar) | SLA estourado/cliente parado (de `entrou_na_etapa_em` + `sla_dias` da etapa ativa) + tarefas pendentes/vencidas. Helpers `acoesPendentes()`/`byPrazo()` |
| 6 | PAC | editável 2-col | pac_status, pac_tipo_amortizacao, pac_valor_imovel, pac_prazo_meses, pac_valor_avaliacao, pac_valor_parcela, pac_probabilidade, pac_tipo_analise |
| 7 | Entrada Facilitada | editável 2-col | entrada_facilitada, ef_qtd_parcelas, ef_construtora, ef_valor_parcela, ef_valor_total, ef_observacao |
| 8 | Simulação Banco (Caixa) | editável 2-col | banco_financiador, taxa_juros_anual, tipo_financiamento, valor_total_financiamento, prazo_simulacao_meses, valor_parcela_banco |
| 9 | Equipe e Responsáveis | misto | corretor_imobiliaria_email (ro), proprietario_email (ro), imobiliaria, responsavel_atual_email (ro), construtora_nome, aprovador_email (ro) |
| 10 | Documentos Principais | real | docs de `opp.documentos` (nome + status badge + download se `tem_arquivo`). "Ver todos" → aba Documentos. Subsistema completo: tabela `crm_opp_documentos` |
| 11 | Próxima Ação | derivado | **tarefa automática da etapa ativa** (`activities` com `stage_id===active_stage_id`, `auto`, pendente); badge "auto", destaca vencida, "Marcar como concluída" (`/activities/{id}/concluir`) |
| 12 | Resumo Financeiro | editável | valor_imovel, valor_entrada, valor_total_financiamento, comissao_total, comissao_recebimento_1, comissao_restante, comissao_previsao_recebimento, comissao_status |
| 13 | Contábil / Fechamento | editável 2-col + anexos | campos contábeis (contabil_mes_fechamento, comissao_*, numero_contrato, cliente ro, empreendimento, endereco) + **Anexos Contábeis** = `anexosContabeis()` lista `opp.documentos` (mesmo subsistema; download via `dl-doc`, "+ Adicionar documento" via `add-anexo` upload rápido) + botão **"Gerar Relatório"** (`gerar-relatorio` → modal de filtros Mês/Ano/Empreendimento/Status comissão → baixa XLSX de `GET /crm/relatorio/contabil`, gerado por `excel_service.gerar_xlsx_relatorio_contabil` a partir de `crm_opportunities_repo.relatorio_contabil(filtros)`) |

Footer (zona `full`): **Automações e Controles** (5 colunas descritivas, "a configurar") + **Legenda de cores das etapas**.

---

## Automação por etapa + SLA (Fase 3) — genérico p/ qualquer pipeline
Cada `crm_stages` configura (no form de etapa em `/crm/pipelines`): **`sla_dias`** (prazo da etapa) e a **tarefa automática** (`auto_tarefa_assunto/descricao/tipo/prazo_dias`, `auto_notificar`). `crm_activities` tem `stage_id` + `auto`.

- **Motor** (`crm_opportunities_repo._criar_tarefa_automatica`): ao ENTRAR numa etapa, cria a "próxima ação" (activity pendente, responsável=proprietário, prazo=agora+(`auto_tarefa_prazo_dias`‖`sla_dias`‖0) dias). Chamado nas 3 entradas de `mudar_stage` (venda/pós-venda/promoção) e em `aplicar_automacao_etapa_atual(opp_id)` (no POST /opportunities, p/ a etapa inicial). **Idempotente** (não duplica tarefa auto PENDENTE da mesma etapa).
- **Card 11** mostra essa tarefa (da etapa ativa). **Card 5** alerta SLA estourado/cliente parado + tarefas vencidas. A **faixa de SLA** e o **Card 4** usam `sla_dias` da etapa ativa + `entrou_na_etapa_em`.
- "Notificação no CRM / e-mail" do mockup = via webhook `opportunity.stage_changed` (+ `pos_venda_iniciada`) — integração externa (Make/n8n) faz o e-mail. Um sistema de notificações in-app (sino) seria fase futura.

## Documentos (card 10 + aba Documentos) — upload + checklist
Tabela **`crm_opp_documentos`** (opportunity_id, nome, status `pendente|enviado|assinado|concluido`, `arquivo` BYTEA nullable, nome_arquivo, content_type, tamanho, observacao, criado_por_id). Repo `crm_opp_documentos_repo` (`_META` qualificado com `d.` — sem o BYTEA; `obter_arquivo` traz os bytes).

Endpoints (em `crm.py`): `GET/POST /opportunities/{id}/documentos` (POST é **multipart**: nome/status/observacao + `arquivo` opcional), `PUT /opportunities/documentos/{doc_id}` (status/nome JSON), `POST /opportunities/documentos/{doc_id}/arquivo` (multipart, anexa/atualiza arquivo; pendente→enviado), `GET /opportunities/documentos/{doc_id}/arquivo` (download), `DELETE`. `/full` devolve `documentos`.

Frontend: upload via **`api.upload(path, FormData)`**, download via **`api.downloadFile(path, nome)`** (Bearer não vai em `<a href>`). Aba Documentos = tabela (nome/status-select/arquivo/excluir) + form "Adicionar" (datalist `DOC_SUGESTOES`) + botão "Checklist padrão" (`DOC_CHECKLIST_PADRAO`). Handlers em `attachDocHandlers()` (chamado por `attachBodyHandlers`). Genérico p/ qualquer pipeline.

## ⚠️ Armadilha crítica: `cardHead` vs `cardOpen`

Cards com **corpo de 2 colunas** (`<div class="vgcard-body two">`) — os cards **6, 7, 8, 13** — DEVEM usar **`cardHead()`** (só cabeçalho, sem abrir body), porque eles abrem o próprio body.

- `cardOpen(num, icon, title, headExtra)` = cabeçalho **+ `<div class="vgcard-body">` já aberto**. Use para cards de 1 coluna (1,2,3,9,10,11,12) **fechando com `cardClose()`** (`</div></div>`).
- `cardHead(num, icon, title, headExtra)` = **só** `<div class="vgcard"><div class="vgcard-head">…</div>`. Use para os cards `.two` (6,7,8,13), que então fazem `'<div class="vgcard-body two">' + campos + '</div></div>'`.

**Se usar `cardOpen` num card `.two`, o `.vgcard` fica SEM FECHAR** → o HTML malformado engole os cards seguintes e cria um buraco (foi exatamente o bug dos cards 7 e 8 sumindo). **Sempre validar o balanço de `<div>` após mexer nos cards** (harness: extrair as funções e contar `<div`/`</div>` — devem bater).

---

## Helpers de campo (no detail)

- `ro(label, value)` — campo **read-only** (sem lápis). Use para dados do cliente e emails de responsáveis.
- `fld(key, label, value, type)` — campo **editável** (`data-key`/`data-type`); `type` ∈ `text|number|money|date|bool`. O display já vem formatado (`fmtMoney`, `fmtDate`); a edição usa `opp[key]` cru.
- `fldBool(key, label, value)` — booleano (✓ Sim / ✗ Não), editável via select.
- Edição: `inlineEdit()` troca o `.field-value` por input → ao salvar chama `patch({key:val})` → `PATCH /opportunities/{id}` → `Object.assign(opp,...)` → `rebuildBody()`. `Esc` cancela.

---

## Como adicionar um campo novo a um card

1. `init_v2.sql`: `ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS <col> <tipo>;` (no bloco `DO $$` existente).
2. `app/db/crm_opportunities_repo.py`: adicione `"<col>"` em `_CAMPOS`.
3. (Se vier de JOIN, ex. cliente) adicione o alias em `_SELECT_FULL`.
4. No card certo em `crm_opportunity_detail.html`: `fld('<col>', 'Label', <valor formatado>, '<type>')` (ou `ro()` se read-only).
5. Build + `docker service update --force habitacao_portal` (ver [[feedback_deploy]]). O startup aplica a coluna.
6. Teste: PATCH no-op (valor atual) deve dar 200; nunca alterar dados reais (ver [[feedback_never_delete]]).

## Como adicionar um card novo
Crie `cardNNome()` (use `cardOpen`+`cardClose` para 1 coluna, ou `cardHead`+body `.two` para 2 colunas) e inclua em `mainFor('visao')` ou `fullFor('visao')` na linha (`vg-3`/`vg-2`/`vg-4`/full) que fizer sentido.

---

## Fase ativa (Venda → Pós-Venda) — IMPLEMENTADO
Pipelines vinculados (`crm_pipelines.tipo` + `pipeline_pos_venda_id`): ao ganhar na pipeline de VENDA, a **MESMA oportunidade** entra na pós-venda vinculada (sem duplicar, sem sumir da venda) e passa a seguir as etapas da pós-venda. A página de detalhe é a MESMA.

- `crm_opportunities` mantém `pipeline_id`/`stage_id` (jornada de VENDA) e ganhou `pos_venda_pipeline_id`/`pos_venda_stage_id`/`pos_venda_iniciada_em`.
- **`/full` resolve a FASE ATIVA** e devolve: `fase_ativa` ('venda'|'pos_venda'), `active_pipeline_id/nome`, `active_stage_id/nome`, e `stages` = etapas da **pipeline ativa**.
- No detalhe: helper **`activeStageId()`** = `opp.active_stage_id ?? opp.stage_id`. `renderCaminho`/`renderSlaFaixa` usam `activeStageId()` + `opp.stages` (já são da fase ativa). Breadcrumb/subtítulo usam `opp.active_pipeline_nome`. Header mostra chip "Pós-venda" + linha "Venda ganha → em pós-venda desde DD/MM" quando `fase_ativa==='pos_venda'`.
- **Mudança de etapa**: o clique nas setinhas faz `POST /opportunities/{id}/stage` com um `stage_id` da pipeline ativa; o backend (`mudar_stage`) detecta a qual jornada a etapa pertence e atualiza `stage_id` (venda) OU `pos_venda_stage_id` (pós-venda). Promoção automática ao ganhar na venda (etapa tipo `ganho` + pipeline com link). Detalhes do modelo em [[project_crm_module]].
