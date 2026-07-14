"""Repositório de notas (Chatter) de cliente."""
from .connection import cursor


def listar_por_cliente(cliente_id: int):
    with cursor() as cur:
        cur.execute("""
            SELECT n.*, u.email AS criado_por_email
              FROM cliente_notas n
              LEFT JOIN usuarios u ON u.id = n.criado_por_id
             WHERE n.cliente_id = %s
             ORDER BY n.created_at DESC
        """, (cliente_id,))
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM cliente_notas WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute("""
            INSERT INTO cliente_notas (cliente_id, corpo, criado_por_id)
            VALUES (%(cliente_id)s, %(corpo)s, %(criado_por_id)s)
            RETURNING id
        """, dados)
        return cur.fetchone()["id"]


def deletar(id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM cliente_notas WHERE id = %s", (id,))
        return cur.rowcount > 0
