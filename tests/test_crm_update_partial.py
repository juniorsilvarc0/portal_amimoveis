"""Regressão: UPDATE parcial nos repos do CRM core (opportunities/leads/activities).

Garante que ``atualizar`` só grava as colunas presentes no dict — colunas
omitidas NÃO entram no SET e portanto NÃO são zeradas. Roda sem banco
(monkeypatch do context manager ``cursor`` de cada repo).
"""
import contextlib

import pytest

from app.db import crm_leads_repo, crm_opportunities_repo, crm_activities_repo


class _FakeCur:
    def __init__(self):
        self.sql = None
        self.params = None
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params


def _fake_cursor_factory(captured):
    @contextlib.contextmanager
    def fake_cursor(dict_cursor=True):
        cur = _FakeCur()
        captured.append(cur)
        yield cur

    return fake_cursor


# (repo, tabela, coluna_presente, coluna_omitida_sensivel)
CASOS = [
    (crm_leads_repo, "crm_leads", "nome", "cliente_id"),
    (crm_opportunities_repo, "crm_opportunities", "nome", "pac_codigo"),
    (crm_activities_repo, "crm_activities", "assunto", "opportunity_id"),
]


@pytest.mark.parametrize("repo, tabela, presente, omitida", CASOS)
def test_atualizar_parcial_nao_zera_colunas_omitidas(monkeypatch, repo, tabela, presente, omitida):
    captured = []
    monkeypatch.setattr(repo, "cursor", _fake_cursor_factory(captured))

    ok = repo.atualizar(7, {presente: "X"})

    assert ok is True
    cur = captured[-1]
    assert f"UPDATE {tabela} SET" in cur.sql
    assert f"{presente} = %({presente})s" in cur.sql
    # CRÍTICO: coluna não enviada não aparece no SET → não é sobrescrita/zerada
    assert omitida not in cur.sql
    assert cur.params == {presente: "X", "id": 7}


@pytest.mark.parametrize("repo, tabela, presente, omitida", CASOS)
def test_atualizar_dict_vazio_nao_executa(monkeypatch, repo, tabela, presente, omitida):
    captured = []
    monkeypatch.setattr(repo, "cursor", _fake_cursor_factory(captured))

    assert repo.atualizar(7, {}) is False
    assert captured == []  # nenhum UPDATE disparado
