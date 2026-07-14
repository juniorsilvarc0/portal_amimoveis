"""Repositório de configurações chave/valor da aplicação."""
from .connection import cursor


def get(key: str, default: str | None = None) -> str | None:
    with cursor() as cur:
        cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
        row = cur.fetchone()
        if row:
            return row["value"]
        return default


def set(key: str, value: str) -> None:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "INSERT INTO app_settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            (key, value),
        )


def get_bool(key: str, default: bool = False) -> bool:
    v = get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("true", "1", "yes", "on", "sim")


def set_bool(key: str, value: bool) -> None:
    set(key, "true" if value else "false")
