"""Repositório RBAC — perfis de acesso (rbac_roles) e matriz de permissões
(rbac_role_permissions). Inclui seed dos perfis padrão e migração dos usuários
legados (perfil admin/usuario → role_id)."""
from __future__ import annotations

from .connection import cursor
from app.auth.recursos import ACOES, RECURSOS, RECURSO_KEYS


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def listar_roles() -> list[dict]:
    """Lista perfis com contagem de usuários vinculados."""
    sql = """
        SELECT r.*, COALESCE(u.cnt, 0) AS usuarios_count
          FROM rbac_roles r
          LEFT JOIN (
              SELECT role_id, COUNT(*) AS cnt
                FROM usuarios WHERE ativo = TRUE GROUP BY role_id
          ) u ON u.role_id = r.id
         ORDER BY r.is_system DESC, r.nome ASC
    """
    with cursor() as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def obter_role(role_id: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM rbac_roles WHERE id = %s", (role_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def obter_role_por_nome(nome: str) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM rbac_roles WHERE nome = %s", (nome,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_permissions_for_role(role_id: int) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            "SELECT recurso, ver, criar, editar, excluir "
            "FROM rbac_role_permissions WHERE role_id = %s",
            (role_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def contar_usuarios(role_id: int) -> int:
    with cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM usuarios WHERE role_id = %s AND ativo = TRUE",
            (role_id,),
        )
        return cur.fetchone()["c"]


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def _upsert_permissoes(cur, role_id: int, permissoes: list[dict]) -> None:
    """Aplica a matriz (lista de {recurso, ver, criar, editar, excluir})."""
    for p in permissoes or []:
        recurso = p.get("recurso")
        if recurso not in RECURSO_KEYS:
            continue
        vals = {a: bool(p.get(a)) for a in ACOES}
        cur.execute(
            """
            INSERT INTO rbac_role_permissions (role_id, recurso, ver, criar, editar, excluir)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (role_id, recurso) DO UPDATE
               SET ver = EXCLUDED.ver, criar = EXCLUDED.criar,
                   editar = EXCLUDED.editar, excluir = EXCLUDED.excluir
            """,
            (role_id, recurso, vals["ver"], vals["criar"], vals["editar"], vals["excluir"]),
        )


def criar_role(nome: str, descricao: str | None, permissoes: list[dict]) -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO rbac_roles (nome, descricao) VALUES (%s, %s) RETURNING id",
            (nome, descricao),
        )
        role_id = cur.fetchone()["id"]
        _upsert_permissoes(cur, role_id, permissoes)
        return role_id


def atualizar_role(role_id: int, nome: str, descricao: str | None, permissoes: list[dict]) -> bool:
    with cursor() as cur:
        cur.execute(
            "UPDATE rbac_roles SET nome = %s, descricao = %s, updated_at = NOW() WHERE id = %s",
            (nome, descricao, role_id),
        )
        if cur.rowcount == 0:
            return False
        _upsert_permissoes(cur, role_id, permissoes)
        return True


def deletar_role(role_id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM rbac_roles WHERE id = %s", (role_id,))
        return cur.rowcount > 0


def atribuir_role_usuario(usuario_id: int, role_id: int) -> None:
    with cursor(dict_cursor=False) as cur:
        cur.execute("UPDATE usuarios SET role_id = %s WHERE id = %s", (role_id, usuario_id))


# ---------------------------------------------------------------------------
# Seed + migração (idempotente, roda no startup)
# ---------------------------------------------------------------------------

def _set_all_permissoes(cur, role_id: int, valor: bool, *, somente_ver: bool = False) -> None:
    for r in RECURSOS:
        ver = True if (valor or somente_ver) else False
        write = valor and not somente_ver
        cur.execute(
            """
            INSERT INTO rbac_role_permissions (role_id, recurso, ver, criar, editar, excluir)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (role_id, recurso) DO UPDATE
               SET ver = EXCLUDED.ver, criar = EXCLUDED.criar,
                   editar = EXCLUDED.editar, excluir = EXCLUDED.excluir
            """,
            (role_id, r["key"], ver, write, write, write),
        )


def seed_roles_e_migrar() -> None:
    """Garante os perfis padrão e migra usuários legados sem role_id."""
    with cursor() as cur:
        # Administrador (sistema, acesso total)
        cur.execute("SELECT id FROM rbac_roles WHERE is_system = TRUE LIMIT 1")
        row = cur.fetchone()
        if row:
            admin_id = row["id"]
        else:
            cur.execute(
                "INSERT INTO rbac_roles (nome, descricao, is_system) "
                "VALUES ('Administrador', 'Acesso total ao sistema (perfil protegido).', TRUE) "
                "RETURNING id"
            )
            admin_id = cur.fetchone()["id"]
        # Mantém o Administrador sempre com tudo marcado.
        _set_all_permissoes(cur, admin_id, True)

        # Somente Leitura (vê tudo, não escreve)
        cur.execute("SELECT id FROM rbac_roles WHERE nome = 'Somente Leitura'")
        row = cur.fetchone()
        if row:
            leitura_id = row["id"]
        else:
            cur.execute(
                "INSERT INTO rbac_roles (nome, descricao) "
                "VALUES ('Somente Leitura', 'Visualiza todos os módulos, sem permissão de escrita.') "
                "RETURNING id"
            )
            leitura_id = cur.fetchone()["id"]
            _set_all_permissoes(cur, leitura_id, False, somente_ver=True)

        # Migração: usuários sem role_id herdam pelo perfil legado.
        cur.execute(
            "UPDATE usuarios SET role_id = %s WHERE role_id IS NULL AND perfil = 'admin'",
            (admin_id,),
        )
        cur.execute(
            "UPDATE usuarios SET role_id = %s WHERE role_id IS NULL AND perfil <> 'admin'",
            (leitura_id,),
        )


def get_admin_role_id() -> int | None:
    with cursor() as cur:
        cur.execute("SELECT id FROM rbac_roles WHERE is_system = TRUE LIMIT 1")
        row = cur.fetchone()
        return row["id"] if row else None
