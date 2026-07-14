import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Valores REAIS vêm do .env (gitignored) / env do container — ver .env.example.
    # Os defaults abaixo são placeholders de dev: NUNCA use em produção.
    database_url: str = "postgresql://habitacao:CHANGE_ME@habitacao_db:5432/habitacao"
    jwt_secret: str = secrets.token_hex(32)  # fallback aleatório: quebra tokens entre restarts
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    admin_password: str = "CHANGE_ME"  # só usado no seed se ainda não existir admin
    cors_origins: list[str] = [
        "https://portal.amimoveis.tec.br",
        "https://habitacao.amimoveis.tec.br",
        "https://proposta.amimoveis.tec.br",
        "http://localhost:8000",
    ]

    # URL pública do portal — usada para montar a URL do webhook registrada na uazapi.
    # Em dev, a uazapi é REMOTA e não alcança localhost: aponte para um túnel (ngrok).
    app_public_url: str = "http://localhost:8000"
    # production => o guard de SSRF passa a EXIGIR https nas URLs externas.
    app_env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
