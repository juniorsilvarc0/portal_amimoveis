"""Router unificado do CRM. Todos os endpoints sob /api/v1/crm/*.

Recursos:
  /pipelines      — funis configuráveis
  /stages         — etapas de cada funil
  /campaigns      — campanhas/origem de leads
  /leads          — prospects (com convert → cliente)
  /opportunities  — negociações (com mudança de stage, kanban, gerar proposta)
  /activities     — tarefas, ligações, reuniões, notas
  /webhooks       — notificações de saída
  /import/leads   — importação em lote de CSV
  /dashboard      — métricas agregadas
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import (
    crm_pipelines_repo,
    crm_stages_repo,
    crm_campaigns_repo,
    crm_leads_repo,
    crm_opportunities_repo,
    crm_opp_notas_repo,
    crm_opp_documentos_repo,
    crm_activities_repo,
    crm_webhooks_repo,
    clientes_repo,
    propostas_repo,
    imoveis_repo,
    imovel_unidades_repo,
)
from app.db.connection import cursor as db_cursor
from app.services import webhook_dispatcher, crm_importer

router = APIRouter(prefix="/api/v1/crm", tags=["CRM"])


def _paged(rows, total, page, per_page):
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

@router.get("/pipelines")
async def listar_pipelines(ativo: Optional[bool] = None,
                            user: dict = Depends(require_permission("crm_pipelines", "ver"))):
    return crm_pipelines_repo.listar(ativo=ativo)


@router.get("/pipelines/default")
async def pipeline_default(user: dict = Depends(require_permission("crm_pipelines", "ver"))):
    p = crm_pipelines_repo.obter_default()
    if not p:
        raise HTTPException(404, "Nenhum pipeline padrão configurado.")
    return p


@router.get("/pipelines/{id}")
async def obter_pipeline(id: int, user: dict = Depends(require_permission("crm_pipelines", "ver"))):
    p = crm_pipelines_repo.obter(id)
    if not p:
        raise HTTPException(404, "Pipeline não encontrado.")
    p["stages"] = crm_stages_repo.listar_por_pipeline(id)
    return p


@router.post("/pipelines", status_code=201)
async def criar_pipeline(body: dict, user: dict = Depends(require_permission("crm_pipelines", "criar"))):
    if not body.get("nome"):
        raise HTTPException(422, "nome obrigatório")
    pid = crm_pipelines_repo.criar(body)
    return crm_pipelines_repo.obter(pid)


@router.put("/pipelines/{id}")
async def atualizar_pipeline(id: int, body: dict, user: dict = Depends(require_permission("crm_pipelines", "editar"))):
    if not crm_pipelines_repo.atualizar(id, body):
        raise HTTPException(404, "Pipeline não encontrado.")
    return crm_pipelines_repo.obter(id)


@router.delete("/pipelines/{id}")
async def deletar_pipeline(id: int, user: dict = Depends(require_permission("crm_pipelines", "excluir"))):
    if not crm_pipelines_repo.deletar(id):
        raise HTTPException(404, "Pipeline não encontrado.")
    return {"mensagem": "Pipeline excluído."}


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

@router.get("/stages")
async def listar_stages(pipeline_id: Optional[int] = None,
                         user: dict = Depends(require_permission("crm_pipelines", "ver"))):
    if pipeline_id:
        return crm_stages_repo.listar_por_pipeline(pipeline_id)
    return crm_stages_repo.listar_todas()


@router.post("/stages", status_code=201)
async def criar_stage(body: dict, user: dict = Depends(require_permission("crm_pipelines", "criar"))):
    if not body.get("pipeline_id") or not body.get("nome"):
        raise HTTPException(422, "pipeline_id e nome obrigatórios")
    sid = crm_stages_repo.criar(body)
    return crm_stages_repo.obter(sid)


@router.put("/stages/{id}")
async def atualizar_stage(id: int, body: dict, user: dict = Depends(require_permission("crm_pipelines", "editar"))):
    if not crm_stages_repo.atualizar(id, body):
        raise HTTPException(404, "Stage não encontrada.")
    return crm_stages_repo.obter(id)


@router.delete("/stages/{id}")
async def deletar_stage(id: int, user: dict = Depends(require_permission("crm_pipelines", "excluir"))):
    if not crm_stages_repo.deletar(id):
        raise HTTPException(404, "Stage não encontrada.")
    return {"mensagem": "Stage excluída."}


@router.post("/stages/reorder")
async def reordenar_stages(body: dict, user: dict = Depends(require_permission("crm_pipelines", "editar"))):
    pipeline_id = body.get("pipeline_id")
    ids = body.get("stage_ids", [])
    if not pipeline_id or not isinstance(ids, list):
        raise HTTPException(422, "pipeline_id e stage_ids (lista) obrigatórios")
    crm_stages_repo.reordenar(pipeline_id, ids)
    return crm_stages_repo.listar_por_pipeline(pipeline_id)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@router.get("/campaigns")
async def listar_campaigns(page: int = 1, per_page: int = 25,
                            search: Optional[str] = None,
                            ativo: Optional[bool] = None,
                            user: dict = Depends(require_permission("crm_campaigns", "ver"))):
    rows, total = crm_campaigns_repo.listar(page=page, per_page=per_page,
                                              search=search, ativo=ativo)
    return _paged(rows, total, page, per_page)


@router.get("/campaigns/{id}")
async def obter_campaign(id: int, user: dict = Depends(require_permission("crm_campaigns", "ver"))):
    c = crm_campaigns_repo.obter(id)
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    return c


@router.post("/campaigns", status_code=201)
async def criar_campaign(body: dict, user: dict = Depends(require_permission("crm_campaigns", "criar"))):
    cid = crm_campaigns_repo.criar(body)
    return crm_campaigns_repo.obter(cid)


@router.put("/campaigns/{id}")
async def atualizar_campaign(id: int, body: dict, user: dict = Depends(require_permission("crm_campaigns", "editar"))):
    if not crm_campaigns_repo.atualizar(id, body):
        raise HTTPException(404, "Campanha não encontrada.")
    return crm_campaigns_repo.obter(id)


@router.delete("/campaigns/{id}")
async def deletar_campaign(id: int, user: dict = Depends(require_permission("crm_campaigns", "excluir"))):
    if not crm_campaigns_repo.deletar(id):
        raise HTTPException(404, "Campanha não encontrada.")
    return {"mensagem": "Campanha excluída."}


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@router.get("/leads")
async def listar_leads(page: int = 1, per_page: int = 25,
                        search: Optional[str] = None,
                        status: Optional[str] = None,
                        campaign_id: Optional[int] = None,
                        proprietario_id: Optional[int] = None,
                        origem: Optional[str] = None,
                        user: dict = Depends(require_permission("crm_leads", "ver"))):
    rows, total = crm_leads_repo.listar(
        page=page, per_page=per_page, search=search,
        status=status, campaign_id=campaign_id,
        proprietario_id=proprietario_id, origem=origem,
    )
    return _paged(rows, total, page, per_page)


@router.get("/leads/lookup-cliente")
async def lookup_cliente_por_cpf(cpf_cnpj: str,
                                   user: dict = Depends(get_current_user)):
    """Helper UI: dado um CPF/CNPJ, retorna o cliente existente (se houver)
    para mostrar no form de Lead que o lead será vinculado a este cliente.

    IMPORTANTE: precisa estar declarado ANTES de `/leads/{id}` no router pra
    não ser interceptado como ``id='lookup-cliente'``.
    """
    cli = crm_leads_repo.buscar_cliente_por_cpf(cpf_cnpj)
    if not cli:
        return {"cliente": None}
    # Buscar histórico de leads desse cliente
    leads_anteriores = crm_leads_repo.listar_por_cliente(cli["id"])
    return {
        "cliente": cli,
        "leads_anteriores": len(leads_anteriores),
        "ja_foi_cliente": True,
    }


@router.get("/leads/{id}")
async def obter_lead(id: int, user: dict = Depends(require_permission("crm_leads", "ver"))):
    lead = crm_leads_repo.obter(id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
    lead["activities"] = crm_activities_repo.timeline("lead", id)
    return lead


@router.post("/leads", status_code=201)
async def criar_lead(body: dict, user: dict = Depends(require_permission("crm_leads", "criar"))):
    """Cria lead. Se CPF/CNPJ corresponder a cliente existente, auto-vincula.

    Retorna o lead criado. Se ``cliente_id`` foi preenchido automaticamente
    pelo lookup de CPF, o campo ``cliente_nome`` no retorno informa o vínculo.
    """
    if not body.get("nome"):
        raise HTTPException(422, "nome é obrigatório")
    lid = crm_leads_repo.criar(body)
    lead = crm_leads_repo.obter(lid)
    webhook_dispatcher.disparar("lead.created", lead)
    return lead


@router.put("/leads/{id}")
async def atualizar_lead(id: int, body: dict, user: dict = Depends(require_permission("crm_leads", "editar"))):
    atual = crm_leads_repo.obter(id)
    if not atual:
        raise HTTPException(404, "Lead não encontrado.")
    # Mescla com o registro atual: campos não enviados (ou enviados nulos) são
    # preservados — protege cliente_id auto-vinculado, data_conversao, etc.
    merged = {**atual, **{k: v for k, v in body.items() if v is not None}}
    crm_leads_repo.atualizar(id, merged)
    lead = crm_leads_repo.obter(id)
    webhook_dispatcher.disparar("lead.updated", lead)
    return lead


@router.delete("/leads/{id}")
async def deletar_lead(id: int, user: dict = Depends(require_permission("crm_leads", "excluir"))):
    lead = crm_leads_repo.obter(id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
    crm_leads_repo.deletar(id)
    webhook_dispatcher.disparar("lead.deleted", {"id": id})
    return {"mensagem": "Lead excluído."}


@router.post("/leads/{id}/convert")
async def converter_lead(id: int, body: Optional[dict] = None,
                          user: dict = Depends(require_permission("crm_leads", "editar"))):
    """Converte lead em cliente; opcionalmente cria uma opportunity.

    Idempotente: se o lead já tem ``cliente_id`` (ex.: auto-vinculado por CPF),
    NÃO cria cliente duplicado — apenas atualiza status e cria opportunity.
    """
    body = body or {}
    lead = crm_leads_repo.obter(id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")

    # 1) Cliente: usar existente se já vinculado, senão criar/upsert
    cliente_id = lead.get("cliente_id")
    if not cliente_id:
        cpf = (lead.get("cpf_cnpj") or "").replace(".", "").replace("-", "").replace("/", "").strip()
        if cpf and len(cpf) >= 11:
            cliente_id = clientes_repo.upsert_por_cpf({
                "cpf": cpf,
                "nome": lead.get("nome"),
                "email": lead.get("email"),
                "whatsapp1": lead.get("whatsapp") or lead.get("telefone"),
                "cidade_id": lead.get("cidade_id"),
            })
        else:
            # Cliente sem CPF válido (CPF pendente)
            cliente_id = clientes_repo.criar({
                "nome": lead.get("nome"),
                "email": lead.get("email"),
                "whatsapp1": lead.get("whatsapp") or lead.get("telefone"),
                "cidade_id": lead.get("cidade_id"),
                "cpf_pendente": True,
            })

    crm_leads_repo.marcar_convertido(id, cliente_id)

    resultado = {"lead_id": id, "cliente_id": cliente_id, "opportunity_id": None}

    # 2) Opcional: cria opportunity
    if body.get("criar_opportunity", True):
        pipeline_id = body.get("pipeline_id")
        if not pipeline_id:
            default = crm_pipelines_repo.obter_default()
            if not default:
                raise HTTPException(400, "Nenhum pipeline padrão. Crie um pipeline antes de converter.")
            pipeline_id = default["id"]

        stage_id = body.get("stage_id")
        if not stage_id:
            stages = crm_stages_repo.listar_por_pipeline(pipeline_id)
            if not stages:
                raise HTTPException(400, "Pipeline sem stages configuradas.")
            stage_id = stages[0]["id"]

        opp_id = crm_opportunities_repo.criar({
            "nome": body.get("opportunity_nome") or f"Negociação {lead.get('nome')}",
            "cliente_id": cliente_id,
            "lead_id": id,
            "pipeline_id": pipeline_id,
            "stage_id": stage_id,
            "valor": body.get("opportunity_valor") or lead.get("valor_estimado"),
            "imovel_id": lead.get("imovel_interesse_id"),
            "campaign_id": lead.get("campaign_id"),
            "proprietario_id": lead.get("proprietario_id"),
        })
        resultado["opportunity_id"] = opp_id

    lead_final = crm_leads_repo.obter(id)
    webhook_dispatcher.disparar("lead.converted", {**lead_final, **resultado})
    return resultado


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

@router.get("/opportunities")
async def listar_opportunities(page: int = 1, per_page: int = 25,
                                search: Optional[str] = None,
                                status: Optional[str] = None,
                                pipeline_id: Optional[int] = None,
                                stage_id: Optional[int] = None,
                                proprietario_id: Optional[int] = None,
                                cliente_id: Optional[int] = None,
                                user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    rows, total = crm_opportunities_repo.listar(
        page=page, per_page=per_page, search=search,
        status=status, pipeline_id=pipeline_id, stage_id=stage_id,
        proprietario_id=proprietario_id, cliente_id=cliente_id,
    )
    return _paged(rows, total, page, per_page)


@router.get("/opportunities/kanban")
async def opportunities_kanban(pipeline_id: Optional[int] = None,
                                user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    """Retorna stages + oportunidades agrupadas para visualização Kanban."""
    if not pipeline_id:
        default = crm_pipelines_repo.obter_default()
        if not default:
            return {"pipeline": None, "columns": []}
        pipeline_id = default["id"]

    pipeline = crm_pipelines_repo.obter(pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline não encontrado.")
    # Pipeline de pós-venda agrupa pela etapa de pós-venda (pos_venda_stage_id),
    # mas opps cuja pipeline PRIMÁRIA já é esta pós-venda (pos_venda_pipeline_id
    # NULL) são agrupadas pela stage_id normal.
    por_pos = pipeline.get("tipo") == "pos_venda"
    stages = crm_stages_repo.listar_por_pipeline(pipeline_id)
    opportunities = crm_opportunities_repo.listar_kanban(pipeline_id, por_pos_venda=por_pos)

    by_stage = {s["id"]: {"stage": s, "opportunities": [], "total_valor": 0.0}
                for s in stages}
    for opp in opportunities:
        if por_pos and opp.get("pos_venda_pipeline_id") == pipeline_id:
            sid = opp.get("pos_venda_stage_id")   # opp promovida para esta pós-venda
        else:
            sid = opp.get("stage_id")             # pipeline primária (venda ou pós-venda direta)
        if sid in by_stage:
            by_stage[sid]["opportunities"].append(opp)
            by_stage[sid]["total_valor"] += float(opp.get("valor") or 0)

    columns = [by_stage[s["id"]] for s in stages]
    return {"pipeline": pipeline, "columns": columns}


@router.get("/opportunities/{id}")
async def obter_opportunity(id: int, user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    opp = crm_opportunities_repo.obter(id)
    if not opp:
        raise HTTPException(404, "Oportunidade não encontrada.")
    opp["activities"] = crm_activities_repo.timeline("opportunity", id)
    return opp


def _preencher_snapshot_imovel(body: dict, imovel: dict | None, unidade: dict | None) -> None:
    """Copia dados do imóvel/unidade para os campos snapshot da oportunidade (Card 2).

    Só preenche o que o body NÃO trouxe — o usuário sempre pode sobrepor. A oportunidade
    guarda a CÓPIA (preserva histórico), não um espelho ao vivo do imóvel.
    """
    def preenche(chave, valor):
        if valor is not None and valor != "" and not body.get(chave):
            body[chave] = valor

    if imovel:
        preenche("empreendimento_nome", imovel.get("nome"))
        preenche("imovel_endereco", imovel.get("endereco"))
        preenche("imovel_bairro", imovel.get("bairro"))
        cidade = imovel.get("cidade_nome")
        if cidade and imovel.get("cidade_uf"):
            cidade = f"{cidade}/{imovel['cidade_uf']}"
        preenche("imovel_cidade_uf", cidade)
        preenche("imovel_cep", imovel.get("cep"))
        preenche("imovel_tipo", imovel.get("tipo"))
    if unidade:
        preenche("unidade", unidade.get("identificador"))
        preenche("valor_imovel", unidade.get("valor"))
        preenche("valor", unidade.get("valor"))


@router.post("/opportunities", status_code=201)
async def criar_opportunity(body: dict, user: dict = Depends(require_permission("crm_opportunities", "criar"))):
    """Cria opportunity. Cliente é obrigatório (novo modelo: Cliente é central).

    ``lead_id`` é opcional — usado pra registrar de qual Lead a opportunity
    se originou (atribuição de origem/campanha).

    Se vier ``unidade_id``: recusa duplicação (uma opp não-perdida por unidade),
    deriva o ``imovel_id`` e AUTO-PREENCHE o snapshot do Card 2 a partir do imóvel/unidade.
    """
    if not body.get("nome") or not body.get("pipeline_id") or not body.get("stage_id"):
        raise HTTPException(422, "nome, pipeline_id e stage_id são obrigatórios")
    if not body.get("cliente_id"):
        raise HTTPException(422, "cliente_id é obrigatório (Cliente é central no novo modelo).")

    unidade_id = body.get("unidade_id")
    if unidade_id:
        ocupada = crm_opportunities_repo.oportunidade_ativa_da_unidade(unidade_id)
        if ocupada:
            raise HTTPException(
                409,
                f"A unidade já tem uma oportunidade ativa: “{ocupada['nome']}” "
                f"(etapa {ocupada.get('stage_nome') or '—'}). Conclua-a ou marque como "
                f"perdida antes de criar outra para a mesma unidade.",
            )
        unidade = imovel_unidades_repo.obter(unidade_id)
        if not unidade:
            raise HTTPException(422, "Unidade informada não existe.")
        if not body.get("imovel_id"):
            body["imovel_id"] = unidade["imovel_id"]
        _preencher_snapshot_imovel(body, imoveis_repo.obter(unidade["imovel_id"]), unidade)

    body["criado_por_id"] = user.get("id")
    body["modificado_por_id"] = user.get("id")
    try:
        oid = crm_opportunities_repo.criar(body)
    except Exception as e:
        # Rede de segurança do banco (índice único parcial), caso duas criações corram juntas.
        if "crm_opp_unidade_ativa_uniq" in str(e) or "unique" in str(e).lower():
            raise HTTPException(409, "A unidade acabou de receber uma oportunidade ativa. Recarregue e tente outra unidade.")
        raise
    if unidade_id:
        imovel_unidades_repo.definir_status(unidade_id, "reservada")
    crm_opportunities_repo.aplicar_automacao_etapa_atual(oid)  # tarefa automática da etapa inicial
    opp = crm_opportunities_repo.obter(oid)
    webhook_dispatcher.disparar("opportunity.created", opp)
    return opp


@router.put("/opportunities/{id}")
async def atualizar_opportunity(id: int, body: dict, user: dict = Depends(require_permission("crm_opportunities", "editar"))):
    atual = crm_opportunities_repo.obter(id)
    if not atual:
        raise HTTPException(404, "Oportunidade não encontrada.")
    # Garantir presença de campos obrigatórios para o UPDATE
    merged = {**atual, **{k: v for k, v in body.items() if v is not None}}
    crm_opportunities_repo.atualizar(id, merged)
    opp = crm_opportunities_repo.obter(id)
    webhook_dispatcher.disparar("opportunity.updated", opp)
    return opp


@router.post("/opportunities/{id}/stage")
async def mudar_stage(id: int, body: dict, user: dict = Depends(require_permission("crm_opportunities", "editar"))):
    stage_id = body.get("stage_id")
    if not stage_id:
        raise HTTPException(422, "stage_id obrigatório")
    result = crm_opportunities_repo.mudar_stage(
        id, stage_id, usuario_id=user.get("id"), motivo=body.get("motivo"),
    )
    if not result:
        raise HTTPException(404, "Oportunidade ou stage não encontrada.")
    opp = crm_opportunities_repo.obter(id)
    # Sincroniza o status da unidade com o ciclo da oportunidade: ganha -> vendida,
    # perdida -> disponivel (liberada), demais -> reservada.
    if opp.get("unidade_id"):
        novo_status_unidade = {"ganha": "vendida", "perdida": "disponivel"}.get(opp.get("status"), "reservada")
        imovel_unidades_repo.definir_status(opp["unidade_id"], novo_status_unidade)
    webhook_dispatcher.disparar("opportunity.stage_changed", opp)
    if opp.get("status") == "ganha":
        webhook_dispatcher.disparar("opportunity.won", opp)
    elif opp.get("status") == "perdida":
        webhook_dispatcher.disparar("opportunity.lost", opp)
    if isinstance(result, dict) and result.get("promovida"):
        webhook_dispatcher.disparar("opportunity.pos_venda_iniciada", opp)
    return opp


@router.delete("/opportunities/{id}")
async def deletar_opportunity(id: int, user: dict = Depends(require_permission("crm_opportunities", "excluir"))):
    if not crm_opportunities_repo.obter(id):
        raise HTTPException(404, "Oportunidade não encontrada.")
    crm_opportunities_repo.deletar(id)
    webhook_dispatcher.disparar("opportunity.deleted", {"id": id})
    return {"mensagem": "Oportunidade excluída."}


@router.get("/opportunities/{id}/full")
async def obter_opportunity_full(id: int, user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    """Retorna oportunidade + tudo relacionado (sidebar Salesforce-like)."""
    opp = crm_opportunities_repo.obter(id)
    if not opp:
        raise HTTPException(404, "Oportunidade não encontrada.")

    # Fase ativa: pós-venda se já promovida, senão venda.
    fase_ativa = "pos_venda" if opp.get("pos_venda_pipeline_id") else "venda"
    active_pipeline_id = opp.get("pos_venda_pipeline_id") or opp["pipeline_id"]
    active_stage_id = opp.get("pos_venda_stage_id") or opp.get("stage_id")
    active_pipeline_nome = opp.get("pos_venda_pipeline_nome") if fase_ativa == "pos_venda" else opp.get("pipeline_nome")
    active_stage_nome = opp.get("pos_venda_stage_nome") if fase_ativa == "pos_venda" else opp.get("stage_nome")

    # Pipeline + stages (para barra de progresso) — da FASE ATIVA
    stages = crm_stages_repo.listar_por_pipeline(active_pipeline_id)

    # Stage history
    with db_cursor() as cur:
        cur.execute("""
            SELECT h.*, s.nome AS stage_nome, s.probabilidade,
                   u.email AS usuario_email
              FROM crm_stage_history h
              JOIN crm_stages s ON s.id = h.stage_id_to
              LEFT JOIN usuarios u ON u.id = h.usuario_id
             WHERE h.opportunity_id = %s
             ORDER BY h.created_at DESC
        """, (id,))
        stage_history = [dict(r) for r in cur.fetchall()]

    # Quando a oportunidade entrou na etapa ATIVA (para a faixa de SLA)
    entrou_na_etapa_em = None
    for h in stage_history:
        if h.get("stage_id_to") == active_stage_id:
            entrou_na_etapa_em = h.get("created_at")
            break
    if entrou_na_etapa_em is None:
        entrou_na_etapa_em = opp.get("updated_at") or opp.get("created_at")

    # Propostas relacionadas (via cliente_id)
    propostas_rel = []
    if opp.get("cliente_id"):
        try:
            with db_cursor() as cur:
                cur.execute("""
                    SELECT id, empreendimento, unidade, valor_total, created_at,
                           (id = %s) AS proposta_vigente
                      FROM propostas
                     WHERE cliente_id = %s
                     ORDER BY created_at DESC
                     LIMIT 20
                """, (opp.get("proposta_id"), opp["cliente_id"]))
                propostas_rel = [dict(r) for r in cur.fetchall()]
        except Exception:
            pass

    # Notas
    notas = crm_opp_notas_repo.listar_por_opportunity(id)

    # Documentos (card 10 + aba Documentos)
    documentos = crm_opp_documentos_repo.listar_por_opportunity(id)

    # Activities (timeline)
    activities = crm_activities_repo.timeline("opportunity", id)

    return {
        **opp,
        "fase_ativa": fase_ativa,
        "active_pipeline_id": active_pipeline_id,
        "active_stage_id": active_stage_id,
        "active_pipeline_nome": active_pipeline_nome,
        "active_stage_nome": active_stage_nome,
        "stages": stages,
        "stage_history": stage_history,
        "entrou_na_etapa_em": entrou_na_etapa_em,
        "propostas_relacionadas": propostas_rel,
        "notas": notas,
        "documentos": documentos,
        "activities": activities,
    }


@router.get("/opportunities/{id}/notas")
async def listar_notas_opp(id: int, user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    return crm_opp_notas_repo.listar_por_opportunity(id)


@router.post("/opportunities/{id}/notas", status_code=201)
async def criar_nota_opp(id: int, body: dict, user: dict = Depends(require_permission("crm_opportunities", "criar"))):
    if not body.get("corpo"):
        raise HTTPException(422, "corpo é obrigatório")
    if not crm_opportunities_repo.obter(id):
        raise HTTPException(404, "Oportunidade não encontrada.")
    nota_id = crm_opp_notas_repo.criar({
        "opportunity_id": id,
        "titulo": body.get("titulo"),
        "corpo": body["corpo"],
        "criado_por_id": user.get("id"),
    })
    return crm_opp_notas_repo.obter(nota_id)


@router.put("/opportunities/notas/{nota_id}")
async def atualizar_nota_opp(nota_id: int, body: dict,
                              user: dict = Depends(require_permission("crm_opportunities", "editar"))):
    if not crm_opp_notas_repo.atualizar(nota_id, body):
        raise HTTPException(404, "Nota não encontrada.")
    return crm_opp_notas_repo.obter(nota_id)


@router.delete("/opportunities/notas/{nota_id}")
async def deletar_nota_opp(nota_id: int, user: dict = Depends(require_permission("crm_opportunities", "excluir"))):
    if not crm_opp_notas_repo.deletar(nota_id):
        raise HTTPException(404, "Nota não encontrada.")
    return {"mensagem": "Nota excluída."}


# ---- Documentos da oportunidade (card 10 + aba Documentos) ----
DOC_MAX_SIZE = 15 * 1024 * 1024  # 15 MB


@router.get("/opportunities/{id}/documentos")
async def listar_documentos_opp(id: int, user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    return crm_opp_documentos_repo.listar_por_opportunity(id)


@router.post("/opportunities/{id}/documentos", status_code=201)
async def criar_documento_opp(
    id: int,
    nome: str = Form(...),
    status: str = Form("pendente"),
    observacao: str = Form(None),
    arquivo: UploadFile = File(None),
    user: dict = Depends(require_permission("crm_opportunities", "editar")),
):
    """Cria um item de documento (com ou sem arquivo). Multipart."""
    if not crm_opportunities_repo.obter(id):
        raise HTTPException(404, "Oportunidade não encontrada.")
    dados = nome_arq = ctype = None
    if arquivo is not None and arquivo.filename:
        dados = await arquivo.read()
        if len(dados) > DOC_MAX_SIZE:
            raise HTTPException(422, "Arquivo excede 15 MB.")
        nome_arq = arquivo.filename
        ctype = arquivo.content_type
    doc_id = crm_opp_documentos_repo.criar(
        id, nome.strip(), status=status or "pendente", arquivo=dados,
        nome_arquivo=nome_arq, content_type=ctype, observacao=observacao,
        criado_por_id=user.get("id"),
    )
    return crm_opp_documentos_repo.obter(doc_id)


@router.put("/opportunities/documentos/{doc_id}")
async def atualizar_documento_opp(doc_id: int, body: dict, user: dict = Depends(require_permission("crm_opportunities", "editar"))):
    if not crm_opp_documentos_repo.atualizar(doc_id, body):
        raise HTTPException(404, "Documento não encontrado.")
    return crm_opp_documentos_repo.obter(doc_id)


@router.post("/opportunities/documentos/{doc_id}/arquivo")
async def upload_arquivo_documento(
    doc_id: int,
    arquivo: UploadFile = File(...),
    user: dict = Depends(require_permission("crm_opportunities", "editar")),
):
    if not crm_opp_documentos_repo.obter(doc_id):
        raise HTTPException(404, "Documento não encontrado.")
    dados = await arquivo.read()
    if len(dados) > DOC_MAX_SIZE:
        raise HTTPException(422, "Arquivo excede 15 MB.")
    crm_opp_documentos_repo.anexar_arquivo(doc_id, dados, arquivo.filename, arquivo.content_type)
    return crm_opp_documentos_repo.obter(doc_id)


@router.get("/opportunities/documentos/{doc_id}/arquivo")
async def baixar_documento_opp(doc_id: int, user: dict = Depends(require_permission("crm_opportunities", "ver"))):
    result = crm_opp_documentos_repo.obter_arquivo(doc_id)
    if not result:
        raise HTTPException(404, "Arquivo não encontrado.")
    dados, content_type, nome = result
    return Response(content=dados, media_type=content_type,
                    headers={"Content-Disposition": f'inline; filename="{nome}"'})


@router.delete("/opportunities/documentos/{doc_id}")
async def deletar_documento_opp(doc_id: int, user: dict = Depends(require_permission("crm_opportunities", "excluir"))):
    if not crm_opp_documentos_repo.deletar(doc_id):
        raise HTTPException(404, "Documento não encontrado.")
    return {"mensagem": "Documento excluído."}


# ---- Relatório contábil consolidado (XLSX) ----
@router.get("/relatorio/contabil")
async def relatorio_contabil(
    mes: Optional[int] = None, ano: Optional[int] = None,
    imovel_id: Optional[int] = None, proprietario_id: Optional[int] = None,
    comissao_status: Optional[str] = None, pipeline_id: Optional[int] = None,
    user: dict = Depends(require_permission("crm_opportunities", "ver")),
):
    from app.services.excel_service import gerar_xlsx_relatorio_contabil
    filtros = {"mes": mes, "ano": ano, "imovel_id": imovel_id,
               "proprietario_id": proprietario_id, "comissao_status": comissao_status,
               "pipeline_id": pipeline_id}
    rows = crm_opportunities_repo.relatorio_contabil(filtros)
    if imovel_id and rows:
        filtros["empreendimento"] = rows[0].get("imovel_nome")
    xlsx = gerar_xlsx_relatorio_contabil(rows, filtros)
    nome = f"relatorio_contabil_{ano or 'todos'}-{(str(mes).zfill(2) if mes else 'todos')}.xlsx"
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.patch("/opportunities/{id}")
async def patch_opportunity(id: int, body: dict, user: dict = Depends(require_permission("crm_opportunities", "editar"))):
    """Inline update — só atualiza campos enviados (preserva o resto)."""
    atual = crm_opportunities_repo.obter(id)
    if not atual:
        raise HTTPException(404, "Oportunidade não encontrada.")
    body["modificado_por_id"] = user.get("id")
    merged = {**atual, **{k: v for k, v in body.items()}}
    crm_opportunities_repo.atualizar(id, merged)
    opp = crm_opportunities_repo.obter(id)
    webhook_dispatcher.disparar("opportunity.updated", opp)
    return opp


@router.post("/opportunities/{id}/gerar-proposta")
async def gerar_proposta(id: int, user: dict = Depends(require_permission("crm_opportunities", "editar"))):
    """Cria uma Proposta pré-preenchida a partir de uma Opportunity."""
    from app.db import propostas_repo
    opp = crm_opportunities_repo.obter(id)
    if not opp:
        raise HTTPException(404, "Oportunidade não encontrada.")
    if not opp.get("cliente_id"):
        raise HTTPException(422, "Oportunidade precisa estar vinculada a um cliente.")

    proposta_id = propostas_repo.criar({
        "cliente_id": opp["cliente_id"],
        "imovel_id": opp.get("imovel_id"),
        "valor_total": str(opp["valor"]) if opp.get("valor") else None,
        "empreendimento": opp.get("imovel_nome") or "",
        "observacoes": opp.get("descricao"),
    })
    crm_opportunities_repo.vincular_proposta(id, proposta_id)
    return {
        "proposta_id": proposta_id,
        "opportunity_id": id,
        "edit_url": f"/proposta/{proposta_id}/editar",
    }


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@router.get("/activities")
async def listar_activities(page: int = 1, per_page: int = 25,
                              search: Optional[str] = None,
                              tipo: Optional[str] = None,
                              status: Optional[str] = None,
                              lead_id: Optional[int] = None,
                              opportunity_id: Optional[int] = None,
                              cliente_id: Optional[int] = None,
                              proprietario_id: Optional[int] = None,
                              user: dict = Depends(require_permission("crm_activities", "ver"))):
    rows, total = crm_activities_repo.listar(
        page=page, per_page=per_page, search=search,
        tipo=tipo, status=status,
        lead_id=lead_id, opportunity_id=opportunity_id,
        cliente_id=cliente_id, proprietario_id=proprietario_id,
    )
    return _paged(rows, total, page, per_page)


@router.get("/activities/{id}")
async def obter_activity(id: int, user: dict = Depends(require_permission("crm_activities", "ver"))):
    a = crm_activities_repo.obter(id)
    if not a:
        raise HTTPException(404, "Atividade não encontrada.")
    return a


@router.post("/activities", status_code=201)
async def criar_activity(body: dict, user: dict = Depends(require_permission("crm_activities", "criar"))):
    if not body.get("tipo") or not body.get("assunto"):
        raise HTTPException(422, "tipo e assunto obrigatórios")
    body["criado_por_id"] = user.get("id")
    aid = crm_activities_repo.criar(body)
    a = crm_activities_repo.obter(aid)
    webhook_dispatcher.disparar("activity.created", a)
    return a


@router.put("/activities/{id}")
async def atualizar_activity(id: int, body: dict, user: dict = Depends(require_permission("crm_activities", "editar"))):
    atual = crm_activities_repo.obter(id)
    if not atual:
        raise HTTPException(404, "Atividade não encontrada.")
    merged = {**atual, **{k: v for k, v in body.items() if v is not None}}
    crm_activities_repo.atualizar(id, merged)
    return crm_activities_repo.obter(id)


@router.post("/activities/{id}/concluir")
async def concluir_activity(id: int, user: dict = Depends(require_permission("crm_activities", "editar"))):
    if not crm_activities_repo.obter(id):
        raise HTTPException(404, "Atividade não encontrada.")
    crm_activities_repo.concluir(id)
    a = crm_activities_repo.obter(id)
    webhook_dispatcher.disparar("activity.completed", a)
    return a


@router.delete("/activities/{id}")
async def deletar_activity(id: int, user: dict = Depends(require_permission("crm_activities", "excluir"))):
    if not crm_activities_repo.obter(id):
        raise HTTPException(404, "Atividade não encontrada.")
    crm_activities_repo.deletar(id)
    return {"mensagem": "Atividade excluída."}


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@router.get("/webhooks")
async def listar_webhooks(user: dict = Depends(require_permission("crm_webhooks", "ver"))):
    return crm_webhooks_repo.listar()


@router.get("/webhooks/{id}")
async def obter_webhook(id: int, user: dict = Depends(require_permission("crm_webhooks", "ver"))):
    w = crm_webhooks_repo.obter(id)
    if not w:
        raise HTTPException(404, "Webhook não encontrado.")
    return w


@router.post("/webhooks", status_code=201)
async def criar_webhook(body: dict, user: dict = Depends(require_permission("crm_webhooks", "criar"))):
    for k in ("nome", "url", "eventos"):
        if not body.get(k):
            raise HTTPException(422, f"{k} é obrigatório")
    wid = crm_webhooks_repo.criar(body)
    return crm_webhooks_repo.obter(wid)


@router.put("/webhooks/{id}")
async def atualizar_webhook(id: int, body: dict, user: dict = Depends(require_permission("crm_webhooks", "editar"))):
    if not crm_webhooks_repo.atualizar(id, body):
        raise HTTPException(404, "Webhook não encontrado.")
    return crm_webhooks_repo.obter(id)


@router.delete("/webhooks/{id}")
async def deletar_webhook(id: int, user: dict = Depends(require_permission("crm_webhooks", "excluir"))):
    if not crm_webhooks_repo.deletar(id):
        raise HTTPException(404, "Webhook não encontrado.")
    return {"mensagem": "Webhook excluído."}


@router.get("/webhooks/{id}/logs")
async def webhook_logs(id: int, limit: int = 100,
                        user: dict = Depends(require_permission("crm_webhooks", "ver"))):
    return crm_webhooks_repo.listar_logs(webhook_id=id, limit=limit)


@router.post("/webhooks/{id}/test")
async def testar_webhook(id: int, user: dict = Depends(require_permission("crm_webhooks", "editar"))):
    """Dispara um payload de teste para validar a configuração do webhook."""
    wh = crm_webhooks_repo.obter(id)
    if not wh:
        raise HTTPException(404, "Webhook não encontrado.")
    webhook_dispatcher._enviar_webhook(
        wh, "webhook.test", {"mensagem": "Payload de teste do AM Imóveis CRM"},
    )
    return {"mensagem": "Teste disparado. Veja os logs."}


# ---------------------------------------------------------------------------
# Import CSV
# ---------------------------------------------------------------------------

@router.post("/import/leads")
async def importar_leads(arquivo: UploadFile = File(...),
                          user: dict = Depends(require_permission("crm_leads", "criar"))):
    """Importa leads em massa a partir de um CSV.

    O CSV deve ter cabeçalho com colunas: nome (obrigatório), email, telefone,
    whatsapp, cpf_cnpj, origem, status, interesse, valor_estimado, observacoes.
    Aceita ; , | ou tab como separador, UTF-8 ou Latin-1.
    """
    content = await arquivo.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(422, "Arquivo excede 10 MB.")
    return crm_importer.importar_leads_csv(content)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    return {
        "leads": crm_leads_repo.metricas(),
        "opportunities": crm_opportunities_repo.metricas(),
    }
