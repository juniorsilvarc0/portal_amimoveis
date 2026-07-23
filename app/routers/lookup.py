"""Router de lookup leve para popular dropdowns no frontend."""
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.db import (
    cidades_repo,
    agencias_repo,
    gerentes_repo,
    parceiros_repo,
    imoveis_repo,
    imovel_unidades_repo,
    correspondentes_repo,
    corretores_repo,
)

router = APIRouter(prefix="/api/v1/lookup", tags=["Lookup"])


@router.get("/cidades")
async def lookup_cidades(user=Depends(get_current_user)):
    rows, _ = cidades_repo.listar(per_page=1000)
    return [{"id": r["id"], "nome": f'{r["nome"]}/{r["uf"]}'} for r in rows]


@router.get("/agencias")
async def lookup_agencias(user=Depends(get_current_user)):
    rows, _ = agencias_repo.listar(per_page=1000)
    return [{"id": r["id"], "nome": r["nome"]} for r in rows]


@router.get("/gerentes")
async def lookup_gerentes(
    agencia_id: int | None = None,
    user=Depends(get_current_user),
):
    rows, _ = gerentes_repo.listar(per_page=1000, agencia_id=agencia_id)
    return [{"id": r["id"], "nome": r["nome"], "agencia_nome": r.get("agencia_nome")} for r in rows]


@router.get("/parceiros")
async def lookup_parceiros(
    tipo: str | None = None,
    user=Depends(get_current_user),
):
    rows, _ = parceiros_repo.listar(per_page=1000, tipo=tipo)
    return [{"id": r["id"], "nome": r["nome"], "tipo": r["tipo"]} for r in rows]


@router.get("/imoveis")
async def lookup_imoveis(
    construtora_id: int | None = None,
    cidade_id: int | None = None,
    user=Depends(get_current_user),
):
    rows, _ = imoveis_repo.listar(per_page=1000, construtora_id=construtora_id, cidade_id=cidade_id)
    return [{"id": r["id"], "nome": r["nome"]} for r in rows]


@router.get("/unidades")
async def lookup_unidades(imovel_id: int, user=Depends(get_current_user)):
    """Unidades de um imóvel, com `ocupada` (já tem oportunidade não-perdida).

    O front usa isto no cascateamento da criação de oportunidade: lista as unidades do
    imóvel selecionado e marca as ocupadas (que a criação recusaria com 409)."""
    return [
        {"id": u["id"], "identificador": u["identificador"], "valor": u["valor"],
         "status": u["status"], "ocupada": u["ocupada"]}
        for u in imovel_unidades_repo.listar_por_imovel(imovel_id)
    ]


@router.get("/correspondentes")
async def lookup_correspondentes(user=Depends(get_current_user)):
    rows, _ = correspondentes_repo.listar(per_page=1000)
    return [{"id": r["id"], "nome": r["nome"]} for r in rows]


@router.get("/corretores")
async def lookup_corretores(user=Depends(get_current_user)):
    rows, _ = corretores_repo.listar(per_page=1000)
    return [{"id": r["id"], "nome": r["nome"], "creci": r.get("creci")} for r in rows]


# --- Endpoint público (sem auth) usado pela página aberta de cadastro de corretor ---
@router.get("/cidades-publico")
async def lookup_cidades_publico():
    """Lista de cidades pública — apenas id/nome/uf, leitura."""
    rows, _ = cidades_repo.listar(per_page=1000)
    return [{"id": r["id"], "nome": r["nome"], "uf": r["uf"]} for r in rows]


@router.get("/contadores")
async def contadores(user=Depends(get_current_user)):
    """Contadores simples para o dashboard."""
    from app.db import clientes_repo, habitacao_repo, propostas_repo, financiamentos_repo

    return {
        "clientes": clientes_repo.listar(per_page=1)[1],
        "habitacao": habitacao_repo.listar(per_page=1)[1],
        "propostas": propostas_repo.listar(per_page=1)[1],
        "financiamentos": financiamentos_repo.listar(per_page=1)[1],
    }
