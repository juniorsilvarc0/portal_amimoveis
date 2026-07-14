import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager
from pathlib import Path

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://habitacao:CHANGE_ME@habitacao_db:5432/habitacao",
)

_pool = None


def _get_pool():
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.SimpleConnectionPool(1, 10, DATABASE_URL)
    return _pool


@contextmanager
def conn():
    """Context manager: pega conexão do pool, commit no sucesso, rollback no erro."""
    connection = None
    try:
        connection = _get_pool().getconn()
    except Exception:
        connection = psycopg2.connect(DATABASE_URL)
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        try:
            _get_pool().putconn(connection)
        except Exception:
            try:
                connection.close()
            except Exception:
                pass


@contextmanager
def cursor(dict_cursor: bool = True):
    """Context manager: cursor pronto para uso, com commit/rollback automático."""
    with conn() as c:
        kwargs = {"cursor_factory": psycopg2.extras.RealDictCursor} if dict_cursor else {}
        with c.cursor(**kwargs) as cur:
            yield cur


def run_init_sql():
    """Executa init_v2.sql de forma idempotente (CREATE IF NOT EXISTS)."""
    sql_path = Path(__file__).resolve().parent.parent.parent / "init_v2.sql"
    if not sql_path.exists():
        return
    sql = sql_path.read_text()
    with conn() as c:
        with c.cursor() as cur:
            cur.execute(sql)
