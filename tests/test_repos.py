import os
import pytest

pytestmark = pytest.mark.db


def test_connection_open(test_db_url):
    os.environ["DATABASE_URL"] = test_db_url
    from app.db.connection import conn
    with conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1


def test_init_sql_runs(test_db_url):
    os.environ["DATABASE_URL"] = test_db_url
    from app.db.connection import run_init_sql, conn
    run_init_sql()
    with conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT to_regclass('clientes')")
            assert cur.fetchone()[0] is not None


def test_cliente_upsert(test_db_url):
    os.environ["DATABASE_URL"] = test_db_url
    from app.db.clientes_repo import upsert_por_cpf, obter_por_cpf
    cid = upsert_por_cpf({"cpf": "11122233344", "nome": "Fulano"})
    assert cid > 0
    c = obter_por_cpf("11122233344")
    assert c and c["nome"] == "Fulano"
