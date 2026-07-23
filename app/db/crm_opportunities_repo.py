"""Repositório de oportunidades (negociações) do CRM."""
from .connection import cursor

_SELECT_FULL = """
SELECT o.*,
       p.nome   AS pipeline_nome,
       s.nome   AS stage_nome,
       s.cor    AS stage_cor,
       s.tipo   AS stage_tipo,
       s.probabilidade AS stage_probabilidade,
       s.ordem  AS stage_ordem,
       cl.nome  AS cliente_nome,
       cl.cpf   AS cliente_cpf,
       cl.whatsapp1     AS cliente_whatsapp1,
       cl.telefone_fixo AS cliente_telefone_fixo,
       cl.email         AS cliente_email,
       cl.estado_civil  AS cliente_estado_civil,
       cl.nascimento    AS cliente_nascimento,
       l.nome   AS lead_nome,
       im.nome  AS imovel_nome,
       u.email  AS proprietario_email,
       uc.email AS corretor_imobiliaria_email,
       ua.email AS aprovador_email,
       ur.email AS responsavel_atual_email,
       ug.email AS gestor_atual_email,
       ucr.email AS criado_por_email,
       umd.email AS modificado_por_email,
       cmp.nome AS campaign_nome,
       pr.id    AS proposta_id_real,
       p.tipo   AS pipeline_tipo,
       p.pipeline_pos_venda_id AS venda_pipeline_pos_id,
       pp.nome  AS pos_venda_pipeline_nome,
       ps.nome  AS pos_venda_stage_nome,
       ps.tipo  AS pos_venda_stage_tipo,
       ps.cor   AS pos_venda_stage_cor,
       ps.ordem AS pos_venda_stage_ordem,
       ps.probabilidade AS pos_venda_stage_probabilidade
  FROM crm_opportunities o
  JOIN crm_pipelines p  ON p.id  = o.pipeline_id
  JOIN crm_stages    s  ON s.id  = o.stage_id
  LEFT JOIN crm_pipelines pp ON pp.id = o.pos_venda_pipeline_id
  LEFT JOIN crm_stages    ps ON ps.id = o.pos_venda_stage_id
  LEFT JOIN clientes  cl ON cl.id = o.cliente_id
  LEFT JOIN crm_leads l  ON l.id  = o.lead_id
  LEFT JOIN imoveis   im ON im.id = o.imovel_id
  LEFT JOIN usuarios  u   ON u.id   = o.proprietario_id
  LEFT JOIN usuarios  uc  ON uc.id  = o.corretor_imobiliaria_id
  LEFT JOIN usuarios  ua  ON ua.id  = o.aprovador_id
  LEFT JOIN usuarios  ur  ON ur.id  = o.responsavel_atual_id
  LEFT JOIN usuarios  ug  ON ug.id  = o.gestor_atual_id
  LEFT JOIN usuarios  ucr ON ucr.id = o.criado_por_id
  LEFT JOIN usuarios  umd ON umd.id = o.modificado_por_id
  LEFT JOIN crm_campaigns cmp ON cmp.id = o.campaign_id
  LEFT JOIN propostas pr ON pr.id = o.proposta_id
"""

_CAMPOS = [
    # Core
    "nome", "cliente_id", "lead_id", "pipeline_id", "stage_id",
    "imovel_id", "unidade_id", "valor", "probabilidade", "data_previsao", "data_fechamento",
    "proprietario_id", "campaign_id", "status", "motivo_perda",
    "proposta_id", "descricao",
    # Identificação / status
    "altera_proprietario", "solicitante", "classificacao_lead", "url_jornada",
    "pendencia_documentos", "sla_expirado", "data_limite_contrato",
    "indicacao_premiada", "enquadramento_apurado", "origem_lead", "marca",
    # Empreendimento snapshot
    "empreendimento_nome", "status_lancamento", "unidade", "imobiliaria", "equipe",
    # Equipe FKs
    "corretor_imobiliaria_id", "aprovador_id", "responsavel_atual_id", "gestor_atual_id",
    # PAC
    "pac_codigo", "pac_valor_imovel", "pac_status", "pac_tipo_amortizacao",
    # Emcash
    "emcash_habilitado", "data_emcash_habilitado",
    # Entrada Facilitada
    "entrada_facilitada", "data_entrada_facilitada",
    # Pagadoria
    "pagadoria", "data_pagadoria",
    # Plano Padrão
    "plano_padrao_aplicado", "data_plano_padrao",
    # Rating
    "rating_gerencial_aplicado", "solicitacao_rating",
    "status_solicitacao_propriedade", "remetente_solicitacao_rating",
    # Negociação Especial
    "negociacao_especial_aplicada", "solicitacao_negociacao_especial",
    "data_ativacao_negociacao_especial", "motivo_negociacao_especial",
    # Financeiro
    "valor_entrada", "valor_total_pagar", "valor_parcela_mensal",
    # Simulação Banco
    "banco_financiador", "avaliacao_banco", "tipo_financiamento",
    "valor_parcela_banco", "prazo_simulacao_meses",
    "valor_total_financiamento", "taxa_juros_anual",
    # Simulação Plataforma
    "renda_mensal", "contribuicao_fgts_3anos", "possui_dependentes",
    "data_nasc_mais_velha", "valor_sinal", "desconto_mrv",
    "valor_fgts", "beneficio_mcmv", "valor_parcela_mrv",
    "fator_social", "estado_civil", "valor_imovel",
    # Boleto
    "codigo_acao_boleto", "linha_digitavel_boleto",
    # Fechamento
    "assinatura_banco_data", "resgate_fgts", "registro",
    # ===== Layout Pós-Venda PHB (13 cards) =====
    # Card 2: Dados do Imóvel
    "imovel_endereco", "imovel_bairro", "imovel_cidade_uf", "imovel_cep", "imovel_tipo",
    # Card 3: Dados da Venda
    "venda_forma_entrada", "venda_qtd_parcelas_entrada", "venda_valor_parcela_entrada",
    "venda_data_primeira_parcela", "data_contrato", "numero_contrato",
    # Card 6: PAC (complemento)
    "pac_valor_avaliacao", "pac_probabilidade", "pac_prazo_meses",
    "pac_valor_parcela", "pac_tipo_analise",
    # Card 7: Entrada Facilitada (complemento)
    "ef_construtora", "ef_qtd_parcelas", "ef_valor_parcela", "ef_valor_total", "ef_observacao",
    # Card 9: Equipe
    "construtora_nome",
    # Card 12/13: Resumo Financeiro + Contábil
    "comissao_total", "comissao_recebimento_1", "comissao_restante",
    "comissao_previsao_recebimento", "comissao_status", "comissao_forma_recebimento",
    "contabil_mes_fechamento", "contabil_data_fechamento",
    # Sistema
    "criado_por_id", "modificado_por_id",
]


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (o.nome ILIKE %s OR cl.nome ILIKE %s)"
        s = f"%{search}%"
        params += [s, s]

    for f in ("status", "pipeline_id", "stage_id", "proprietario_id", "cliente_id"):
        v = filters.get(f)
        if v not in (None, ""):
            where += f" AND o.{f} = %s"
            params.append(v)

    with cursor() as cur:
        cur.execute(
            f"""SELECT COUNT(*) FROM crm_opportunities o
                  LEFT JOIN clientes cl ON cl.id = o.cliente_id {where}""",
            params,
        )
        total = cur.fetchone()["count"]
        cur.execute(
            f"{_SELECT_FULL} {where} ORDER BY o.created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]
    return rows, total


def listar_kanban(pipeline_id: int = None, por_pos_venda: bool = False):
    """Retorna oportunidades agrupadas para visão Kanban.

    ``por_pos_venda=False`` (padrão): jornada de VENDA — filtra por
    ``pipeline_id`` e ordena pela etapa de venda (``s.ordem``).
    ``por_pos_venda=True``: jornada de PÓS-VENDA — inclui tanto as opps
    PROMOVIDAS para esta pós-venda (``pos_venda_pipeline_id``) quanto as que
    têm esta pós-venda como pipeline PRIMÁRIA (``pipeline_id``) — ex.: opps
    criadas/importadas direto num funil de pós-venda, que têm
    ``pos_venda_pipeline_id`` NULL. O agrupamento por coluna (no router)
    escolhe ``pos_venda_stage_id`` ou ``stage_id`` conforme o caso.
    Em ambos os casos a MESMA oportunidade pode aparecer no kanban de venda
    (na coluna ganho) e no de pós-venda (na sua etapa atual), sem duplicar.
    """
    where = "WHERE 1=1"
    params = []
    if pipeline_id:
        if por_pos_venda:
            where += " AND (o.pos_venda_pipeline_id = %s OR o.pipeline_id = %s)"
            params += [pipeline_id, pipeline_id]
        else:
            where += " AND o.pipeline_id = %s"
            params.append(pipeline_id)
    order = "COALESCE(ps.ordem, s.ordem)" if por_pos_venda else "s.ordem"
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} {where} ORDER BY {order}, o.created_at DESC", params)
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE o.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def oportunidade_ativa_da_unidade(unidade_id: int, excluir_id: int | None = None) -> dict | None:
    """Oportunidade NÃO-perdida que já ocupa a unidade (para o 409 amigável).

    Espelha a regra do índice único parcial `crm_opp_unidade_ativa_uniq`. `excluir_id`
    permite ignorar a própria oportunidade numa eventual revalidação de update."""
    with cursor() as cur:
        sql = (
            "SELECT o.id, o.nome, o.status, s.nome AS stage_nome "
            "FROM crm_opportunities o LEFT JOIN crm_stages s ON s.id = o.stage_id "
            "WHERE o.unidade_id = %s AND o.status <> 'perdida'"
        )
        params: list = [unidade_id]
        if excluir_id:
            sql += " AND o.id <> %s"
            params.append(excluir_id)
        cur.execute(sql + " LIMIT 1", params)
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    params = {c: dados.get(c) for c in _CAMPOS}
    if not params.get("status"):
        params["status"] = "aberta"
    with cursor() as cur:
        cur.execute(
            f"INSERT INTO crm_opportunities ({cols}) VALUES ({placeholders}) RETURNING id",
            params,
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    """Update PARCIAL: grava só as colunas presentes em ``dados``.

    Colunas de ``_CAMPOS`` ausentes do dict NÃO são tocadas — evita zerar
    silenciosamente campos não enviados (p.ex. as ~80 colunas Salesforce que
    um PUT do formulário básico não inclui). Nenhum dado é perdido por omissão.
    """
    campos = [c for c in _CAMPOS if c in dados]
    if not campos:
        return False
    sets = ", ".join(f"{c} = %({c})s" for c in campos)
    params = {c: dados.get(c) for c in campos}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE crm_opportunities SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def _criar_tarefa_automatica(cur, opp_id, stage, cliente_id, proprietario_id):
    """Cria a 'próxima ação automática' da etapa (card 11 'Próxima Ação'), se a
    etapa tiver ``auto_tarefa_assunto`` configurado. Genérico p/ QUALQUER pipeline.

    Idempotente: não duplica se já houver tarefa automática PENDENTE da mesma
    etapa nesta oportunidade. Prazo = agora + (auto_tarefa_prazo_dias OU sla_dias
    OU 0) dias. Responsável = proprietário da oportunidade.
    """
    assunto = stage.get("auto_tarefa_assunto")
    if not assunto:
        return
    cur.execute(
        """SELECT 1 FROM crm_activities
            WHERE opportunity_id = %s AND stage_id = %s AND auto = TRUE AND status = 'pendente'
            LIMIT 1""",
        (opp_id, stage["id"]),
    )
    if cur.fetchone():
        return
    prazo = stage.get("auto_tarefa_prazo_dias")
    if prazo is None:
        prazo = stage.get("sla_dias")
    prazo = prazo or 0
    cur.execute(
        """INSERT INTO crm_activities
               (tipo, assunto, descricao, data_atividade, status, prioridade,
                opportunity_id, cliente_id, proprietario_id, criado_por_id, stage_id, auto)
           VALUES (%s, %s, %s, NOW() + (%s || ' days')::interval, 'pendente', 'normal',
                   %s, %s, %s, %s, %s, TRUE)""",
        (stage.get("auto_tarefa_tipo") or "tarefa", assunto, stage.get("auto_tarefa_descricao"),
         prazo, opp_id, cliente_id, proprietario_id, proprietario_id, stage["id"]),
    )


def mudar_stage(id: int, stage_id_to: int, usuario_id: int = None, motivo: str = None):
    """Move a oportunidade para a etapa destino e registra no histórico.

    Roteamento por JORNADA: a etapa destino pertence a uma pipeline. Se essa
    pipeline for a de pós-venda da oportunidade, move a jornada de PÓS-VENDA
    (``pos_venda_stage_id``). Senão, move a jornada de VENDA (``stage_id``) e,
    ao atingir uma etapa tipo ``ganho``, PROMOVE automaticamente para a
    pós-venda vinculada — mesma oportunidade, sem duplicar, sem sair da venda.

    Retorna dict com ``fase`` ('venda'|'pos_venda') e ``promovida`` (bool),
    ou None se não encontrar a oportunidade/etapa.
    """
    with cursor() as cur:
        cur.execute(
            """SELECT o.stage_id, o.pos_venda_stage_id, o.pos_venda_pipeline_id,
                      o.pipeline_id, o.cliente_id, o.proprietario_id,
                      p.pipeline_pos_venda_id
                 FROM crm_opportunities o
                 JOIN crm_pipelines p ON p.id = o.pipeline_id
                WHERE o.id = %s""",
            (id,),
        )
        opp = cur.fetchone()
        if not opp:
            return None

        cur.execute("SELECT * FROM crm_stages WHERE id = %s", (stage_id_to,))
        stage = cur.fetchone()
        if not stage:
            return None

        # A etapa destino pertence à jornada de PÓS-VENDA da oportunidade?
        is_pos = (opp["pos_venda_pipeline_id"] is not None
                  and stage["pipeline_id"] == opp["pos_venda_pipeline_id"])

        if is_pos:
            stage_id_from = opp["pos_venda_stage_id"]
            cur.execute(
                "UPDATE crm_opportunities SET pos_venda_stage_id = %s, updated_at = NOW() WHERE id = %s",
                (stage_id_to, id),
            )
            cur.execute(
                """INSERT INTO crm_stage_history (opportunity_id, stage_id_from, stage_id_to, usuario_id, motivo)
                   VALUES (%s, %s, %s, %s, %s)""",
                (id, stage_id_from, stage_id_to, usuario_id, motivo),
            )
            _criar_tarefa_automatica(cur, id, stage, opp["cliente_id"], opp["proprietario_id"])
            return {"fase": "pos_venda", "promovida": False}

        # --- jornada de VENDA ---
        stage_id_from = opp["stage_id"]
        novo_status = {"ganho": "ganha", "perdido": "perdida"}.get(stage["tipo"], "aberta")
        cur.execute(
            """UPDATE crm_opportunities
                  SET stage_id = %s, status = %s, updated_at = NOW(),
                      data_fechamento = CASE WHEN %s IN ('ganha','perdida') THEN CURRENT_DATE ELSE data_fechamento END,
                      motivo_perda = COALESCE(%s, motivo_perda)
                WHERE id = %s""",
            (stage_id_to, novo_status, novo_status, motivo, id),
        )
        cur.execute(
            """INSERT INTO crm_stage_history (opportunity_id, stage_id_from, stage_id_to, usuario_id, motivo)
               VALUES (%s, %s, %s, %s, %s)""",
            (id, stage_id_from, stage_id_to, usuario_id, motivo),
        )
        _criar_tarefa_automatica(cur, id, stage, opp["cliente_id"], opp["proprietario_id"])

        # Promoção automática para a pós-venda ao GANHAR (idempotente)
        promovida = False
        if (stage["tipo"] == "ganho"
                and opp["pipeline_pos_venda_id"]
                and opp["pos_venda_pipeline_id"] is None):
            pos_pid = opp["pipeline_pos_venda_id"]
            cur.execute(
                "SELECT * FROM crm_stages WHERE pipeline_id = %s ORDER BY ordem, id LIMIT 1",
                (pos_pid,),
            )
            first = cur.fetchone()
            if first:
                cur.execute(
                    """UPDATE crm_opportunities
                          SET pos_venda_pipeline_id = %s, pos_venda_stage_id = %s,
                              pos_venda_iniciada_em = NOW(), updated_at = NOW()
                        WHERE id = %s""",
                    (pos_pid, first["id"], id),
                )
                cur.execute(
                    """INSERT INTO crm_stage_history (opportunity_id, stage_id_from, stage_id_to, usuario_id, motivo)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (id, None, first["id"], usuario_id, "Promovida automaticamente para pós-venda"),
                )
                _criar_tarefa_automatica(cur, id, first, opp["cliente_id"], opp["proprietario_id"])
                promovida = True
        return {"fase": "venda", "promovida": promovida}


def aplicar_automacao_etapa_atual(opp_id: int):
    """Cria a tarefa automática da etapa ATIVA da oportunidade (usado ao CRIAR a
    oportunidade, para a etapa inicial). Idempotente — não duplica."""
    with cursor() as cur:
        cur.execute(
            """SELECT COALESCE(pos_venda_stage_id, stage_id) AS active_stage_id,
                      cliente_id, proprietario_id
                 FROM crm_opportunities WHERE id = %s""",
            (opp_id,),
        )
        o = cur.fetchone()
        if not o or not o["active_stage_id"]:
            return
        cur.execute("SELECT * FROM crm_stages WHERE id = %s", (o["active_stage_id"],))
        stage = cur.fetchone()
        if stage:
            _criar_tarefa_automatica(cur, opp_id, stage, o["cliente_id"], o["proprietario_id"])


def relatorio_contabil(filtros: dict = None):
    """Linhas para o relatório contábil consolidado (com JOINs de cliente/imóvel/
    responsável/funil). Filtra por mês/ano (data de fechamento), imóvel, responsável,
    status da comissão e pipeline. Período usa COALESCE(contabil_data_fechamento, data_fechamento)."""
    filtros = filtros or {}
    where = ["1=1"]
    params = []
    periodo = "COALESCE(o.contabil_data_fechamento, o.data_fechamento)"
    if filtros.get("ano"):
        where.append(f"EXTRACT(YEAR FROM {periodo}) = %s"); params.append(filtros["ano"])
    if filtros.get("mes"):
        where.append(f"EXTRACT(MONTH FROM {periodo}) = %s"); params.append(filtros["mes"])
    if filtros.get("imovel_id"):
        where.append("o.imovel_id = %s"); params.append(filtros["imovel_id"])
    if filtros.get("proprietario_id"):
        where.append("o.proprietario_id = %s"); params.append(filtros["proprietario_id"])
    if filtros.get("comissao_status"):
        where.append("o.comissao_status = %s"); params.append(filtros["comissao_status"])
    if filtros.get("pipeline_id"):
        where.append("o.pipeline_id = %s"); params.append(filtros["pipeline_id"])
    sql = f"""
        SELECT o.*, cl.nome AS cliente_nome, cl.cpf AS cliente_cpf,
               im.nome AS imovel_nome, u.email AS proprietario_email,
               p.nome AS pipeline_nome, s.nome AS stage_nome
          FROM crm_opportunities o
          LEFT JOIN clientes      cl ON cl.id = o.cliente_id
          LEFT JOIN imoveis       im ON im.id = o.imovel_id
          LEFT JOIN usuarios      u  ON u.id  = o.proprietario_id
          LEFT JOIN crm_pipelines p  ON p.id  = o.pipeline_id
          LEFT JOIN crm_stages    s  ON s.id  = o.stage_id
         WHERE {' AND '.join(where)}
         ORDER BY {periodo} DESC NULLS LAST, o.id"""
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM crm_opportunities WHERE id = %s", (id,))
        return cur.rowcount > 0


def vincular_proposta(opp_id: int, proposta_id: int):
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE crm_opportunities SET proposta_id = %s, updated_at = NOW() WHERE id = %s",
            (proposta_id, opp_id),
        )
        return cur.rowcount > 0


def metricas():
    with cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'aberta')   AS abertas,
                COUNT(*) FILTER (WHERE status = 'ganha')    AS ganhas,
                COUNT(*) FILTER (WHERE status = 'perdida')  AS perdidas,
                COALESCE(SUM(valor) FILTER (WHERE status = 'aberta'), 0) AS valor_aberto,
                COALESCE(SUM(valor) FILTER (WHERE status = 'ganha'), 0)  AS valor_ganho,
                COALESCE(AVG(valor) FILTER (WHERE status = 'ganha'), 0)  AS ticket_medio
              FROM crm_opportunities
        """)
        m = dict(cur.fetchone())
        for k in ("valor_aberto", "valor_ganho", "ticket_medio"):
            m[k] = float(m[k] or 0)
        return m
