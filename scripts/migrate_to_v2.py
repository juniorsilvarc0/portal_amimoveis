#!/usr/bin/env python3
"""Migra fichas (schema legado Flask) para clientes + habitacao_fichas + conjuges (schema v2).

Uso dentro do container portal:

    python /tmp/migrate_to_v2.py              # dry-run (default) — rollback no final
    python /tmp/migrate_to_v2.py --execute    # commita de verdade

Regras:
- CPF normalizado (só dígitos). 11 dígitos = válido; senão cpf_pendente=true + CPF sintético.
- Dedupe por CPF: se já existe cliente, aplica "última vence" em campos mutáveis
  (email, whatsapp1, whatsapp2, telefone_fixo, endereco, bairro, cep, profissao,
  observacoes) — conflitos logados em /tmp/migration_conflicts.csv.
- Nome do cliente: primeira ficha vence (preserva nome original).
- Cônjuge: se prop2_nome presente, upsert em conjuges (1:1 com cliente).
- Idempotência: coluna habitacao_fichas.legacy_ficha_id guarda o id original da ficha;
  re-execuções pulam fichas já migradas.
"""

import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

LOG = logging.getLogger("migrate")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://habitacao:CHANGE_ME@habitacao_db:5432/habitacao",
)

MUTABLE_FIELDS = [
    "email", "whatsapp1", "whatsapp2", "telefone_fixo",
    "endereco", "bairro", "cep", "profissao", "observacoes",
]


def cpf_digits(raw):
    return re.sub(r"\D", "", raw or "")


def non_empty(v):
    s = (v or "").strip() if isinstance(v, str) else v
    return s or None


def ficha_to_cliente(f):
    return {
        "nome": (f.get("proponente1_nome") or "").strip() or "SEM NOME",
        "email": non_empty(f.get("contato_email")),
        "whatsapp1": non_empty(f.get("contato_telefone")),
    }


def ficha_to_habitacao(f, cliente_id):
    g = lambda k: non_empty(f.get(k))
    return {
        "cliente_id": cliente_id,
        "empreendimento": g("empreendimento"),
        "idade_snapshot": g("proponente1_idade"),
        "dependentes": g("dependentes"),
        "coobrigado_nome": g("coobrigado_nome"),
        "titular_funcao": g("prop1_funcao"),
        "titular_empresa": g("prop1_empresa"),
        "titular_admissao": g("prop1_admissao"),
        "titular_renda_bruta": g("prop1_renda_bruta"),
        "titular_renda_liquida": g("prop1_renda_liquida"),
        "titular_extras": g("prop1_extras"),
        "conjuge_funcao": g("prop2_funcao"),
        "conjuge_empresa": g("prop2_empresa"),
        "conjuge_admissao": g("prop2_admissao"),
        "conjuge_renda_bruta": g("prop2_renda_bruta"),
        "conjuge_renda_liquida": g("prop2_renda_liquida"),
        "conjuge_extras": g("prop2_extras"),
        "emprestimos": g("emprestimos"),
        "moradia_tipo": g("moradia_tipo"),
        "transportes": g("transportes"),
        "conta": g("conta"),
        "conta_salario": g("conta_salario"),
        "open_finance": g("open_finance"),
        "opt_in": g("opt_in"),
        "biometria": g("biometria"),
        "cartao_credito": g("cartao_credito"),
        "crot": g("crot"),
        "valor_total": g("valor_total"),
        "subsidio": g("subsidio"),
        "entrada": g("entrada"),
        "negociacao": g("negociacao"),
        "financiado": g("financiado"),
        "parcela": g("parcela"),
        "prazo": g("prazo"),
        "amortizacao": g("amortizacao"),
        "utilizar_fgts": g("utilizar_fgts"),
        "endereco_imovel": g("endereco_imovel"),
        "proprietarios": g("proprietarios"),
        "construtora_nome": g("construtora"),
        "proprietarios_construtora": g("proprietarios_construtora"),
        "taxa_vista_contrato": g("taxa_vista_contrato"),
        "seguridade": g("seguridade"),
    }


def migrate(execute, log_path):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    conflitos = []
    stats = {
        "fichas_lidas": 0,
        "ja_migradas": 0,
        "clientes_criados": 0,
        "clientes_reutilizados": 0,
        "clientes_pendentes": 0,
        "conflitos_campo": 0,
        "conjuges_criados": 0,
        "habitacao_inseridas": 0,
    }

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Coluna de rastreamento para idempotência
            cur.execute(
                "ALTER TABLE habitacao_fichas "
                "ADD COLUMN IF NOT EXISTS legacy_ficha_id INT"
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_habitacao_legacy "
                "ON habitacao_fichas(legacy_ficha_id) WHERE legacy_ficha_id IS NOT NULL"
            )

            cur.execute(
                "SELECT * FROM fichas ORDER BY created_at ASC, id ASC"
            )
            fichas = cur.fetchall()
            stats["fichas_lidas"] = len(fichas)
            LOG.info("Lidas %d fichas legadas", len(fichas))

            for f in fichas:
                fid = f["id"]

                # Já migrada?
                cur.execute(
                    "SELECT id FROM habitacao_fichas WHERE legacy_ficha_id = %s",
                    (fid,),
                )
                if cur.fetchone():
                    stats["ja_migradas"] += 1
                    continue

                cpf = cpf_digits(f.get("proponente1_cpf"))
                cliente_data = ficha_to_cliente(f)

                if len(cpf) == 11:
                    # Dedupe por CPF válido
                    cur.execute(
                        "SELECT * FROM clientes "
                        "WHERE cpf = %s AND cpf_pendente = false",
                        (cpf,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        # Última vence em mutáveis
                        updates = {}
                        for k in MUTABLE_FIELDS:
                            novo = cliente_data.get(k)
                            antigo = existing.get(k)
                            if novo and novo != antigo:
                                updates[k] = novo
                                conflitos.append({
                                    "ficha_id": fid,
                                    "cpf": cpf,
                                    "campo": k,
                                    "antigo": str(antigo or ""),
                                    "novo": str(novo),
                                })
                                stats["conflitos_campo"] += 1
                        if updates:
                            sets = ", ".join(f"{k} = %({k})s" for k in updates)
                            updates["id"] = existing["id"]
                            cur.execute(
                                f"UPDATE clientes SET {sets}, updated_at = NOW() "
                                f"WHERE id = %(id)s",
                                updates,
                            )
                        cliente_id = existing["id"]
                        stats["clientes_reutilizados"] += 1
                    else:
                        cur.execute(
                            "INSERT INTO clientes (cpf, cpf_pendente, nome, email, whatsapp1) "
                            "VALUES (%s, false, %s, %s, %s) RETURNING id",
                            (cpf, cliente_data["nome"],
                             cliente_data["email"], cliente_data["whatsapp1"]),
                        )
                        cliente_id = cur.fetchone()["id"]
                        stats["clientes_criados"] += 1
                else:
                    # CPF inválido/vazio → cpf_pendente + CPF sintético único
                    synthetic = f"PEND{fid:07d}"[:11]
                    cur.execute(
                        "INSERT INTO clientes (cpf, cpf_pendente, nome, email, whatsapp1) "
                        "VALUES (%s, true, %s, %s, %s) RETURNING id",
                        (synthetic, cliente_data["nome"],
                         cliente_data["email"], cliente_data["whatsapp1"]),
                    )
                    cliente_id = cur.fetchone()["id"]
                    stats["clientes_pendentes"] += 1
                    LOG.warning("ficha %s CPF inválido (%r) → pendente %s",
                                fid, f.get("proponente1_cpf"), synthetic)

                # Cônjuge
                prop2_nome = (f.get("prop2_nome") or "").strip()
                if prop2_nome:
                    cur.execute(
                        "INSERT INTO conjuges (cliente_id, nome) VALUES (%s, %s) "
                        "ON CONFLICT (cliente_id) DO UPDATE "
                        "SET nome = EXCLUDED.nome, updated_at = NOW()",
                        (cliente_id, prop2_nome),
                    )
                    stats["conjuges_criados"] += 1

                # habitacao_fichas
                h = ficha_to_habitacao(f, cliente_id)
                h["legacy_ficha_id"] = fid
                cols = list(h.keys())
                placeholders = ", ".join(f"%({c})s" for c in cols)
                cur.execute(
                    f"INSERT INTO habitacao_fichas ({', '.join(cols)}) "
                    f"VALUES ({placeholders})",
                    h,
                )
                stats["habitacao_inseridas"] += 1

        if execute:
            conn.commit()
            LOG.info("COMMIT: transação completa, dados persistidos.")
        else:
            conn.rollback()
            LOG.info("DRY-RUN: rollback completo, nada foi persistido.")

        # Log de conflitos (sempre, mesmo em dry-run)
        if conflitos:
            with open(log_path, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["ficha_id", "cpf", "campo", "antigo", "novo"])
                w.writeheader()
                w.writerows(conflitos)
            LOG.info("Conflitos logados em %s (%d linhas)", log_path, len(conflitos))

        LOG.info("========== RESUMO ==========")
        for k, v in stats.items():
            LOG.info("  %-22s %d", k, v)
        LOG.info("============================")
        return stats
    except Exception as e:
        conn.rollback()
        LOG.exception("Erro durante migração, rollback feito: %s", e)
        raise
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="Commita de verdade (default: dry-run rolling back)")
    ap.add_argument("--log", default="/tmp/migration_conflicts.csv",
                    help="Caminho do CSV de conflitos")
    args = ap.parse_args()
    migrate(execute=args.execute, log_path=Path(args.log))


if __name__ == "__main__":
    main()
