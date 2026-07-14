"""Guard de SSRF para URLs vindas do usuário.

A URL do servidor uazapi é DIGITADA na tela de conexão (`chat_integracoes.api_url`).
Sem este guard, o Portal viraria um proxy para a rede interna: bastaria cadastrar
`http://habitacao_db:5432` ou `http://169.254.169.254/` (metadata da nuvem) e o
servidor faria a requisição por quem pediu.

Puro: não resolve DNS, não faz I/O. Bloqueia o que dá para bloquear pela forma da URL.
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import ParseResult, urlparse

from app.config import settings

# Hostnames que nunca podem ser alvo, mesmo que resolvam para algo público.
_HOSTS_BLOQUEADOS = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
# Sufixos de rede interna (mDNS/Docker/k8s).
_SUFIXOS_BLOQUEADOS = (".local", ".internal", ".localdomain", ".cluster.local")


def _para_ip(host: str) -> ipaddress._BaseAddress | None:
    """Converte o host em IP, cobrindo as formas OFUSCADAS que enganam validação ingênua.

    Um atacante não escreve `127.0.0.1`. Ele escreve `2130706433` (decimal),
    `0x7f000001` (hex) ou `::ffff:127.0.0.1` (IPv4 mapeado em IPv6) — todas resolvem
    para loopback, e todas passam por um `if host == "127.0.0.1"`.
    """
    h = host.strip().strip("[]").lower()

    # IPv6 (inclui ::ffff:127.0.0.1 e ::ffff:7f00:1)
    try:
        ip = ipaddress.ip_address(h)
        # IPv4 mapeado em IPv6: avalia o IPv4 embutido, senão `is_private` mente.
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            return ip.ipv4_mapped
        return ip
    except ValueError:
        pass

    # Inteiro decimal ou hexadecimal (formas legais de escrever um IPv4)
    try:
        if re.fullmatch(r"0x[0-9a-f]+", h):
            return ipaddress.ip_address(int(h, 16))
        if re.fullmatch(r"\d+", h):
            return ipaddress.ip_address(int(h))
    except ValueError:
        pass

    return None


def _eh_host_privado(host: str) -> bool:
    h = host.strip().strip("[]").lower()

    if h in _HOSTS_BLOQUEADOS or any(h.endswith(s) for s in _SUFIXOS_BLOQUEADOS):
        return True

    ip = _para_ip(h)
    if ip is None:
        # Hostname (não IP puro). Não resolvemos DNS aqui — resolver não protege de
        # verdade contra DNS rebinding e custa I/O por request. Duas heurísticas fecham
        # os alvos mais próximos e perigosos:
        #
        # (a) Host SEM PONTO é, por definição, um nome interno (`habitacao_db`,
        #     `localhost`, um serviço do Swarm) — o Postgres de produção mora aí.
        if "." not in h:
            return True
        # (b) IPv4 dotted disfarçado de hostname: `0x7f.0.0.1`, `0177.0.0.1`, `127.0.0.1`
        #     burlam `_para_ip` (têm ponto, não são hex/decimal puros) mas o inet_aton do
        #     SO ainda os resolve para loopback. O inet_aton só trata um rótulo como
        #     numérico se for `0x`-hex ou só dígitos (decimal/octal) — um TLD real como
        #     `.cafe` (letras a-f, mas sem 0x e não-numérico) NÃO é numérico e resolve por
        #     DNS normal. Então basta bloquear quando o último rótulo é 0x-hex ou dígitos.
        ultimo_rotulo = h.rsplit(".", 1)[-1]
        if ultimo_rotulo and re.fullmatch(r"0x[0-9a-f]+|[0-9]+", ultimo_rotulo):
            return True
        return False

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local        # 169.254.x -> metadata da nuvem
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified       # 0.0.0.0
    )


def assert_url_segura(raw_url: str) -> ParseResult:
    """Valida a URL. Levanta ValueError com motivo legível se for insegura."""
    if not raw_url or not raw_url.strip():
        raise ValueError("URL vazia")

    u = urlparse(raw_url.strip())

    if u.scheme not in ("http", "https"):
        raise ValueError(f"esquema não permitido: {u.scheme or '(nenhum)'} — use http ou https")

    if not u.hostname:
        raise ValueError("URL sem host")

    # Em produção, texto claro na rede é inaceitável (o token da instância viaja no header).
    if settings.app_env == "production" and u.scheme != "https":
        raise ValueError("em produção a URL deve ser https")

    if _eh_host_privado(u.hostname):
        raise ValueError(f"host não permitido (rede interna/loopback): {u.hostname}")

    return u


def base_url_segura(raw_url: str) -> str:
    """Valida e devolve a base normalizada (sem barra final), pronta para concatenar rota."""
    u = assert_url_segura(raw_url)
    base = f"{u.scheme}://{u.netloc}{u.path}"
    return base.rstrip("/")
