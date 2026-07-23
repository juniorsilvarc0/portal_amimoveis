"""Router de páginas HTML do portal.

Serve arquivos estáticos como rotas nomeadas (sem prefixo /static).
Rotas cujo HTML ainda não existe retornam uma página "Em construção" inline.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

router = APIRouter(tags=["Pages"])

BASE = Path(__file__).resolve().parent.parent.parent / "static"


def _em_construcao(titulo: str = "Em construção", modulo: str = "") -> HTMLResponse:
    html = (
        "<!doctype html><html lang='pt-BR'><head>"
        "<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>" + titulo + " — AM Imoveis</title>"
        "<link href='https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap' rel='stylesheet'>"
        "<style>"
        "body{font-family:'DM Sans',sans-serif;background:#f4f6f9;display:flex;align-items:center;"
        "justify-content:center;min-height:100vh;margin:0;color:#2d3748}"
        ".card{background:#fff;border-radius:12px;padding:48px 40px;text-align:center;"
        "box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:480px;width:90%}"
        "h1{font-size:28px;font-weight:700;color:#065676;margin-bottom:10px}"
        "p{color:#8896a6;margin-bottom:28px;font-size:15px}"
        "a{display:inline-block;background:#E5094B;color:#fff;padding:10px 24px;"
        "border-radius:8px;font-weight:600;text-decoration:none}"
        "a:hover{background:#c70840}"
        ".badge{display:inline-block;background:#fef3f2;color:#E5094B;font-size:11px;"
        "font-weight:700;padding:4px 10px;border-radius:20px;margin-bottom:20px;letter-spacing:.5px}"
        "</style></head><body>"
        "<div class='card'>"
        "<div class='badge'>EM DESENVOLVIMENTO</div>"
        "<h1>" + titulo + "</h1>"
        "<p>O módulo <strong>" + (modulo or titulo) + "</strong> está sendo desenvolvido e estará disponível em breve.</p>"
        "<a href='/'>&#8592; Voltar ao início</a>"
        "</div></body></html>"
    )
    return HTMLResponse(content=html)


_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _page(filename: str):
    """Retorna FileResponse se o arquivo existir, caso contrário 'Em construção'.

    HTMLs do portal sempre vão com Cache-Control: no-cache para evitar que
    usuários vejam versão antiga após redeploy (o browser deve sempre revalidar).
    """
    async def _handler():
        path = BASE / filename
        if path.exists():
            return FileResponse(
                str(path),
                media_type="text/html",
                headers=_NO_CACHE_HEADERS,
            )
        titulo = filename.split(".")[0].replace("_", " ").title()
        return _em_construcao(titulo, filename.split(".")[0])
    return _handler


# ---------------------------------------------------------------------------
# Raiz e autenticação
# ---------------------------------------------------------------------------
router.get("/")(          _page("portal_dashboard.html"))
router.get("/login")(     _page("login.html"))

# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------
router.get("/clientes")(          _page("clientes.html"))
router.get("/cliente/novo")(      _page("cliente_detail.html"))   # modo novo (edição inline Salesforce-style)


@router.get("/cliente/{cid}/editar")
async def cliente_editar(cid: int):
    """Serve o mesmo form (JS lê o ID da URL e entra em modo edição)."""
    path = BASE / "clientes_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Cliente", "clientes_form")


@router.get("/clientes/{cid}")
async def cliente_detalhe(cid: int):
    """Página de detalhe Salesforce-like."""
    path = BASE / "cliente_detail.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html",
                             headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return _em_construcao("Cliente", "cliente_detail")


# ---------------------------------------------------------------------------
# Habitação
# ---------------------------------------------------------------------------
router.get("/habitacao")(         _page("habitacao_list.html"))
router.get("/habitacao/novo")(    _page("habitacao_form.html"))


@router.get("/habitacao/{hid}/editar")
async def habitacao_editar(hid: int):
    path = BASE / "habitacao_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Ficha Habitacional", "habitacao_form")


# ---------------------------------------------------------------------------
# Proposta
# ---------------------------------------------------------------------------
router.get("/proposta")(          _page("proposta.html"))
router.get("/proposta/novo")(     _page("proposta_form_v2.html"))
router.get("/proposta/nova")(     _page("proposta_form_v2.html"))


@router.get("/proposta/{pid}/editar")
async def proposta_editar(pid: int):
    path = BASE / "proposta_form_v2.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Proposta", "proposta_form_v2")


# ---------------------------------------------------------------------------
# Termo de Parentesco
# ---------------------------------------------------------------------------
router.get("/parentesco")(         _page("parentesco_list.html"))
router.get("/parentesco/novo")(    _page("parentesco_form.html"))


@router.get("/parentesco/{pid}/editar")
async def parentesco_editar(pid: int):
    path = BASE / "parentesco_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Termo de Parentesco", "parentesco_form")


# ---------------------------------------------------------------------------
# Recibos
# ---------------------------------------------------------------------------
router.get("/recibos")(         _page("recibos_list.html"))
router.get("/recibos/novo")(    _page("recibos_form.html"))


@router.get("/recibos/{rid}/editar")
async def recibo_editar(rid: int):
    path = BASE / "recibos_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Recibo", "recibos_form")


# ---------------------------------------------------------------------------
# Financiamento
# ---------------------------------------------------------------------------
router.get("/financiamento")(          _page("financiamento_list.html"))
router.get("/financiamento/novo")(     _page("financiamento_form.html"))


@router.get("/financiamento/{fid}/editar")
async def financiamento_editar(fid: int):
    path = BASE / "financiamento_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Financiamento", "financiamento_form")


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------
router.get("/crm")(                  _page("crm_dashboard.html"))
router.get("/crm/dashboard")(        _page("crm_dashboard.html"))
router.get("/crm/kanban")(           _page("crm_kanban.html"))
router.get("/crm/leads")(            _page("crm_leads.html"))
router.get("/crm/leads/novo")(       _page("crm_lead_form.html"))
router.get("/crm/opportunities")(    _page("crm_opportunities.html"))
router.get("/crm/opportunities/novo")( _page("crm_opportunity_detail.html"))   # modo novo: todos os campos editáveis
router.get("/crm/activities")(       _page("crm_activities.html"))
router.get("/crm/activities/nova")(  _page("crm_activity_form.html"))
router.get("/crm/campaigns")(        _page("crm_campaigns.html"))
router.get("/crm/pipelines")(        _page("crm_pipelines.html"))
router.get("/crm/webhooks")(         _page("crm_webhooks.html"))
router.get("/crm/import")(           _page("crm_import.html"))

# ---------------------------------------------------------------------------
# WhatsApp (uazapi)
# ---------------------------------------------------------------------------
router.get("/chat")(                 _page("whatsapp_chat.html"))
router.get("/conexao")(              _page("whatsapp_conexao.html"))


@router.get("/crm/leads/{lid}/editar")
async def crm_lead_editar(lid: int):
    path = BASE / "crm_lead_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Lead", "crm_lead_form")


@router.get("/crm/opportunities/{oid}/editar")
async def crm_opp_editar(oid: int):
    # Página de edição removida — todos os campos são editáveis inline no detalhe.
    # Redireciona para o detalhe para não quebrar links/bookmarks antigos.
    return RedirectResponse(f"/crm/opportunities/{oid}", status_code=302)


@router.get("/crm/opportunities/{oid}")
async def crm_opp_detalhe(oid: int):
    """Página de detalhe Salesforce-like."""
    path = BASE / "crm_opportunity_detail.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html",
                             headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return _em_construcao("Oportunidade", "crm_opportunity_detail")


@router.get("/crm/activities/{aid}/editar")
async def crm_act_editar(aid: int):
    path = BASE / "crm_activity_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar Atividade", "crm_activity_form")


# ---------------------------------------------------------------------------
# Cadastros auxiliares
# ---------------------------------------------------------------------------
router.get("/cadastros/cidades")(       _page("cidades.html"))
router.get("/cadastros/agencias")(      _page("agencias.html"))
router.get("/cadastros/gerentes")(      _page("gerentes.html"))
router.get("/cadastros/parceiros")(     _page("parceiros.html"))
router.get("/cadastros/imoveis")(       _page("imoveis.html"))
router.get("/cadastros/correspondentes")(_page("correspondentes.html"))
router.get("/cadastros/corretores")(    _page("corretores.html"))
router.get("/cadastros/logos")(         _page("logos_list.html"))

# Rota PÚBLICA — cadastro aberto de corretor (sem login)
router.get("/corretor/cadastro")(       _page("corretor_publico.html"))

# ---------------------------------------------------------------------------
# Usuários + Perfis de Acesso (proteção real está no router de API)
# ---------------------------------------------------------------------------
router.get("/usuarios")(          _page("usuarios.html"))
router.get("/perfis")(            _page("perfis_list.html"))
router.get("/perfis/novo")(       _page("perfis_form.html"))
router.get("/perfis/{rid}/editar")(_page("perfis_form.html"))
