"""Catálogo canônico de recursos do RBAC — fonte única de verdade.

Cada recurso é uma "linha" da matriz de permissões; as colunas são as ações
(ver, criar, editar, excluir). Esta lista é usada por:
  - app/auth/permissions.py — validação de require_permission
  - app/db/rbac_repo.py — seed dos perfis padrão (Administrador, Somente Leitura)
  - app/routers/rbac.py — endpoint GET /api/v1/perfis/recursos (monta a matriz no front)
"""
from __future__ import annotations

# (key, label, grupo) — a ordem define a exibição na matriz do frontend.
RECURSOS: list[dict] = [
    {"key": "clientes",            "label": "Clientes",              "grupo": "Clientes"},
    {"key": "habitacao",           "label": "Habitação",             "grupo": "Documentos"},
    {"key": "proposta",            "label": "Proposta",              "grupo": "Documentos"},
    {"key": "parentesco",          "label": "Termo de Parentesco",   "grupo": "Documentos"},
    {"key": "recibo",              "label": "Recibo",                "grupo": "Documentos"},
    {"key": "financiamento",       "label": "Financiamento",         "grupo": "Financiamento"},
    {"key": "crm_leads",           "label": "CRM — Leads",           "grupo": "CRM"},
    {"key": "crm_opportunities",   "label": "CRM — Oportunidades",   "grupo": "CRM"},
    {"key": "crm_activities",      "label": "CRM — Atividades",      "grupo": "CRM"},
    {"key": "crm_campaigns",       "label": "CRM — Campanhas",       "grupo": "CRM"},
    {"key": "crm_pipelines",       "label": "CRM — Pipelines",       "grupo": "CRM"},
    {"key": "crm_webhooks",        "label": "CRM — Webhooks",        "grupo": "CRM"},
    {"key": "cad_cidades",         "label": "Cidades",               "grupo": "Cadastros"},
    {"key": "cad_agencias",        "label": "Agências",              "grupo": "Cadastros"},
    {"key": "cad_gerentes",        "label": "Gerentes",              "grupo": "Cadastros"},
    {"key": "cad_parceiros",       "label": "Parceiros",             "grupo": "Cadastros"},
    {"key": "cad_imoveis",         "label": "Imóveis",               "grupo": "Cadastros"},
    {"key": "cad_correspondentes", "label": "Correspondentes",       "grupo": "Cadastros"},
    {"key": "cad_corretores",      "label": "Corretores",            "grupo": "Cadastros"},
    {"key": "logos",               "label": "Logos",                 "grupo": "Cadastros"},
    {"key": "usuarios",            "label": "Usuários e Perfis",     "grupo": "Sistema"},
]

# Conjunto de chaves válidas (validação rápida).
RECURSO_KEYS: set[str] = {r["key"] for r in RECURSOS}

# Ações possíveis em cada recurso (colunas da matriz).
ACOES: tuple[str, ...] = ("ver", "criar", "editar", "excluir")
