"""Testes do guard de SSRF.

A `api_url` da instância é DIGITADA pelo usuário na tela de conexão. Sem este guard, o
Portal viraria um proxy para a rede interna — e o atacante não escreve "127.0.0.1", ele
escreve "2130706433".
"""
import pytest

from app.config import settings
from app.services.ssrf_guard import assert_url_segura, base_url_segura


@pytest.fixture(autouse=True)
def _modo_dev(monkeypatch):
    """Fixa o ambiente em 'development' por padrão para estes testes.

    Sem isto, a suíte fica NÃO-DETERMINÍSTICA: no servidor de produção o gate roda
    com APP_ENV=production carregado do .env, e os casos que verificam URL http
    (só válida fora de produção) falhariam ali mas passariam no dev local — foi
    exatamente o que abortou um deploy. O teste que exige produção sobrescreve
    explicitamente.
    """
    monkeypatch.setattr(settings, "app_env", "development")


@pytest.mark.parametrize("url", [
    "https://spincode.uazapi.com",
    "https://api.uazapi.com/v2",
    "http://uazapi.exemplo.com.br",   # http é aceito fora de produção
])
def test_urls_publicas_passam(url):
    assert assert_url_segura(url)


@pytest.mark.parametrize("url", [
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://0.0.0.0",
    "http://10.0.0.5",
    "http://192.168.1.1",
    "http://172.16.0.1",
    "http://169.254.169.254/latest/meta-data/",   # metadata da nuvem
    "http://habitacao_db.local",
    "http://habitacao_db:5432",   # hostname Docker sem ponto = o Postgres de produção
    "http://db",
    "http://[::1]",
])
def test_rede_interna_e_bloqueada(url):
    with pytest.raises(ValueError):
        assert_url_segura(url)


@pytest.mark.parametrize("url", [
    "http://2130706433",           # 127.0.0.1 em decimal
    "http://0x7f000001",           # 127.0.0.1 em hexadecimal
    "http://[::ffff:127.0.0.1]",   # IPv4 mapeado em IPv6
    "http://0x7f.0.0.1",           # IPv4 dotted com octeto hex (inet_aton resolve p/ loopback)
    "http://127.0.0.1.nip.io.0",   # último rótulo decimal -> IP fantasiado
])
def test_loopback_ofuscado_e_bloqueado(url):
    """As formas que passam batido por um `if host == "127.0.0.1"`."""
    with pytest.raises(ValueError):
        assert_url_segura(url)


@pytest.mark.parametrize("url", [
    "https://exemplo.cafe",    # TLD só com letras a-f: NÃO é IP, resolve por DNS
    "https://uazapi.dev",      # 'dev' tem 'v' fora de [0-9a-f]
    "https://foo.face",        # 'face' é hex-like mas não é numérico p/ inet_aton
])
def test_dominios_hex_like_nao_sao_bloqueados(url):
    """A heurística anti-IP-fantasiado não pode barrar TLDs legítimos como .cafe/.face."""
    assert assert_url_segura(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x", "ftp://x", "", "sem-esquema.com"])
def test_esquema_invalido(url):
    with pytest.raises(ValueError):
        assert_url_segura(url)


def test_em_producao_exige_https(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(ValueError, match="https"):
        assert_url_segura("http://uazapi.exemplo.com")
    assert assert_url_segura("https://uazapi.exemplo.com")


def test_base_url_normaliza_sem_barra_final():
    assert base_url_segura("https://x.uazapi.com/") == "https://x.uazapi.com"
    assert base_url_segura("https://x.uazapi.com/v2/") == "https://x.uazapi.com/v2"
