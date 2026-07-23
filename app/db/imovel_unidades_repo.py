"""Repositório de unidades de um imóvel (Apto 302, Casa 15...)."""
from .connection import cursor


def listar_por_imovel(imovel_id: int) -> list[dict]:
    """Unidades de um imóvel, com a flag `ocupada` = já tem oportunidade não-perdida.

    A flag alimenta a UI (marcar/desabilitar unidades já em negociação) e reflete a
    mesma regra do índice único parcial que bloqueia duplicação.
    """
    with cursor() as cur:
        cur.execute(
            """
            SELECT u.*,
                   EXISTS (
                       SELECT 1 FROM crm_opportunities o
                        WHERE o.unidade_id = u.id AND o.status <> 'perdida'
                   ) AS ocupada
              FROM imovel_unidades u
             WHERE u.imovel_id = %s
             ORDER BY u.identificador ASC
            """,
            (imovel_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def obter(id: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM imovel_unidades WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(imovel_id: int, dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO imovel_unidades (imovel_id, identificador, valor, status, observacao)
            VALUES (%(imovel_id)s, %(identificador)s, %(valor)s,
                    COALESCE(%(status)s, 'disponivel'), %(observacao)s)
            RETURNING id
            """,
            {
                "imovel_id": imovel_id,
                "identificador": dados["identificador"],
                "valor": dados.get("valor"),
                "status": dados.get("status"),
                "observacao": dados.get("observacao"),
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE imovel_unidades SET
                identificador = %s, valor = %s,
                status = COALESCE(%s, status), observacao = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (dados["identificador"], dados.get("valor"),
             dados.get("status"), dados.get("observacao"), id),
        )
        return cur.rowcount > 0


def definir_status(id: int, status: str) -> bool:
    """Sincroniza o status da unidade com o ciclo da oportunidade (reservada/vendida/
    disponivel). Chamado pelo CRM ao criar/mover oportunidade — não pelo usuário direto."""
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE imovel_unidades SET status = %s, updated_at = NOW() WHERE id = %s",
            (status, id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM imovel_unidades WHERE id = %s", (id,))
        return cur.rowcount > 0
