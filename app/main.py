"""Portal AM Imóveis — API + frontend vanilla em FastAPI."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.auth.router import router as auth_router
from app.routers import (
    agencias,
    chat,
    cidades,
    clientes,
    correspondentes,
    corretores,
    crm,
    settings as settings_router,
    financiamentos,
    gerentes,
    habitacao,
    imoveis,
    logos,
    lookup,
    pages,
    parceiros,
    parentescos,
    propostas,
    rbac,
    recibos,
    usuarios,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("portal")

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: aplica schema v2 + garante admin seed. Shutdown: nada."""
    try:
        from app.db.connection import run_init_sql

        run_init_sql()
        logger.info("init_v2.sql aplicado (idempotente)")
    except Exception as exc:  # pragma: no cover
        logger.error("Falha ao aplicar init_v2.sql: %s", exc)

    try:
        from app.auth.jwt import hash_password
        from app.db.usuarios_repo import seed_admin_se_necessario

        seed_admin_se_necessario(hash_password(settings.admin_password))
        logger.info("seed admin OK")
    except Exception as exc:  # pragma: no cover
        logger.warning("seed admin skipped: %s", exc)

    try:
        from app.db.rbac_repo import seed_roles_e_migrar

        seed_roles_e_migrar()
        logger.info("seed RBAC (perfis padrão + migração) OK")
    except Exception as exc:  # pragma: no cover
        logger.warning("seed RBAC skipped: %s", exc)

    yield


app = FastAPI(
    title="Portal AM Imóveis",
    description="API unificada para habitação, proposta, financiamento e cadastros.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Cabeçalhos de segurança padrão em todas as respostas."""
    response: Response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    # HSTS só faz sentido sob HTTPS — Traefik termina TLS, então é sempre true em prod.
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    # Cache-bust agressivo em HTMLs, JS e CSS do frontend: sempre revalidar.
    # Imagens/fontes podem cachear normalmente.
    path = request.url.path
    if path.endswith((".html", ".js", ".css")) or path == "/" or (
        path.startswith("/") and not path.startswith("/static/") and not path.startswith("/api/")
        and "." not in path.rsplit("/", 1)[-1]
    ):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(clientes.router)
app.include_router(habitacao.router)
app.include_router(propostas.router)
app.include_router(parentescos.router)
app.include_router(financiamentos.router)
app.include_router(cidades.router)
app.include_router(agencias.router)
app.include_router(gerentes.router)
app.include_router(parceiros.router)
app.include_router(imoveis.router)
app.include_router(correspondentes.router)
app.include_router(corretores.router)
app.include_router(logos.router)
app.include_router(recibos.router)
app.include_router(crm.router)
app.include_router(chat.router)
app.include_router(settings_router.router)
app.include_router(usuarios.router)
app.include_router(rbac.router)
app.include_router(lookup.router)
app.include_router(pages.router)

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/healthz", tags=["infra"])
async def healthz():
    """Healthcheck raso (app pronto)."""
    return {"status": "ok"}


@app.get("/readyz", tags=["infra"])
async def readyz():
    """Readiness check: valida conexão com o banco."""
    try:
        from app.db.connection import conn

        with conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "ready"}
    except Exception as exc:
        return Response(
            content=f'{{"status":"not-ready","error":"{exc}"}}',
            media_type="application/json",
            status_code=503,
        )
