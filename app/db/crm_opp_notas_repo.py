"""Repositório de notas de oportunidade."""
from .connection import cursor


def listar_por_opportunity(opportunity_id: int):
    with cursor() as cur:
        cur.execute("""
            SELECT n.*, u.email AS criado_por_email
              FROM crm_opp_notas n
              LEFT JOIN usuarios u ON u.id = n.criado_por_id
             WHERE n.opportunity_id = %s
             ORDER BY n.created_at DESC
        """, (opportunity_id,))
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM crm_opp_notas WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute("""
            INSERT INTO crm_opp_notas (opportunity_id, titulo, corpo, criado_por_id)
            VALUES (%(opportunity_id)s, %(titulo)s, %(corpo)s, %(criado_por_id)s)
            RETURNING id
        """, {
            "opportunity_id": dados["opportunity_id"],
            "titulo": dados.get("titulo"),
            "corpo": dados["corpo"],
            "criado_por_id": dados.get("criado_por_id"),
        })
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor() as cur:
        cur.execute("""
            UPDATE crm_opp_notas
               SET titulo = %(titulo)s,
                   corpo = COALESCE(%(corpo)s, corpo),
                   updated_at = NOW()
             WHERE id = %(id)s
        """, {"id": id, "titulo": dados.get("titulo"), "corpo": dados.get("corpo")})
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM crm_opp_notas WHERE id = %s", (id,))
        return cur.rowcount > 0
