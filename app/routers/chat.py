"""Router do módulo WhatsApp (uazapi): conexão da instância + chat."""
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.auth.permissions import require_permission
from app.config import settings
from app.db import chat_conversas_repo, chat_integracoes_repo, chat_mensagens_repo
from app.schemas.chat import (
    ConexaoCreate,
    ConexaoRead,
    ConversaRead,
    EnviarTextoCreate,
    MensagemRead,
    QrCodeRead,
)
from app.schemas.common import MessageResponse, PagedResponse
from app.services import chat_service, uazapi_client
from app.services.uazapi_client import UazapiError

logger = logging.getLogger("portal.chat")

router = APIRouter(prefix="/api/v1/chat", tags=["WhatsApp"])


def _integracao_ativa_ou_409() -> dict:
    integ = chat_integracoes_repo.obter_ativa()
    if not integ:
        raise HTTPException(409, "WhatsApp não configurado. Configure em /conexao.")
    return integ


def _montar_webhook_url(secret: str) -> str:
    base = settings.app_public_url.rstrip("/")
    return f"{base}/api/v1/chat/webhook/uazapi?s={secret}"


# ---------------------------------------------------------------------------
# WEBHOOK — PÚBLICO
# ---------------------------------------------------------------------------

@router.post("/webhook/uazapi")
async def webhook_uazapi(request: Request, s: str | None = Query(None)):
    """Recebe os eventos da uazapi.

    PÚBLICO por construção: sem `Depends` de autenticação. O Portal não tem auth global
    (ela é por endpoint), então basta não declarar a dependência — é o mesmo padrão do
    `GET /api/v1/logos/{id}/imagem`.

    O segredo viaja na QUERY STRING (`?s=`) porque a uazapi não envia headers
    customizados. Comparação em tempo constante para não vazar o segredo por timing.
    """
    integ = chat_integracoes_repo.obter_ativa()
    if not integ:
        # 200 de propósito: sem integração, não há o que fazer — e devolver erro só faria
        # a uazapi ficar reenfileirando evento de uma instância que não é mais nossa.
        return {"ok": False, "motivo": "sem_integracao"}

    if not s or not hmac.compare_digest(s, integ["webhook_secret"] or ""):
        raise HTTPException(401, "não autorizado")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "payload inválido")

    try:
        return chat_service.processar_webhook(payload)
    except Exception as e:  # nunca deixar a exceção escapar: a uazapi reenviaria em loop
        logger.exception("[chat/webhook] falha ao processar: %s", e)
        return JSONResponse({"ok": False}, status_code=500)


# ---------------------------------------------------------------------------
# CONEXÃO
# ---------------------------------------------------------------------------

@router.get("/conexao", response_model=ConexaoRead)
async def conexao_estado(user=Depends(require_permission("chat_conexao", "ver"))):
    """Estado atual. Consulta a uazapi ao vivo (o status não é persistido)."""
    integ = chat_integracoes_repo.obter_ativa()
    if not integ:
        return {"configurada": False}

    base = {
        "configurada": True,
        "id": integ["id"],
        "api_url": integ["api_url"],
        "webhook_url": integ["webhook_url"],
        "conectado": integ["conectado"],
        "estado": integ["estado"],
        "telefone_dono": integ["telefone_dono"],
        "ultimo_erro": integ["ultimo_erro"],
    }

    try:
        st = await uazapi_client.status(integ["api_url"], integ["token"])
    except (UazapiError, ValueError) as e:
        # A instância pode estar fora do ar. Devolve o último estado conhecido + o erro,
        # em vez de derrubar a tela.
        chat_integracoes_repo.atualizar_estado(
            integ["id"], False, "unknown", None, str(e)[:300]
        )
        return {**base, "conectado": False, "estado": "unknown", "ultimo_erro": str(e)[:300]}

    chat_integracoes_repo.atualizar_estado(
        integ["id"], st["connected"], st["estado"], st.get("owner"), None
    )
    return {
        **base,
        "conectado": st["connected"],
        "estado": st["estado"],
        "telefone_dono": st.get("owner") or integ["telefone_dono"],
        "ultimo_erro": None,
    }


@router.post("/conexao", response_model=ConexaoRead, status_code=201)
async def conexao_criar(body: ConexaoCreate,
                        user=Depends(require_permission("chat_conexao", "criar"))):
    """Cadastra a instância: valida as credenciais, salva e registra o webhook."""
    if chat_integracoes_repo.obter_ativa():
        raise HTTPException(409, "Já existe uma instância configurada. Exclua-a antes de cadastrar outra.")

    # 1) A api_url é digitada pelo usuário -> guard de SSRF ANTES de qualquer fetch.
    try:
        uazapi_client.base_url_segura(body.api_url)
    except ValueError as e:
        raise HTTPException(422, f"URL inválida: {e}")

    # 2) Prova que as credenciais funcionam antes de gravar qualquer coisa.
    try:
        st = await uazapi_client.status(body.api_url, body.token)
    except UazapiError as e:
        raise HTTPException(502, f"A uazapi recusou as credenciais: {e}")

    try:
        integ_id = chat_integracoes_repo.criar(body.api_url, body.token, user.get("id"))
    except Exception as e:
        # Índice único parcial (uma ativa por provider): dois cadastros concorrentes
        # (ex.: duplo clique) — o segundo perde e recebe 409, não um 500 cru.
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Já existe uma instância configurada.")
        raise
    integ = chat_integracoes_repo.obter(integ_id)

    # 3) Registra o webhook. Se falhar, a integração fica salva (dá para re-registrar),
    #    mas o erro precisa aparecer: sem webhook, nenhuma mensagem chega.
    erro = None
    webhook_url = _montar_webhook_url(integ["webhook_secret"])
    try:
        await uazapi_client.registrar_webhook(integ["api_url"], integ["token"], webhook_url)
        chat_integracoes_repo.atualizar_webhook(integ_id, webhook_url)
    except (UazapiError, ValueError) as e:
        erro = f"Instância salva, mas o webhook NÃO foi registrado: {e}"
        logger.warning("[chat/conexao] %s", erro)

    chat_integracoes_repo.atualizar_estado(
        integ_id, st["connected"], st["estado"], st.get("owner"), erro
    )
    integ = chat_integracoes_repo.obter(integ_id)
    return {
        "configurada": True,
        "id": integ["id"],
        "api_url": integ["api_url"],
        "conectado": integ["conectado"],
        "estado": integ["estado"],
        "telefone_dono": integ["telefone_dono"],
        "webhook_url": integ["webhook_url"],
        "ultimo_erro": integ["ultimo_erro"],
    }


@router.post("/conexao/qr", response_model=QrCodeRead)
async def conexao_qr(user=Depends(require_permission("chat_conexao", "editar"))):
    """Gera o QR (ou o código de pareamento).

    ATENÇÃO: cada chamada REINICIA o socket de pareamento na uazapi. A UI deve chamar
    isto a cada ~25s (TTL do QR), NUNCA no ritmo do polling de status (3s) — senão o QR
    é substituído antes de o usuário conseguir lê-lo.
    """
    integ = _integracao_ativa_ou_409()
    try:
        return await uazapi_client.conectar(integ["api_url"], integ["token"])
    except (UazapiError, ValueError) as e:
        raise HTTPException(502, f"Falha ao gerar o QR: {e}")


@router.post("/conexao/webhook", response_model=MessageResponse)
async def conexao_registrar_webhook(user=Depends(require_permission("chat_conexao", "editar"))):
    """Re-registra o webhook. Necessário sempre que a URL pública mudar — em dev, o
    túnel (ngrok) troca de URL a cada restart."""
    integ = _integracao_ativa_ou_409()
    webhook_url = _montar_webhook_url(integ["webhook_secret"])
    try:
        await uazapi_client.registrar_webhook(integ["api_url"], integ["token"], webhook_url)
    except (UazapiError, ValueError) as e:
        raise HTTPException(502, f"Falha ao registrar o webhook: {e}")
    chat_integracoes_repo.atualizar_webhook(integ["id"], webhook_url)
    return {"mensagem": f"Webhook registrado em {webhook_url.split('?')[0]}"}


@router.post("/conexao/desconectar", response_model=MessageResponse)
async def conexao_desconectar(user=Depends(require_permission("chat_conexao", "editar"))):
    """Logout do celular. A instância e o histórico continuam; dá para reconectar pelo QR."""
    integ = _integracao_ativa_ou_409()
    try:
        await uazapi_client.desconectar(integ["api_url"], integ["token"])
    except (UazapiError, ValueError) as e:
        raise HTTPException(502, f"Falha ao desconectar: {e}")
    chat_integracoes_repo.atualizar_estado(integ["id"], False, "close", None, None)
    return {"mensagem": "WhatsApp desconectado"}


@router.delete("/conexao", response_model=MessageResponse)
async def conexao_excluir(user=Depends(require_permission("chat_conexao", "excluir"))):
    """Exclui a instância do Portal.

    APAGA conversas e mensagens (CASCADE). Os LEADS gerados por elas ficam INTACTOS —
    são dado de CRM, não de chat.
    """
    integ = _integracao_ativa_ou_409()
    try:
        await uazapi_client.desconectar(integ["api_url"], integ["token"])
    except (UazapiError, ValueError):
        pass  # a instância pode estar inacessível; a exclusão local segue
    chat_integracoes_repo.deletar(integ["id"])
    return {"mensagem": "Instância excluída. Os leads foram preservados."}


# ---------------------------------------------------------------------------
# CHAT
# ---------------------------------------------------------------------------

@router.get("/conversas", response_model=PagedResponse[ConversaRead])
async def listar_conversas(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = None,
    status: str | None = None,
    user=Depends(require_permission("chat", "ver")),
):
    rows, total = chat_conversas_repo.listar(
        page=page, per_page=per_page, search=search, status=status
    )
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    }


@router.delete("/conversas", response_model=MessageResponse)
async def limpar_historico(
    confirmar: bool = Query(False, description="Obrigatório: ?confirmar=true"),
    user=Depends(require_permission("chat", "excluir")),
):
    """Apaga TODO o histórico do chat (conversas + mensagens).

    Preserva a CONEXÃO do WhatsApp (a instância continua pareada, sem QR novo) e os
    LEADS já captados. Exige `?confirmar=true` — sem a trava, um DELETE acidental na
    coleção limparia o histórico inteiro sem querer.
    """
    if not confirmar:
        raise HTTPException(
            400, "Passe ?confirmar=true para apagar TODO o histórico de conversas e mensagens."
        )
    r = chat_conversas_repo.deletar_todas()
    logger.warning("[chat] histórico limpo por usuario_id=%s: %s conversas, %s mensagens",
                   user.get("id"), r["conversas"], r["mensagens"])
    return {"mensagem": f"Histórico limpo: {r['conversas']} conversas e {r['mensagens']} mensagens "
                        f"apagadas. Conexão do WhatsApp e leads preservados."}


@router.get("/conversas/{conversa_id}", response_model=ConversaRead)
async def obter_conversa(conversa_id: int, user=Depends(require_permission("chat", "ver"))):
    c = chat_conversas_repo.obter(conversa_id)
    if not c:
        raise HTTPException(404, "Conversa não encontrada")
    return c


@router.get("/conversas/{conversa_id}/mensagens", response_model=list[MensagemRead])
async def listar_mensagens(
    conversa_id: int,
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("chat", "ver")),
):
    if not chat_conversas_repo.obter(conversa_id):
        raise HTTPException(404, "Conversa não encontrada")
    return chat_mensagens_repo.listar(conversa_id, limit=limit)


@router.delete("/conversas/{conversa_id}", response_model=MessageResponse)
async def deletar_conversa(conversa_id: int, user=Depends(require_permission("chat", "excluir"))):
    """Apaga UMA conversa e suas mensagens. O lead vinculado é preservado."""
    if not chat_conversas_repo.deletar(conversa_id):
        raise HTTPException(404, "Conversa não encontrada")
    return {"mensagem": "Conversa apagada. O lead vinculado foi preservado."}


@router.post("/conversas/{conversa_id}/ler", response_model=MessageResponse)
async def marcar_lida(conversa_id: int, user=Depends(require_permission("chat", "editar"))):
    if not chat_conversas_repo.zerar_nao_lidas(conversa_id):
        raise HTTPException(404, "Conversa não encontrada")
    return {"mensagem": "Conversa marcada como lida"}


@router.post("/conversas/{conversa_id}/mensagens", response_model=MensagemRead, status_code=201)
async def enviar_mensagem(
    conversa_id: int,
    body: EnviarTextoCreate,
    user=Depends(require_permission("chat", "criar")),
):
    conv = chat_conversas_repo.obter(conversa_id)
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    integ = _integracao_ativa_ou_409()

    # Grava ANTES de enviar: o id vira o track_id, que volta no echo `fromMe` e permite
    # reconciliar em vez de duplicar. Se enviássemos primeiro, o echo poderia chegar
    # antes de existir uma linha para casar.
    msg_id = chat_mensagens_repo.criar_pendente(conversa_id, body.texto, user.get("id"))

    try:
        r = await uazapi_client.enviar_texto(
            integ["api_url"], integ["token"],
            # SEMPRE o external_id da conversa (derivado do chatid da uazapi). Reconstruir
            # o número a partir do lead reintroduziria o problema do 9º dígito.
            numero=conv["external_id"],
            texto=body.texto,
            track_id=str(msg_id),
        )
    except (UazapiError, ValueError) as e:
        chat_mensagens_repo.marcar_falha(msg_id, str(e))
        raise HTTPException(502, f"Falha ao enviar: {e}")

    chat_mensagens_repo.marcar_enviada(msg_id, r.get("messageid"))
    msg = chat_mensagens_repo.obter(msg_id)
    chat_conversas_repo.tocar_previa(conversa_id, body.texto, msg["mensagem_em"])
    return msg
