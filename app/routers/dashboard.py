"""Dashboard executivo da home — métricas agregadas de todo o portal.

Um único endpoint (`GET /api/v1/dashboard/resumo`) devolve tudo que a home
precisa em uma chamada: KPIs com variação vs mês anterior, funil de vendas,
VGV por empreendimento, Meta × Realizado, origem dos leads, top corretores,
agenda de hoje e atividades recentes.

Autorização: números AGREGADOS são abertos a qualquer logado (mesmo critério
de /lookup/contadores e /crm/dashboard). Blocos com REGISTROS INDIVIDUAIS
(agenda de hoje, atividades recentes) respeitam o RBAC: cada fonte só entra
se o usuário tiver `ver` no recurso correspondente.

Timezone: o Postgres roda em UTC e o negócio opera em America/Fortaleza
(UTC-3, sem DST). Todos os cortes de "hoje"/"mês" usam o relógio LOCAL —
sem isso, a agenda virava "amanhã" às 21h e registros criados entre 21h e
23h59 do último dia do mês caíam no mês seguinte.
"""
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import user_can
from app.db.connection import cursor

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

_TZ = "America/Fortaleza"
_AGORA = f"(now() AT TIME ZONE '{_TZ}')"                       # timestamp local (naive)


def _local(campo: str) -> str:
    """Instante real (timestamptz) convertido para o relógio local (naive)."""
    return f"({campo} AT TIME ZONE '{_TZ}')"


def _var_pct(atual, anterior):
    """Variação % entre dois volumes; None quando não dá pra comparar."""
    if anterior is None or anterior == 0:
        return None
    return round((float(atual) - float(anterior)) / float(anterior) * 100, 1)


def _periodo_where(campo_local: str, periodo: str) -> str:
    """Filtro SQL do período global (mes|ano|tudo) sobre um campo JÁ em hora local."""
    if periodo == "mes":
        return f"AND date_trunc('month', {campo_local}) = date_trunc('month', {_AGORA})"
    if periodo == "ano":
        return f"AND date_trunc('year', {campo_local}) = date_trunc('year', {_AGORA})"
    return ""


# Data de fechamento efetiva de uma opp ganha, em hora local. data_fechamento é DATE
# (gravada pelo fluxo de stage); o fallback updated_at cobre ganhas antigas sem a data —
# LIMITAÇÃO conhecida: editar uma ganha antiga move o updated_at (e o mês do VGV dela).
_FECH = f"COALESCE(o.data_fechamento::timestamp, o.updated_at AT TIME ZONE '{_TZ}')"
# VGV de uma oportunidade = valor do imóvel (venda); fallback no valor da oportunidade.
_VGV = "COALESCE(o.valor_imovel, o.valor, 0)"
# Métricas de VENDA não contam oportunidades criadas direto em funis de pós-venda
# (jornada de acompanhamento, não venda — inflaria taxa/comissões/VGV).
_JOIN_VENDA = ("JOIN crm_pipelines pl ON pl.id = o.pipeline_id "
               "AND COALESCE(pl.tipo, 'venda') <> 'pos_venda'")


@router.get("/resumo")
async def resumo(periodo: str = Query("mes", pattern="^(mes|ano|tudo)$"),
                 user=Depends(get_current_user)):
    out = {"periodo": periodo}
    with cursor() as cur:
        # ---------------- KPIs ------------------------------------------------------------
        # Variação = novos este mês vs novos mês passado (entradas), em hora local.
        def _kpi_contagem(tabela, campo_data, where_total="", where_inflow=None):
            # where_inflow separado: p/ leads, o estoque é filtrado por status mas a ENTRADA
            # conta todos os novos (senão um lead convertido some do influxo e enviesa a %).
            wi = where_total if where_inflow is None else where_inflow
            loc = _local(campo_data)
            cur.execute(f"""
                SELECT (SELECT COUNT(*) FROM {tabela} WHERE 1=1 {where_total}) AS total,
                       (SELECT COUNT(*) FROM {tabela}
                         WHERE date_trunc('month', {loc}) = date_trunc('month', {_AGORA}) {wi}) AS novos_mes,
                       (SELECT COUNT(*) FROM {tabela}
                         WHERE date_trunc('month', {loc}) = date_trunc('month', {_AGORA} - interval '1 month') {wi}) AS novos_passado
            """)
            r = cur.fetchone()
            return {"atual": r["total"], "var_pct": _var_pct(r["novos_mes"], r["novos_passado"])}

        kpis = {}
        kpis["leads_ativos"] = _kpi_contagem(
            "crm_leads", "created_at",
            where_total="AND status NOT IN ('convertido','descartado')", where_inflow="")
        kpis["clientes"] = _kpi_contagem("clientes", "created_at")
        kpis["propostas"] = _kpi_contagem("propostas", "created_at")
        kpis["financiamentos_aprovados"] = _kpi_contagem(
            "financiamentos", "created_at", where_total="AND analise = 'APROVADO'")

        # Imóveis disponíveis: unidades com status 'disponivel' E sem oportunidade ativa
        # (o status é editável na tela de imóveis — vendas fora do CRM contam também).
        # Sem unidades cadastradas, cai para o total de imóveis. Sem histórico → sem variação.
        cur.execute("""
            SELECT (SELECT COUNT(*) FROM imovel_unidades) AS unidades,
                   (SELECT COUNT(*) FROM imovel_unidades u
                     WHERE u.status = 'disponivel'
                       AND NOT EXISTS (SELECT 1 FROM crm_opportunities o
                                        WHERE o.unidade_id = u.id AND o.status <> 'perdida')) AS disponiveis,
                   (SELECT COUNT(*) FROM imoveis) AS imoveis
        """)
        r = cur.fetchone()
        kpis["imoveis_disponiveis"] = {
            "atual": r["disponiveis"] if r["unidades"] > 0 else r["imoveis"],
            "var_pct": None,
        }

        # VGV do mês (ganhas de VENDA fechadas no mês) vs mês anterior.
        cur.execute(f"""
            SELECT COALESCE(SUM({_VGV}) FILTER (WHERE date_trunc('month', {_FECH}) = date_trunc('month', {_AGORA})), 0) AS mes,
                   COALESCE(SUM({_VGV}) FILTER (WHERE date_trunc('month', {_FECH}) = date_trunc('month', {_AGORA} - interval '1 month')), 0) AS passado
              FROM crm_opportunities o {_JOIN_VENDA}
             WHERE o.status = 'ganha'
        """)
        r = cur.fetchone()
        kpis["vgv_mes"] = {"atual": float(r["mes"]), "var_pct": _var_pct(r["mes"], r["passado"])}

        # Taxa de conversão = ganhas / total (só funis de VENDA). Variação em p.p. vs a taxa
        # das opps criadas até o fim do mês passado (aproximação: usa o status atual delas).
        cur.execute(f"""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE o.status = 'ganha') AS ganhas,
                   COUNT(*) FILTER (WHERE {_local('o.created_at')} < date_trunc('month', {_AGORA})) AS total_ant,
                   COUNT(*) FILTER (WHERE {_local('o.created_at')} < date_trunc('month', {_AGORA}) AND o.status = 'ganha') AS ganhas_ant
              FROM crm_opportunities o {_JOIN_VENDA}
        """)
        r = cur.fetchone()
        taxa = (r["ganhas"] / r["total"] * 100) if r["total"] else 0.0
        taxa_ant = (r["ganhas_ant"] / r["total_ant"] * 100) if r["total_ant"] else None
        kpis["taxa_conversao"] = {
            "atual": round(taxa, 1),
            "var_pp": round(taxa - taxa_ant, 1) if taxa_ant is not None else None,
        }

        # Comissões previstas = comissão das oportunidades de VENDA abertas.
        cur.execute(f"""
            SELECT COALESCE(SUM(o.comissao_total) FILTER (WHERE o.status = 'aberta'), 0) AS previstas,
                   COALESCE(SUM(o.comissao_total) FILTER (WHERE date_trunc('month', {_local('o.created_at')}) = date_trunc('month', {_AGORA})), 0) AS mes,
                   COALESCE(SUM(o.comissao_total) FILTER (WHERE date_trunc('month', {_local('o.created_at')}) = date_trunc('month', {_AGORA} - interval '1 month')), 0) AS passado
              FROM crm_opportunities o {_JOIN_VENDA}
        """)
        r = cur.fetchone()
        kpis["comissoes_previstas"] = {"atual": float(r["previstas"]),
                                       "var_pct": _var_pct(r["mes"], r["passado"])}
        out["kpis"] = kpis

        # ---------------- Funil de vendas (pipeline default de venda; opps por etapa) -------
        cur.execute("""
            SELECT p.id, p.nome FROM crm_pipelines p
             WHERE p.ativo = TRUE AND COALESCE(p.tipo, 'venda') <> 'pos_venda'
             ORDER BY p.is_default DESC, p.id LIMIT 1
        """)
        pl = cur.fetchone()
        funil = {"pipeline": pl["nome"] if pl else None, "leads_total": 0, "etapas": []}
        cur.execute("SELECT COUNT(*) AS n FROM crm_leads")
        funil["leads_total"] = cur.fetchone()["n"]
        if pl:
            cur.execute("""
                SELECT s.nome, s.cor, COUNT(o.id) AS count
                  FROM crm_stages s
                  LEFT JOIN crm_opportunities o ON o.stage_id = s.id
                 WHERE s.pipeline_id = %s
                 GROUP BY s.id, s.nome, s.cor, s.ordem
                 ORDER BY s.ordem, s.id
            """, (pl["id"],))
            funil["etapas"] = [dict(r) for r in cur.fetchall()]
        out["funil"] = funil

        # ---------------- Vendas (VGV) por empreendimento — período global ------------------
        pf = _periodo_where(_FECH, periodo)
        cur.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(o.empreendimento_nome), ''), im.nome, '(sem empreendimento)') AS nome,
                   SUM({_VGV}) AS vgv
              FROM crm_opportunities o {_JOIN_VENDA}
              LEFT JOIN imoveis im ON im.id = o.imovel_id
             WHERE o.status = 'ganha' {pf}
             GROUP BY 1 ORDER BY 2 DESC LIMIT 6
        """)
        out["vendas_empreendimento"] = [
            {"nome": r["nome"], "vgv": float(r["vgv"] or 0)} for r in cur.fetchall()]

        # ---------------- Meta × Realizado (VGV) — últimos 6 meses --------------------------
        cur.execute(f"""
            SELECT to_char(date_trunc('month', {_FECH}), 'YYYY-MM') AS ym, SUM({_VGV}) AS vgv
              FROM crm_opportunities o {_JOIN_VENDA}
             WHERE o.status = 'ganha'
               AND {_FECH} >= date_trunc('month', {_AGORA}) - interval '5 months'
             GROUP BY 1
        """)
        por_mes = {r["ym"]: float(r["vgv"] or 0) for r in cur.fetchall()}
        cur.execute(f"""
            SELECT to_char(date_trunc('month', {_AGORA}) - (i || ' months')::interval, 'YYYY-MM') AS ym
              FROM generate_series(5, 0, -1) AS i
        """)
        _MES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        meses = [{"ym": r["ym"],
                  "label": _MES_PT[int(r["ym"][5:7]) - 1] + "/" + r["ym"][2:4]}
                 for r in cur.fetchall()]
        cur.execute("SELECT value FROM app_settings WHERE key = 'meta_vgv_mensal'")
        r = cur.fetchone()
        try:
            meta = float(r["value"]) if r and r["value"] not in (None, "") else None
        except (TypeError, ValueError):
            meta = None
        out["meta_realizado"] = {
            "meses": [m["label"] for m in meses],
            "realizado": [por_mes.get(m["ym"], 0.0) for m in meses],
            "meta": meta,
        }

        # ---------------- Origem dos leads — período global ---------------------------------
        pf = _periodo_where(_local("l.created_at"), periodo)
        cur.execute(f"""
            SELECT COALESCE(NULLIF(TRIM(l.origem), ''), 'Outros') AS origem, COUNT(*) AS count
              FROM crm_leads l WHERE 1=1 {pf}
             GROUP BY 1 ORDER BY 2 DESC LIMIT 6
        """)
        out["origem_leads"] = [dict(r) for r in cur.fetchall()]

        # ---------------- Top corretores (proprietários) por VGV ganho — período ------------
        pf = _periodo_where(_FECH, periodo)
        cur.execute(f"""
            SELECT COALESCE(u.nome, u.email, '(sem responsável)') AS nome,
                   SUM({_VGV}) AS vgv, COUNT(*) AS vendas
              FROM crm_opportunities o {_JOIN_VENDA}
              LEFT JOIN usuarios u ON u.id = o.proprietario_id
             WHERE o.status = 'ganha' {pf}
             GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """)
        out["top_corretores"] = [
            {"nome": r["nome"], "vgv": float(r["vgv"] or 0), "vendas": r["vendas"]}
            for r in cur.fetchall()]

        # ---------------- Agenda de hoje (REGISTROS individuais → exige RBAC) ---------------
        # "Hoje" pelo relógio local. O lado esquerdo fica cru de propósito: atividades manuais
        # são gravadas com a hora digitada (ver form) e ::date devolve a data local digitada.
        out["agenda_hoje"] = []
        out["agenda_hoje_total"] = 0
        if user_can(user, "crm_activities", "ver"):
            cur.execute(f"""
                SELECT to_char(a.data_atividade, 'HH24:MI') AS hora, a.assunto, a.tipo, a.status
                  FROM crm_activities a
                 WHERE a.data_atividade::date = {_AGORA}::date
                 ORDER BY a.data_atividade LIMIT 8
            """)
            out["agenda_hoje"] = [dict(r) for r in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) AS n FROM crm_activities a WHERE a.data_atividade::date = {_AGORA}::date")
            out["agenda_hoje_total"] = cur.fetchone()["n"]

        # ---------------- Atividades recentes (REGISTROS individuais → RBAC por fonte) ------
        fontes = []
        if user_can(user, "clientes", "ver"):
            fontes.append("""
                (SELECT 'Cliente' AS tipo, c.nome AS titulo,
                        COALESCE(cd.nome, '') AS subtitulo,
                        COALESCE(u.nome, u.email, '') AS responsavel,
                        'Novo' AS status, c.created_at AS data
                   FROM clientes c
                   LEFT JOIN cidades cd ON cd.id = c.cidade_id
                   LEFT JOIN usuarios u ON u.id = c.criado_por_id)""")
        if user_can(user, "proposta", "ver"):
            fontes.append("""
                (SELECT 'Proposta', COALESCE(c.nome, '—'),
                        COALESCE(p.empreendimento, ''), COALESCE(p.corretor_nome, ''),
                        'Emitida', p.created_at
                   FROM propostas p LEFT JOIN clientes c ON c.id = p.cliente_id)""")
        if user_can(user, "financiamento", "ver"):
            fontes.append("""
                (SELECT 'Financiamento', COALESCE(c.nome, '—'),
                        COALESCE(f.modalidade::text, ''), '',
                        INITCAP(REPLACE(f.analise::text, '_', ' ')), f.created_at
                   FROM financiamentos f LEFT JOIN clientes c ON c.id = f.cliente_id)""")
        if user_can(user, "crm_activities", "ver"):
            fontes.append("""
                (SELECT INITCAP(a.tipo), a.assunto,
                        COALESCE(c.nome, ''), COALESCE(u.nome, u.email, ''),
                        INITCAP(a.status), a.created_at
                   FROM crm_activities a
                   LEFT JOIN usuarios u ON u.id = a.proprietario_id
                   LEFT JOIN clientes c ON c.id = a.cliente_id)""")
        out["atividades_recentes"] = []
        if fontes:
            cur.execute(" UNION ALL ".join(fontes) + " ORDER BY data DESC NULLS LAST LIMIT 8")
            out["atividades_recentes"] = [
                {**dict(r), "data": r["data"].isoformat() if r["data"] else None}
                for r in cur.fetchall()]

    return out
