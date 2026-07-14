"""Repositório de logos (imagens para documentos PDF)."""
from .connection import cursor


def listar():
    sql = "SELECT id, nome, content_type, created_at FROM logos ORDER BY nome"
    with cursor() as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT id, nome, content_type, created_at FROM logos WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def obter_imagem(id: int):
    """Retorna (bytes, content_type) ou None."""
    with cursor() as cur:
        cur.execute("SELECT arquivo, content_type FROM logos WHERE id = %s", (id,))
        row = cur.fetchone()
        if not row:
            return None
        return bytes(row["arquivo"]), row["content_type"]


def criar(nome: str, arquivo: bytes, content_type: str) -> int:
    sql = "INSERT INTO logos (nome, arquivo, content_type) VALUES (%s, %s, %s) RETURNING id"
    with cursor() as cur:
        cur.execute(sql, (nome, arquivo, content_type))
        return cur.fetchone()["id"]


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM logos WHERE id = %s", (id,))
        return cur.rowcount > 0
