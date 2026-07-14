"""PDF service for the FastAPI app layer.

Adapted from services/pdf_service.py (the original Flask-era service).
BASE_DIR now points to the project root (parent of app/).
"""
import asyncio
import os
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# A4 = 210mm x 297mm
# Margins: 15mm horizontal, 10mm vertical
MARGIN_H = 15  # mm
MARGIN_V = 10  # mm
A4_W_MM = 210
A4_H_MM = 297
USABLE_W_PX = int((A4_W_MM - 2 * MARGIN_H) * 96 / 25.4)  # ~680px
USABLE_H_PX = int((A4_H_MM - 2 * MARGIN_V) * 96 / 25.4)  # ~1047px


async def _gerar_pdf(html_content: str) -> bytes:
    """Gera PDF a partir de HTML usando Playwright (headless Chromium)."""
    browser = None
    tmp_path = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            page = await browser.new_page(
                viewport={"width": USABLE_W_PX, "height": 1200}
            )

            fd, tmp_path = tempfile.mkstemp(suffix=".html", dir=str(STATIC_DIR))
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(html_content)

            await page.goto(f"file://{tmp_path}", wait_until="networkidle")

            try:
                await page.evaluate("() => document.fonts.ready")
            except Exception:
                pass

            content_h = await page.evaluate(
                "() => document.getElementById('wrap').scrollHeight"
            )

            scale = 1.0
            if content_h > USABLE_H_PX:
                scale = USABLE_H_PX / content_h
                scale = max(0.6, scale)

            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                scale=scale,
                margin={
                    "top": f"{MARGIN_V}mm",
                    "right": f"{MARGIN_H}mm",
                    "bottom": f"{MARGIN_V}mm",
                    "left": f"{MARGIN_H}mm",
                },
                prefer_css_page_size=False,
            )

            # Safety: se ainda deu 2+ páginas, reduz mais
            if pdf_bytes.count(b"/Type /Page\n") > 1:
                scale *= 0.82
                pdf_bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    scale=max(0.5, scale),
                    margin={
                        "top": f"{MARGIN_V}mm",
                        "right": f"{MARGIN_H}mm",
                        "bottom": f"{MARGIN_V}mm",
                        "left": f"{MARGIN_H}mm",
                    },
                    prefer_css_page_size=False,
                )

            await browser.close()
            browser = None
            return pdf_bytes

    finally:
        if browser:
            await browser.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def gerar_pdf(html_content: str) -> bytes:
    """Wrapper síncrono para geração de PDF."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _gerar_pdf(html_content)).result()
    else:
        return asyncio.run(_gerar_pdf(html_content))


# ---------------------------------------------------------------------------
# Funções de alto nível para cada módulo
# ---------------------------------------------------------------------------

def gerar_pdf_habitacao(ficha: dict) -> bytes:
    """Renderiza template ficha_habitacional.html com os dados e gera PDF.

    ficha é um dict com cliente + dados de processo. Faz o mapeamento para o
    template que espera campos flat (proponente1_nome, etc).
    """
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("ficha_habitacional.html")
    context = _map_habitacao_to_template(ficha)
    return gerar_pdf(template.render(**context))


def _format_data_br(raw) -> str:
    """Converte 'YYYY-MM-DD' (ou date) para 'DD/MM/YYYY'. Qualquer outro formato passa direto."""
    if not raw:
        return ""
    s = str(raw)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def _format_cpf(raw: str) -> str:
    """000.000.000-00 se tiver 11 dígitos, senão devolve como está."""
    if not raw:
        return ""
    import re
    d = re.sub(r"\D", "", raw)
    if len(d) != 11:
        return raw
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def _map_habitacao_to_template(ficha: dict) -> dict:
    """Mapeia schema novo (cliente_id, titular_*, conjuge_*) para os 46 campos flat do template antigo."""
    ficha = ficha or {}
    return {
        "proponente1_nome": ficha.get("cliente_nome") or "",
        "proponente1_idade": ficha.get("idade_snapshot") or "",
        "proponente1_cpf": _format_cpf(ficha.get("cliente_cpf")),
        # Linha "2.COOBRIGADO/IDADE" do PDF agora usa o nome do cônjuge/2º proponente
        # (campo coobrigado_nome do form foi removido e unificado com conjuge_nome).
        # Fallback para coobrigado_nome legado (fichas antigas).
        "coobrigado_nome": ficha.get("conjuge_nome") or ficha.get("coobrigado_nome") or "",
        "coobrigado_cpf": _format_cpf(ficha.get("conjuge_cpf")),
        "dependentes": ficha.get("dependentes") or "",
        "contato_telefone": ficha.get("cliente_whatsapp1") or "",
        "contato_email": ficha.get("cliente_email") or "",
        "prop1_nome": ficha.get("cliente_nome") or "",
        "prop1_funcao": ficha.get("titular_funcao") or "",
        "prop1_empresa": ficha.get("titular_empresa") or "",
        "prop1_admissao": _format_data_br(ficha.get("titular_admissao")),
        "prop1_renda_bruta": ficha.get("titular_renda_bruta") or "",
        "prop1_renda_liquida": ficha.get("titular_renda_liquida") or "",
        "prop1_extras": ficha.get("titular_extras") or "",
        "prop2_nome": ficha.get("conjuge_nome") or "",
        "prop2_funcao": ficha.get("conjuge_funcao") or "",
        "prop2_empresa": ficha.get("conjuge_empresa") or "",
        "prop2_admissao": _format_data_br(ficha.get("conjuge_admissao")),
        "prop2_renda_bruta": ficha.get("conjuge_renda_bruta") or "",
        "prop2_renda_liquida": ficha.get("conjuge_renda_liquida") or "",
        "prop2_extras": ficha.get("conjuge_extras") or "",
        "emprestimos": ficha.get("emprestimos") or "",
        "moradia_tipo": ficha.get("moradia_tipo") or "",
        "transportes": ficha.get("transportes") or "",
        "conta": ficha.get("conta") or "",
        "conta_salario": ficha.get("conta_salario") or "",
        "open_finance": ficha.get("open_finance") or "",
        "opt_in": ficha.get("opt_in") or "",
        "biometria": ficha.get("biometria") or "",
        "cartao_credito": ficha.get("cartao_credito") or "",
        "crot": ficha.get("crot") or "",
        "valor_total": ficha.get("valor_total") or "",
        "subsidio": ficha.get("subsidio") or "",
        "entrada": ficha.get("entrada") or "",
        "negociacao": ficha.get("negociacao") or "",
        "financiado": ficha.get("financiado") or "",
        "parcela": ficha.get("parcela") or "",
        "prazo": ficha.get("prazo") or "",
        "amortizacao": ficha.get("amortizacao") or "",
        "utilizar_fgts": ficha.get("utilizar_fgts") or "",
        "endereco_imovel": ficha.get("endereco_imovel") or "",
        "proprietarios": ficha.get("proprietarios") or "",
        "construtora": ficha.get("construtora_nome") or "",
        "proprietarios_construtora": ficha.get("proprietarios_construtora") or "",
        "taxa_vista_contrato": ficha.get("taxa_vista_contrato") or "",
        "seguridade": ficha.get("seguridade") or "",
        "empreendimento": ficha.get("empreendimento") or "",
    }


def gerar_pdf_proposta(proposta: dict) -> bytes:
    """Renderiza template proposta_imoveis.html. A proposta já deve vir com
    cliente + cônjuge + lista de pagamentos nested."""
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("proposta_imoveis.html")
    ctx = _map_proposta_to_template(proposta)
    ctx["logo_path"] = str(STATIC_DIR / "logoAM.png")
    return gerar_pdf(template.render(**ctx))


def gerar_pdf_parentesco(termo: dict) -> bytes:
    """Renderiza declaração CAIXA de parentesco/residência/ausência de renda."""
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("parentesco.html")
    ctx = _map_parentesco_to_template(termo)
    ctx["logo_caixa_path"] = str(STATIC_DIR / "logoCaixa.png")
    return gerar_pdf(template.render(**ctx))


def _map_parentesco_to_template(t: dict) -> dict:
    t = t or {}
    return {
        "parente_nome":         t.get("parente_nome") or "",
        "parente_cpf":          _format_cpf(t.get("parente_cpf")),
        "parente_estado_civil": t.get("parente_estado_civil") or "",
        "grau_parentesco":      t.get("grau_parentesco") or "",
        "conjuge_parente_nome": t.get("conjuge_parente_nome") or "",
        "proponente_nome":      t.get("cliente_nome") or "",
        "proponente_cpf":       _format_cpf(t.get("cliente_cpf")),
        "data_declaracao":      _format_data_br(t.get("data_declaracao")),
    }


def _map_proposta_to_template(p: dict) -> dict:
    """Mapeia proposta v2 (normalizada) para os campos flat do template."""
    p = p or {}
    ctx = {
        "empreendimento": p.get("empreendimento") or "",
        "unidade": p.get("unidade") or "",
        "valor_total": p.get("valor_total") or "",
        "prop_nome": p.get("cliente_nome") or "",
        "prop_nacionalidade": p.get("cliente_nacionalidade") or "",
        "prop_estado_civil": p.get("cliente_estado_civil") or "",
        "prop_regime": p.get("cliente_regime_bens") or "",
        "prop_nasc": str(p.get("cliente_nascimento") or ""),
        "prop_profissao": p.get("cliente_profissao") or "",
        "prop_rg": p.get("cliente_rg") or "",
        "prop_rg_orgao": p.get("cliente_rg_orgao") or "",
        "prop_cpf": _format_cpf(p.get("cliente_cpf")),
        "prop_endereco": p.get("cliente_endereco") or "",
        "prop_bairro": p.get("cliente_bairro") or "",
        "prop_cep": p.get("cliente_cep") or "",
        "prop_cidade": p.get("cliente_cidade_nome") or "",
        "prop_fixo": p.get("cliente_telefone_fixo") or "",
        "prop_whats1": p.get("cliente_whatsapp1") or "",
        "prop_whats2": p.get("cliente_whatsapp2") or "",
        "prop_email": p.get("cliente_email") or "",
        "conj_nome": p.get("conjuge_nome") or "",
        "conj_nacionalidade": p.get("conjuge_nacionalidade") or "",
        "conj_estado_civil": p.get("conjuge_estado_civil") or "",
        "conj_nasc": str(p.get("conjuge_nascimento") or ""),
        "conj_profissao": p.get("conjuge_profissao") or "",
        "conj_rg": p.get("conjuge_rg") or "",
        "conj_rg_orgao": p.get("conjuge_rg_orgao") or "",
        "conj_cpf": _format_cpf(p.get("conjuge_cpf")),
        "conj_whats": p.get("conjuge_whatsapp") or "",
        "conj_fixo": p.get("conjuge_fixo") or "",
        "conj_email": p.get("conjuge_email") or "",
        "observacoes": p.get("observacoes") or "",
        "validade": p.get("validade") or "",
        "corretor_nome": p.get("corretor_nome") or "",
        "corretor_creci": p.get("corretor_creci") or "",
        "data_dia": p.get("data_dia") or "",
        "data_mes": p.get("data_mes") or "",
        "data_ano": p.get("data_ano") or "",
    }
    # Mapeia pagamentos para campos flat pg_<chave>_<col>
    key_map = {
        "Sinal": "sinal",
        "Parcelamento do sinal": "parcsinal",
        "Parcelas mensais": "parcelas",
        "1ª Intercalada": "inter1",
        "2ª Intercalada": "inter2",
        "3ª Intercalada": "inter3",
        "Subsídio": "subsidio",
        "Financiamento": "fin",
    }
    for k in key_map.values():
        for col in ("qtd", "valor", "total", "forma", "venc"):
            ctx[f"pg_{k}_{col}"] = ""
    for pag in (p.get("pagamentos") or []):
        desc = pag.get("descricao") or ""
        k = key_map.get(desc)
        if not k:
            continue
        ctx[f"pg_{k}_qtd"] = pag.get("quantidade") or ""
        ctx[f"pg_{k}_valor"] = pag.get("valor_parcela") or ""
        ctx[f"pg_{k}_total"] = pag.get("valor_total") or ""
        ctx[f"pg_{k}_forma"] = pag.get("forma") or ""
        ctx[f"pg_{k}_venc"] = pag.get("vencimento") or ""
    return ctx


# ---------------------------------------------------------------------------
# Recibo
# ---------------------------------------------------------------------------

def _valor_por_extenso(valor) -> str:
    """Converte valor numérico para texto em PT-BR (ex: 'quatorze mil e setecentos reais')."""
    if not valor:
        return ""
    try:
        from num2words import num2words
        v = float(valor)
        extenso = num2words(v, lang='pt_BR', to='currency')
        return extenso.capitalize()
    except Exception:
        return ""


def _format_valor_br(valor) -> str:
    """Formata valor numérico para moeda BR sem R$ (ex: '14.700,00')."""
    if not valor:
        return ""
    try:
        v = float(valor)
        formatted = f"{v:,.2f}"
        # Troca separadores: 14,700.00 → 14.700,00
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except Exception:
        return str(valor)


def _format_cnpj(raw: str) -> str:
    """00.000.000/0000-00 se tiver 14 dígitos."""
    if not raw:
        return ""
    import re
    d = re.sub(r"\D", "", raw)
    if len(d) != 14:
        return raw
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def gerar_pdf_recibo(recibo: dict, logo_bytes: bytes = None, logo_content_type: str = None) -> bytes:
    """Renderiza template recibo.html com os dados e gera PDF."""
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("recibo.html")
    ctx = _map_recibo_to_template(recibo)

    # Logo como data URI (inline no HTML para file:// funcionar)
    if logo_bytes and logo_content_type:
        import base64
        b64 = base64.b64encode(logo_bytes).decode("ascii")
        ctx["logo_data_uri"] = f"data:{logo_content_type};base64,{b64}"
    else:
        ctx["logo_data_uri"] = ""

    return gerar_pdf(template.render(**ctx))


def _format_doc(raw: str) -> str:
    """Formata CPF (11 dígitos) ou CNPJ (14 dígitos) automaticamente."""
    if not raw:
        return ""
    import re
    d = re.sub(r"\D", "", raw)
    if len(d) == 11:
        return _format_cpf(raw)
    if len(d) == 14:
        return _format_cnpj(raw)
    return raw


def _doc_label(raw: str) -> str:
    """Retorna 'CPF' ou 'CNPJ' conforme quantidade de dígitos."""
    if not raw:
        return "CPF"
    import re
    d = re.sub(r"\D", "", raw)
    return "CNPJ" if len(d) == 14 else "CPF"


def _formas_pagamento_breakdown(d: dict) -> tuple:
    """Normaliza formas_pagamento (lista de {forma, valor}) e devolve
    (lista_formatada, frase_pagamento).

    A frase já vem com o separador inicial pronto para concatenar após o
    valor por extenso no corpo do recibo. Ex:
      0 formas, com forma_pagamento legado → ' via Pix'
      1 forma  → ' via Pix'
      2+ formas → ', sendo R$900,00 via Pix e R$100,00 via cartão de crédito'
    """
    import json as _json

    formas_raw = d.get("formas_pagamento")
    if isinstance(formas_raw, str):
        try:
            formas_raw = _json.loads(formas_raw)
        except Exception:
            formas_raw = None

    lista = []
    if isinstance(formas_raw, list):
        for item in formas_raw:
            if not isinstance(item, dict):
                continue
            forma = (item.get("forma") or "").strip()
            valor = item.get("valor")
            if not forma and not valor:
                continue
            lista.append({"forma": forma, "valor_fmt": _format_valor_br(valor)})

    partes = [
        f"R$ {f['valor_fmt']} via {f['forma']}"
        for f in lista
        if f["valor_fmt"] and f["forma"]
    ]

    if len(partes) >= 2:
        frase = ", sendo " + (", ".join(partes[:-1]) + " e " + partes[-1])
    elif len(lista) == 1 and lista[0]["forma"]:
        frase = " via " + lista[0]["forma"]
    elif d.get("forma_pagamento"):
        frase = " via " + str(d.get("forma_pagamento"))
    else:
        frase = ""

    return lista, frase


def _map_recibo_to_template(d: dict) -> dict:
    d = d or {}
    # Recebedor = quem assina (mesmo campo)
    assinatura_nome = d.get("assinatura_nome") or ""
    doc_recebedor = d.get("doc_recebedor") or ""
    doc_pagador = d.get("doc_pagador") or ""
    formas_lista, pagamento_frase = _formas_pagamento_breakdown(d)
    return {
        "numero_contrato":       d.get("numero_contrato") or "",
        "data_recibo":           _format_data_br(d.get("data_recibo")),
        "valor_cabecalho_fmt":   _format_valor_br(d.get("valor_recebido")),
        "valor_cabecalho_extenso": _valor_por_extenso(d.get("valor_recebido")),
        "valor_recebido_fmt":    _format_valor_br(d.get("valor_recebido")),
        "valor_recebido_extenso": _valor_por_extenso(d.get("valor_recebido")),
        "nome_recebedor":        assinatura_nome,
        "doc_recebedor_label":   _doc_label(doc_recebedor),
        "doc_recebedor_fmt":     _format_doc(doc_recebedor),
        "nome_pagador":          d.get("nome_pagador") or "",
        "doc_pagador_label":     _doc_label(doc_pagador),
        "doc_pagador_fmt":       _format_doc(doc_pagador),
        "forma_pagamento":       d.get("forma_pagamento") or "",
        "formas_lista":          formas_lista,
        "pagamento_frase":       pagamento_frase,
        "descricao_referencia":  d.get("descricao_referencia") or "",
        "cidade":                d.get("cidade_nome") or "",
        "uf":                    d.get("cidade_uf") or "",
        "data_local":            _format_data_br(d.get("data_local")),
        "assinatura_nome":       assinatura_nome,
        "doc_assinatura_label":  _doc_label(doc_recebedor),
        "doc_assinatura_fmt":    _format_doc(doc_recebedor),
        "rodape_texto":          d.get("rodape_texto") or "",
        "observacoes":           d.get("observacoes") or "",
    }
