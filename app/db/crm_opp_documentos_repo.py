"""Repositório de documentos da oportunidade (card 10 + aba Documentos).

Cada linha é um item de documento da oportunidade: pode ser só um item de
checklist (sem arquivo) ou ter um arquivo anexado (BYTEA). Status:
``pendente | enviado | assinado | concluido``.
"""
from .connection import cursor

# colunas sem o BYTEA (lista/leitura leve) — qualificadas com d. (evita ambiguidade no JOIN)
_META = """d.id, d.opportunity_id, d.nome, d.status, d.nome_arquivo, d.content_type, d.tamanho,
           d.observacao, d.criado_por_id, d.created_at, d.updated_at,
           (d.arquivo IS NOT NULL) AS tem_arquivo"""


def listar_por_opportunity(opportunity_id: int):
    with cursor() as cur:
        cur.execute(
            f"""SELECT {_META}, u.email AS criado_por_email
                  FROM crm_opp_documentos d
                  LEFT JOIN usuarios u ON u.id = d.criado_por_id
                 WHERE d.opportunity_id = %s
                 ORDER BY d.created_at""",
            (opportunity_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"SELECT {_META} FROM crm_opp_documentos d WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def obter_arquivo(id: int):
    """Retorna (bytes, content_type, nome_arquivo) ou None."""
    with cursor() as cur:
        cur.execute(
            "SELECT arquivo, content_type, nome_arquivo, nome FROM crm_opp_documentos WHERE id = %s",
            (id,),
        )
        row = cur.fetchone()
        if not row or row["arquivo"] is None:
            return None
        return bytes(row["arquivo"]), (row["content_type"] or "application/octet-stream"), (row["nome_arquivo"] or row["nome"])


def criar(opportunity_id: int, nome: str, status: str = "pendente",
          arquivo: bytes = None, nome_arquivo: str = None, content_type: str = None,
          observacao: str = None, criado_por_id: int = None) -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO crm_opp_documentos
                   (opportunity_id, nome, status, arquivo, nome_arquivo, content_type,
                    tamanho, observacao, criado_por_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (opportunity_id, nome, status or "pendente", arquivo, nome_arquivo, content_type,
             (len(arquivo) if arquivo else None), observacao, criado_por_id),
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    """Update parcial de metadados (nome, status, observacao)."""
    campos = [c for c in ("nome", "status", "observacao") if c in dados]
    if not campos:
        return False
    sets = ", ".join(f"{c} = %({c})s" for c in campos)
    params = {c: dados.get(c) for c in campos}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE crm_opp_documentos SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def anexar_arquivo(id: int, arquivo: bytes, nome_arquivo: str, content_type: str) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """UPDATE crm_opp_documentos
                  SET arquivo = %s, nome_arquivo = %s, content_type = %s, tamanho = %s,
                      status = CASE WHEN status = 'pendente' THEN 'enviado' ELSE status END,
                      updated_at = NOW()
                WHERE id = %s""",
            (arquivo, nome_arquivo, content_type, len(arquivo), id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM crm_opp_documentos WHERE id = %s", (id,))
        return cur.rowcount > 0
