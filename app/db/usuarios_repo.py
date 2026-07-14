"""Repositório de usuários (tabela: usuarios — compartilhada com Flask legacy)."""
from .connection import cursor

_COLS_PUBLIC = (
    "u.id, u.nome, u.email, u.perfil, u.role_id, u.ativo, u.created_at, "
    "r.nome AS role_nome"
)
_FROM = "FROM usuarios u LEFT JOIN rbac_roles r ON r.id = u.role_id"


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (u.nome ILIKE %s OR u.email ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]

    perfil = filters.get("perfil")
    if perfil:
        where += " AND u.perfil = %s"
        params.append(perfil)

    role_id = filters.get("role_id")
    if role_id:
        where += " AND u.role_id = %s"
        params.append(role_id)

    ativo = filters.get("ativo")
    if ativo is not None:
        where += " AND u.ativo = %s"
        params.append(ativo)

    count_sql = f"SELECT COUNT(*) FROM usuarios u {where}"
    list_sql = (
        f"SELECT {_COLS_PUBLIC} {_FROM} {where} "
        f"ORDER BY u.created_at DESC LIMIT %s OFFSET %s"
    )

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(
            f"SELECT {_COLS_PUBLIC} {_FROM} WHERE u.id = %s",
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def obter_por_email(email: str):
    """Retorna usuário ativo pelo e-mail (inclui senha_hash para autenticação)."""
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM usuarios WHERE email = %s AND ativo = TRUE",
            (email,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios (nome, email, senha_hash, perfil, role_id)
            VALUES (%(nome)s, %(email)s, %(senha_hash)s, %(perfil)s, %(role_id)s)
            RETURNING id
            """,
            {
                "nome": dados["nome"],
                "email": dados["email"],
                "senha_hash": dados["senha_hash"],
                "perfil": dados.get("perfil", "usuario"),
                "role_id": dados.get("role_id"),
            },
        )
        return cur.fetchone()["id"]


_USUARIO_ALLOWED = ["nome", "email", "perfil", "role_id", "senha_hash", "ativo"]


def atualizar(id: int, dados: dict) -> bool:
    """Update PARCIAL: só atualiza colunas presentes no dict."""
    campos_presentes = [f for f in _USUARIO_ALLOWED if f in dados]
    if not campos_presentes:
        return False

    sets = ", ".join(f"{c} = %({c})s" for c in campos_presentes)
    params = {c: dados.get(c) for c in campos_presentes}
    params["id"] = id

    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE usuarios SET {sets} WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    """Soft delete: marca ativo = FALSE."""
    with cursor(dict_cursor=False) as cur:
        cur.execute("UPDATE usuarios SET ativo = FALSE WHERE id = %s", (id,))
        return cur.rowcount > 0


def seed_admin_se_necessario(senha_hash: str):
    """Cria admin@roper.com se não existir nenhum admin ativo."""
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM usuarios WHERE perfil = 'admin' AND ativo = TRUE"
        )
        count = cur.fetchone()[0]

    if count == 0:
        criar(
            {
                "nome": "Administrador",
                "email": "admin@roper.com",
                "senha_hash": senha_hash,
                "perfil": "admin",
            }
        )
