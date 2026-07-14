"""Importador em lote de leads e oportunidades a partir de CSV."""
from __future__ import annotations

import csv
import io
from typing import Optional

from app.db import crm_leads_repo, crm_opportunities_repo


# Mapa: nome de coluna possível no CSV → campo do banco.
# Aceita variações comuns para facilitar a vida do usuário.
_LEAD_FIELD_MAP = {
    "nome": "nome", "name": "nome",
    "email": "email", "e-mail": "email",
    "telefone": "telefone", "phone": "telefone", "fone": "telefone",
    "whatsapp": "whatsapp", "wpp": "whatsapp", "celular": "whatsapp",
    "cpf_cnpj": "cpf_cnpj", "cpf": "cpf_cnpj", "cnpj": "cpf_cnpj", "documento": "cpf_cnpj",
    "origem": "origem", "source": "origem",
    "status": "status",
    "interesse": "interesse", "interest": "interesse",
    "valor_estimado": "valor_estimado", "valor": "valor_estimado",
    "observacoes": "observacoes", "observações": "observacoes", "notas": "observacoes",
}


def _normalizar_chave(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")


def _normalizar_valor(s: str):
    if s is None:
        return None
    v = s.strip()
    return v if v else None


def importar_leads_csv(file_content: bytes) -> dict:
    """Importa leads de um CSV (UTF-8). Retorna {sucesso: n, falhas: [...]}.

    Espera cabeçalho na primeira linha. Aceita variações em PT e EN.
    """
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    # Detecta delimitador
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    sucesso = 0
    falhas = []
    for i, row in enumerate(reader, start=2):  # linha 1 é cabeçalho
        try:
            dados = {}
            for col, val in row.items():
                key = _normalizar_chave(col)
                campo = _LEAD_FIELD_MAP.get(key)
                if not campo:
                    continue
                if campo == "valor_estimado":
                    v = _normalizar_valor(val)
                    if v:
                        v = v.replace("R$", "").replace(".", "").replace(",", ".").strip()
                        try:
                            dados[campo] = float(v)
                        except ValueError:
                            pass
                else:
                    dados[campo] = _normalizar_valor(val)

            if not dados.get("nome"):
                falhas.append({"linha": i, "erro": "Nome ausente"})
                continue

            crm_leads_repo.criar(dados)
            sucesso += 1
        except Exception as exc:
            falhas.append({"linha": i, "erro": str(exc)})

    return {"sucesso": sucesso, "falhas": falhas, "total": sucesso + len(falhas)}
