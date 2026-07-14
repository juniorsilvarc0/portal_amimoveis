import pytest


def test_cliente_schema_accepts_valid():
    from app.schemas.cliente import ClienteCreate
    c = ClienteCreate(cpf="12345678900", nome="João")
    assert c.cpf == "12345678900"
    assert c.nome == "João"


def test_cliente_schema_rejects_short_cpf():
    from app.schemas.cliente import ClienteCreate
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ClienteCreate(cpf="123", nome="X")


def test_parceiro_tipo_enum():
    from app.schemas.parceiro import ParceiroCreate
    p = ParceiroCreate(nome="ACME", tipo="CONSTRUTORA", cidade_id=1)
    assert p.tipo == "CONSTRUTORA"


def test_parceiro_tipo_invalid():
    from app.schemas.parceiro import ParceiroCreate
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ParceiroCreate(nome="X", tipo="BANCO", cidade_id=1)


def test_financiamento_analise_default():
    from app.schemas.financiamento import FinanciamentoCreate
    f = FinanciamentoCreate(cliente_id=1)
    assert f.analise in (None, "PENDENTE")
