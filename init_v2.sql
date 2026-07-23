-- Schema v2 — fonte única de verdade do portal AM Imóveis
-- Idempotente: usa CREATE TABLE IF NOT EXISTS e DO $$ EXCEPTION blocks

-- Usuarios (portal auth)
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT 'usuario'
        CHECK (perfil IN ('admin', 'usuario')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);

-- ============================================================
-- RBAC: perfis de acesso + matriz de permissões granular
-- ============================================================
CREATE TABLE IF NOT EXISTS rbac_roles (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,   -- Administrador protegido (sempre acesso total)
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rbac_role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INT NOT NULL REFERENCES rbac_roles(id) ON DELETE CASCADE,
    recurso TEXT NOT NULL,
    ver     BOOLEAN NOT NULL DEFAULT FALSE,
    criar   BOOLEAN NOT NULL DEFAULT FALSE,
    editar  BOOLEAN NOT NULL DEFAULT FALSE,
    excluir BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (role_id, recurso)
);
CREATE INDEX IF NOT EXISTS idx_rbac_perm_role ON rbac_role_permissions(role_id);

-- Vínculo usuário → perfil de acesso (migração idempotente)
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS role_id INT REFERENCES rbac_roles(id) ON DELETE SET NULL;

-- Cadastros auxiliares
CREATE TABLE IF NOT EXISTS cidades (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    uf CHAR(2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (nome, uf)
);

CREATE TABLE IF NOT EXISTS agencias (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    bairro TEXT,
    numero TEXT,
    cidade_id INT NOT NULL REFERENCES cidades(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agencias_cidade ON agencias(cidade_id);

CREATE TABLE IF NOT EXISTS gerentes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    agencia_id INT NOT NULL REFERENCES agencias(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gerentes_agencia ON gerentes(agencia_id);

DO $$ BEGIN
    CREATE TYPE tipo_parceiro AS ENUM ('CONSTRUTORA','IMOBILIARIA','AUTONOMO');
EXCEPTION WHEN duplicate_object THEN null; END $$;

CREATE TABLE IF NOT EXISTS parceiros (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo tipo_parceiro NOT NULL,
    cidade_id INT NOT NULL REFERENCES cidades(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_parceiros_cidade ON parceiros(cidade_id);
CREATE INDEX IF NOT EXISTS idx_parceiros_tipo ON parceiros(tipo);

CREATE TABLE IF NOT EXISTS imoveis (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    construtora_id INT REFERENCES parceiros(id) ON DELETE SET NULL,
    cidade_id INT NOT NULL REFERENCES cidades(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_imoveis_cidade ON imoveis(cidade_id);
CREATE INDEX IF NOT EXISTS idx_imoveis_construtora ON imoveis(construtora_id);

CREATE TABLE IF NOT EXISTS correspondentes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cidade_id INT NOT NULL REFERENCES cidades(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS corretores (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf CHAR(11),
    nascimento DATE,
    telefone TEXT,
    email TEXT,
    creci TEXT,
    cidade_id INT REFERENCES cidades(id) ON DELETE SET NULL,
    tamanho_camisa TEXT,
    chocolate_preferido TEXT,
    bebida_preferida TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE corretores ADD COLUMN IF NOT EXISTS tamanho_camisa TEXT;
ALTER TABLE corretores ADD COLUMN IF NOT EXISTS chocolate_preferido TEXT;
ALTER TABLE corretores ADD COLUMN IF NOT EXISTS bebida_preferida TEXT;

-- Configurações chave/valor da aplicação (toggles, flags, etc)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO app_settings (key, value) VALUES ('corretores_publico_ativo', 'true')
    ON CONFLICT (key) DO NOTHING;
CREATE INDEX IF NOT EXISTS idx_corretores_nome ON corretores(nome);
CREATE INDEX IF NOT EXISTS idx_corretores_cpf ON corretores(cpf);
CREATE INDEX IF NOT EXISTS idx_corretores_cidade ON corretores(cidade_id);

-- Cliente central (dados pessoais puros)
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    cpf CHAR(11) NOT NULL,
    cpf_pendente BOOLEAN NOT NULL DEFAULT false,
    nome TEXT NOT NULL,
    rg TEXT, rg_orgao TEXT,
    nascimento DATE,
    nacionalidade TEXT, estado_civil TEXT, regime_bens TEXT, profissao TEXT,
    email TEXT, telefone_fixo TEXT, whatsapp1 TEXT, whatsapp2 TEXT,
    endereco TEXT, bairro TEXT, cep TEXT,
    cidade_id INT REFERENCES cidades(id) ON DELETE SET NULL,
    observacoes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS clientes_cpf_valid_idx ON clientes(cpf) WHERE cpf_pendente = false;
CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome);

-- Migração: campos adicionais Salesforce-like
DO $$ BEGIN
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS sexo TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS tipo_pessoa TEXT DEFAULT 'Fisica';
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS naturalidade TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS escolaridade TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nome_mae TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nome_pai TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS numero_pis TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS titulo_eleitor TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS categoria TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS codigo_sap TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS codigo_crm TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cargo TEXT;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS proprietario_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS criado_por_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    ALTER TABLE clientes ADD COLUMN IF NOT EXISTS modificado_por_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
EXCEPTION WHEN others THEN NULL; END $$;

-- Notas (Chatter) de cliente
CREATE TABLE IF NOT EXISTS cliente_notas (
    id              SERIAL PRIMARY KEY,
    cliente_id      INT NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    corpo           TEXT NOT NULL,
    criado_por_id   INT REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cliente_notas_cliente ON cliente_notas(cliente_id);

-- Cônjuge (1:1 opcional)
CREATE TABLE IF NOT EXISTS conjuges (
    id SERIAL PRIMARY KEY,
    cliente_id INT NOT NULL UNIQUE REFERENCES clientes(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    cpf TEXT, rg TEXT, rg_orgao TEXT,
    nascimento DATE,
    nacionalidade TEXT, estado_civil TEXT, profissao TEXT,
    email TEXT, whatsapp TEXT, fixo TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Habitação (snapshot por processo)
CREATE TABLE IF NOT EXISTS habitacao_fichas (
    id SERIAL PRIMARY KEY,
    cliente_id INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    empreendimento TEXT,
    imovel_id INT REFERENCES imoveis(id) ON DELETE SET NULL,
    idade_snapshot TEXT,
    dependentes TEXT,
    coobrigado_nome TEXT,
    titular_funcao TEXT, titular_empresa TEXT, titular_admissao TEXT,
    titular_renda_bruta TEXT, titular_renda_liquida TEXT, titular_extras TEXT,
    conjuge_nome TEXT, conjuge_cpf TEXT,
    conjuge_funcao TEXT, conjuge_empresa TEXT, conjuge_admissao TEXT,
    conjuge_renda_bruta TEXT, conjuge_renda_liquida TEXT, conjuge_extras TEXT,
    emprestimos TEXT, moradia_tipo TEXT, transportes TEXT,
    conta TEXT, conta_salario TEXT, open_finance TEXT, opt_in TEXT,
    biometria TEXT, cartao_credito TEXT, crot TEXT,
    valor_total TEXT, subsidio TEXT, entrada TEXT, negociacao TEXT,
    financiado TEXT, parcela TEXT, prazo TEXT, amortizacao TEXT, utilizar_fgts TEXT,
    endereco_imovel TEXT, proprietarios TEXT,
    construtora_id INT REFERENCES parceiros(id) ON DELETE SET NULL,
    construtora_nome TEXT,
    proprietarios_construtora TEXT,
    taxa_vista_contrato TEXT, seguridade TEXT,
    legacy_ficha_id INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_habitacao_cliente ON habitacao_fichas(cliente_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_habitacao_legacy ON habitacao_fichas(legacy_ficha_id) WHERE legacy_ficha_id IS NOT NULL;

-- Migração: conjuge_nome/cpf direto na ficha (substitui JOIN com tabela conjuges)
DO $$ BEGIN
    ALTER TABLE habitacao_fichas ADD COLUMN IF NOT EXISTS conjuge_nome TEXT;
    ALTER TABLE habitacao_fichas ADD COLUMN IF NOT EXISTS conjuge_cpf  TEXT;
EXCEPTION WHEN others THEN NULL; END $$;

-- Propostas v2
CREATE TABLE IF NOT EXISTS propostas (
    id SERIAL PRIMARY KEY,
    cliente_id INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    imovel_id INT REFERENCES imoveis(id) ON DELETE SET NULL,
    empreendimento TEXT,
    unidade TEXT,
    valor_total TEXT,
    observacoes TEXT,
    validade TEXT,
    corretor_nome TEXT,
    corretor_creci TEXT,
    data_dia TEXT, data_mes TEXT, data_ano TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_propostas_cliente ON propostas(cliente_id);
ALTER TABLE propostas ADD COLUMN IF NOT EXISTS corretor_id INT REFERENCES corretores(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS proposta_pagamentos (
    id SERIAL PRIMARY KEY,
    proposta_id INT NOT NULL REFERENCES propostas(id) ON DELETE CASCADE,
    ordem INT NOT NULL,
    descricao TEXT NOT NULL,
    quantidade TEXT,
    valor_parcela TEXT,
    valor_total TEXT,
    forma TEXT,
    vencimento TEXT
);
CREATE INDEX IF NOT EXISTS idx_proposta_pag_proposta ON proposta_pagamentos(proposta_id);

-- Financiamento
DO $$ BEGIN
    CREATE TYPE modalidade_imovel AS ENUM ('CASA','APARTAMENTO','TERRENO','COMERCIAL');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE status_analise AS ENUM ('PENDENTE','EM_ANALISE','APROVADO','REPROVADO','CANCELADO');
EXCEPTION WHEN duplicate_object THEN null; END $$;

CREATE TABLE IF NOT EXISTS financiamentos (
    id SERIAL PRIMARY KEY,
    cliente_id INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    imovel_id INT REFERENCES imoveis(id) ON DELETE SET NULL,
    gerente_id INT REFERENCES gerentes(id) ON DELETE SET NULL,
    parceiro_id INT REFERENCES parceiros(id) ON DELETE SET NULL,
    correspondente_id INT REFERENCES correspondentes(id) ON DELETE SET NULL,
    modalidade modalidade_imovel,
    renda NUMERIC(15,2),
    valor_financiamento NUMERIC(15,2),
    analise status_analise NOT NULL DEFAULT 'PENDENTE',
    observacoes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_financiamentos_cliente ON financiamentos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_financiamentos_analise ON financiamentos(analise);

-- ============================================================
-- Termo de Parentesco (declaração CAIXA Lei 14.620/2023)
-- ============================================================
CREATE TABLE IF NOT EXISTS parentescos (
    id                     SERIAL PRIMARY KEY,
    cliente_id             INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    parente_nome           TEXT NOT NULL,
    parente_cpf            TEXT NOT NULL,
    parente_estado_civil   TEXT,
    grau_parentesco        TEXT,
    conjuge_parente_nome   TEXT,
    data_declaracao        TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_parentescos_cliente ON parentescos(cliente_id);

-- ============================================================
-- Logos (imagens de logo para documentos PDF)
-- ============================================================
CREATE TABLE IF NOT EXISTS logos (
    id              SERIAL PRIMARY KEY,
    nome            TEXT NOT NULL,
    arquivo         BYTEA NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'image/png',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Recibos
-- ============================================================
CREATE TABLE IF NOT EXISTS recibos (
    id                      SERIAL PRIMARY KEY,
    cliente_id              INT REFERENCES clientes(id) ON DELETE RESTRICT,
    logo_id                 INT REFERENCES logos(id) ON DELETE SET NULL,
    cidade_id               INT REFERENCES cidades(id) ON DELETE SET NULL,
    numero_contrato         TEXT,
    data_recibo             DATE,
    valor_recebido          NUMERIC(15,2),
    nome_pagador            TEXT,
    doc_pagador             TEXT,
    forma_pagamento         TEXT,
    formas_pagamento        JSONB,
    descricao_referencia    TEXT,
    data_local              DATE,
    assinatura_nome         TEXT,
    doc_recebedor           TEXT,
    rodape_texto            TEXT,
    observacoes             TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_recibos_cliente ON recibos(cliente_id);

-- Migração recibos: remover colunas obsoletas e adicionar cidade_id
DO $$ BEGIN
    ALTER TABLE recibos ADD COLUMN IF NOT EXISTS cidade_id INT REFERENCES cidades(id) ON DELETE SET NULL;
EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE recibos DROP COLUMN IF EXISTS nome_recebedor;
    ALTER TABLE recibos DROP COLUMN IF EXISTS cpf_recebedor;
    ALTER TABLE recibos DROP COLUMN IF EXISTS cidade;
    ALTER TABLE recibos DROP COLUMN IF EXISTS uf;
EXCEPTION WHEN others THEN NULL; END $$;
-- Converter data_recibo/data_local de TEXT para DATE se necessário
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='recibos' AND column_name='data_recibo' AND data_type='text') THEN
        ALTER TABLE recibos ALTER COLUMN data_recibo TYPE DATE USING NULL;
        ALTER TABLE recibos ALTER COLUMN data_local TYPE DATE USING NULL;
    END IF;
EXCEPTION WHEN others THEN NULL; END $$;
-- Migração v3: cliente_id nullable, renomear doc campos
DO $$ BEGIN
    ALTER TABLE recibos ALTER COLUMN cliente_id DROP NOT NULL;
EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE recibos RENAME COLUMN cnpj_pagador TO doc_pagador;
EXCEPTION WHEN undefined_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE recibos RENAME COLUMN assinatura_cpf TO doc_recebedor;
EXCEPTION WHEN undefined_column THEN NULL; END $$;
ALTER TABLE recibos DROP COLUMN IF EXISTS valor_cabecalho;
-- Migração v4: formas de pagamento múltiplas (breakdown: [{forma, valor}, ...])
ALTER TABLE recibos ADD COLUMN IF NOT EXISTS formas_pagamento JSONB;

-- ============================================================
-- CRM (Salesforce-style sales pipeline)
-- ============================================================

-- Pipelines (funis configuráveis)
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    descricao   TEXT,
    is_default  BOOLEAN NOT NULL DEFAULT FALSE,
    ativo       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Etapas (stages) de cada pipeline
CREATE TABLE IF NOT EXISTS crm_stages (
    id              SERIAL PRIMARY KEY,
    pipeline_id     INT NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE,
    nome            TEXT NOT NULL,
    ordem           INT NOT NULL DEFAULT 0,
    probabilidade   INT NOT NULL DEFAULT 0,   -- 0-100
    cor             TEXT DEFAULT '#065676',
    tipo            TEXT NOT NULL DEFAULT 'aberto',  -- aberto | ganho | perdido
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_stages_pipeline ON crm_stages(pipeline_id);

-- Campanhas / origens de leads
CREATE TABLE IF NOT EXISTS crm_campaigns (
    id           SERIAL PRIMARY KEY,
    nome         TEXT NOT NULL,
    tipo         TEXT,        -- meta_ads, google_ads, indicacao, whatsapp, site, evento, outro
    status       TEXT DEFAULT 'ativa',
    data_inicio  DATE,
    data_fim     DATE,
    orcamento    NUMERIC(15,2),
    descricao    TEXT,
    ativo        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Leads (prospects ainda não qualificados/convertidos)
CREATE TABLE IF NOT EXISTS crm_leads (
    id                   SERIAL PRIMARY KEY,
    nome                 TEXT NOT NULL,
    email                TEXT,
    telefone             TEXT,
    whatsapp             TEXT,
    cpf_cnpj             TEXT,
    cidade_id            INT REFERENCES cidades(id) ON DELETE SET NULL,
    origem               TEXT,                  -- texto livre (site, indicacao, anuncio...)
    campaign_id          INT REFERENCES crm_campaigns(id) ON DELETE SET NULL,
    status               TEXT NOT NULL DEFAULT 'novo',  -- novo, contatado, qualificado, convertido, reativado, descartado
    score                INT DEFAULT 0,         -- 0-100, lead scoring
    interesse            TEXT,                  -- comprar, alugar, vender, financiar
    imovel_interesse_id  INT REFERENCES imoveis(id) ON DELETE SET NULL,
    valor_estimado       NUMERIC(15,2),
    proprietario_id      INT REFERENCES usuarios(id) ON DELETE SET NULL,   -- responsável
    cliente_id           INT REFERENCES clientes(id) ON DELETE SET NULL,   -- preenchido se convertido
    observacoes          TEXT,
    data_conversao       TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_leads_status ON crm_leads(status);
CREATE INDEX IF NOT EXISTS idx_crm_leads_proprietario ON crm_leads(proprietario_id);
CREATE INDEX IF NOT EXISTS idx_crm_leads_campaign ON crm_leads(campaign_id);
-- Índice pra auto-link de Lead → Cliente por CPF
CREATE INDEX IF NOT EXISTS idx_crm_leads_cpf ON crm_leads(cpf_cnpj) WHERE cpf_cnpj IS NOT NULL;

-- Opportunities (negociações em andamento)
-- Modelo: Cliente é central. Toda opp REQUER cliente_id. lead_id é metadata de origem.
CREATE TABLE IF NOT EXISTS crm_opportunities (
    id               SERIAL PRIMARY KEY,
    nome             TEXT NOT NULL,
    cliente_id       INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    lead_id          INT REFERENCES crm_leads(id) ON DELETE SET NULL,
    pipeline_id      INT NOT NULL REFERENCES crm_pipelines(id) ON DELETE RESTRICT,
    stage_id         INT NOT NULL REFERENCES crm_stages(id) ON DELETE RESTRICT,
    imovel_id        INT REFERENCES imoveis(id) ON DELETE SET NULL,
    valor            NUMERIC(15,2),
    probabilidade    INT,                 -- override do stage; NULL = usa do stage
    data_previsao    DATE,
    data_fechamento  DATE,
    proprietario_id  INT REFERENCES usuarios(id) ON DELETE SET NULL,
    campaign_id      INT REFERENCES crm_campaigns(id) ON DELETE SET NULL,
    status           TEXT NOT NULL DEFAULT 'aberta',  -- aberta, ganha, perdida
    motivo_perda     TEXT,
    proposta_id      INT REFERENCES propostas(id) ON DELETE SET NULL,
    descricao        TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_opp_status ON crm_opportunities(status);
CREATE INDEX IF NOT EXISTS idx_crm_opp_stage ON crm_opportunities(stage_id);
CREATE INDEX IF NOT EXISTS idx_crm_opp_pipeline ON crm_opportunities(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_crm_opp_proprietario ON crm_opportunities(proprietario_id);
CREATE INDEX IF NOT EXISTS idx_crm_opp_cliente ON crm_opportunities(cliente_id);

-- Activities (tarefas, ligações, reuniões, e-mails, notas)
CREATE TABLE IF NOT EXISTS crm_activities (
    id              SERIAL PRIMARY KEY,
    tipo            TEXT NOT NULL,        -- tarefa, ligacao, reuniao, email, whatsapp, nota
    assunto         TEXT NOT NULL,
    descricao       TEXT,
    data_atividade  TIMESTAMPTZ,
    data_conclusao  TIMESTAMPTZ,
    status          TEXT DEFAULT 'pendente',  -- pendente, em_andamento, concluida, cancelada
    prioridade      TEXT DEFAULT 'normal',    -- baixa, normal, alta, urgente
    lead_id         INT REFERENCES crm_leads(id) ON DELETE CASCADE,
    opportunity_id  INT REFERENCES crm_opportunities(id) ON DELETE CASCADE,
    cliente_id      INT REFERENCES clientes(id) ON DELETE CASCADE,
    proprietario_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
    criado_por_id   INT REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_act_lead ON crm_activities(lead_id);
CREATE INDEX IF NOT EXISTS idx_crm_act_opp ON crm_activities(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_crm_act_cliente ON crm_activities(cliente_id);
CREATE INDEX IF NOT EXISTS idx_crm_act_status ON crm_activities(status);

-- Stage history (auditoria de movimentação no funil)
CREATE TABLE IF NOT EXISTS crm_stage_history (
    id              SERIAL PRIMARY KEY,
    opportunity_id  INT NOT NULL REFERENCES crm_opportunities(id) ON DELETE CASCADE,
    stage_id_from   INT REFERENCES crm_stages(id) ON DELETE SET NULL,
    stage_id_to     INT NOT NULL REFERENCES crm_stages(id) ON DELETE CASCADE,
    usuario_id      INT REFERENCES usuarios(id) ON DELETE SET NULL,
    motivo          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_stage_hist_opp ON crm_stage_history(opportunity_id);

-- Webhooks (notificações de saída para integrações)
CREATE TABLE IF NOT EXISTS crm_webhooks (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    url         TEXT NOT NULL,
    eventos     TEXT NOT NULL,    -- csv: lead.created,lead.converted,opportunity.created,opportunity.stage_changed,opportunity.won,opportunity.lost,activity.created
    secret      TEXT,             -- HMAC SHA-256 signature secret
    ativo       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_webhook_logs (
    id            SERIAL PRIMARY KEY,
    webhook_id    INT NOT NULL REFERENCES crm_webhooks(id) ON DELETE CASCADE,
    evento        TEXT NOT NULL,
    payload       JSONB,
    status_code   INT,
    response_body TEXT,
    erro          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_wh_logs_webhook ON crm_webhook_logs(webhook_id);

-- Seed: pipeline padrão se nenhum existe
DO $$
DECLARE
    new_pipeline_id INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM crm_pipelines) THEN
        INSERT INTO crm_pipelines (nome, descricao, is_default)
        VALUES ('Vendas Imobiliárias', 'Pipeline padrão de vendas', TRUE)
        RETURNING id INTO new_pipeline_id;

        INSERT INTO crm_stages (pipeline_id, nome, ordem, probabilidade, cor, tipo) VALUES
            (new_pipeline_id, 'Prospecção',  1, 10, '#94a3b8', 'aberto'),
            (new_pipeline_id, 'Qualificação', 2, 25, '#3b82f6', 'aberto'),
            (new_pipeline_id, 'Visita',       3, 40, '#8b5cf6', 'aberto'),
            (new_pipeline_id, 'Proposta',     4, 60, '#f59e0b', 'aberto'),
            (new_pipeline_id, 'Negociação',   5, 80, '#ec4899', 'aberto'),
            (new_pipeline_id, 'Ganho',        6, 100, '#22c55e', 'ganho'),
            (new_pipeline_id, 'Perdido',      7, 0,   '#ef4444', 'perdido');
    END IF;
END $$;

-- ============================================================
-- Expansão de crm_opportunities (campos Salesforce-like)
-- ============================================================
DO $$ BEGIN
    -- Identificação / status
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS altera_proprietario BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS solicitante TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS classificacao_lead TEXT DEFAULT 'Não Classificado';
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS url_jornada TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pendencia_documentos BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS sla_expirado BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_limite_contrato DATE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS indicacao_premiada BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS enquadramento_apurado TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS origem_lead TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS marca TEXT;
    -- Empreendimento snapshot
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS empreendimento_nome TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS status_lancamento TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS unidade TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS imobiliaria TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS equipe TEXT;
    -- Equipe (FKs adicionais)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS corretor_imobiliaria_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS aprovador_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS responsavel_atual_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS gestor_atual_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    -- PAC (Proposta de Análise de Crédito)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_codigo TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_valor_imovel NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_status TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_tipo_amortizacao TEXT;
    -- Emcash
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS emcash_habilitado BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_emcash_habilitado TIMESTAMPTZ;
    -- Entrada Facilitada
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS entrada_facilitada BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_entrada_facilitada TIMESTAMPTZ;
    -- Pagadoria
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pagadoria BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_pagadoria TIMESTAMPTZ;
    -- Plano Padrão
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS plano_padrao_aplicado BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_plano_padrao DATE;
    -- Bala de Prata / Rating
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS rating_gerencial_aplicado BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS solicitacao_rating BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS status_solicitacao_propriedade TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS remetente_solicitacao_rating TEXT;
    -- Negociação Especial
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS negociacao_especial_aplicada BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS solicitacao_negociacao_especial BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_ativacao_negociacao_especial TIMESTAMPTZ;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS motivo_negociacao_especial TEXT;
    -- Financeiro
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_entrada NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_total_pagar NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_parcela_mensal NUMERIC(15,2);
    -- Simulação Banco
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS banco_financiador TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS avaliacao_banco TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS tipo_financiamento TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_parcela_banco NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS prazo_simulacao_meses INT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_total_financiamento NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS taxa_juros_anual NUMERIC(6,3);
    -- Simulação Plataforma
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS renda_mensal NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS contribuicao_fgts_3anos BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS possui_dependentes BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_nasc_mais_velha DATE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_sinal NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS desconto_mrv NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_fgts NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS beneficio_mcmv NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_parcela_mrv NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS fator_social BOOLEAN DEFAULT FALSE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS estado_civil TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_imovel NUMERIC(15,2);
    -- Boleto
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS codigo_acao_boleto TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS linha_digitavel_boleto TEXT;
    -- Fechamento
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS assinatura_banco_data DATE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS resgate_fgts TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS registro TEXT;
    -- Sistema (criador/modificador) — created_at/updated_at já existem
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS criado_por_id INT REFERENCES usuarios(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS modificado_por_id INT REFERENCES usuarios(id) ON DELETE SET NULL;

    -- ===== Layout "Pos-Venda PHB" (13 cards) — 2026-06 =====
    -- Card 2: Dados do Imovel (detalhamento snapshot da oportunidade)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS imovel_endereco TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS imovel_bairro TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS imovel_cidade_uf TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS imovel_cep TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS imovel_tipo TEXT;
    -- Card 3: Dados da Venda
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS venda_forma_entrada TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS venda_qtd_parcelas_entrada INT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS venda_valor_parcela_entrada NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS venda_data_primeira_parcela DATE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS data_contrato DATE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS numero_contrato TEXT;
    -- Card 6: PAC (complemento — pac_codigo/pac_valor_imovel/pac_status/pac_tipo_amortizacao ja existem)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_valor_avaliacao NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_probabilidade INT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_prazo_meses INT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_valor_parcela NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pac_tipo_analise TEXT;
    -- Card 7: Entrada Facilitada (complemento — entrada_facilitada ja existe)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS ef_construtora TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS ef_qtd_parcelas INT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS ef_valor_parcela NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS ef_valor_total NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS ef_observacao TEXT;
    -- Card 9: Equipe (complemento)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS construtora_nome TEXT;
    -- Card 12/13: Resumo Financeiro + Contabil / Fechamento
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS comissao_total NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS comissao_recebimento_1 NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS comissao_restante NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS comissao_previsao_recebimento DATE;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS comissao_status TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS comissao_forma_recebimento TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS contabil_mes_fechamento TEXT;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS contabil_data_fechamento DATE;

    -- SLA por etapa (faixa de SLA na pagina de detalhe)
    ALTER TABLE crm_stages ADD COLUMN IF NOT EXISTS sla_dias INT;

    -- ===== Fase 2: pipelines Venda -> Pos-Venda vinculados — 2026-06 =====
    -- Pipeline ganha tipo + link para a pipeline de pos-venda
    ALTER TABLE crm_pipelines ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'generico'; -- venda | pos_venda | generico
    ALTER TABLE crm_pipelines ADD COLUMN IF NOT EXISTS pipeline_pos_venda_id INT REFERENCES crm_pipelines(id) ON DELETE SET NULL;
    -- Oportunidade guarda a jornada de pos-venda em paralelo (mantem pipeline_id/stage_id = jornada de venda)
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pos_venda_pipeline_id INT REFERENCES crm_pipelines(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pos_venda_stage_id INT REFERENCES crm_stages(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS pos_venda_iniciada_em TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_crm_opp_pos_pipeline ON crm_opportunities(pos_venda_pipeline_id);

    -- ===== Fase 3: gatilhos/automacoes por etapa (qualquer pipeline) — 2026-06 =====
    -- Cada etapa configura a "proxima acao automatica" + SLA. Ao entrar na etapa,
    -- o motor cria a tarefa automatica (card 11) e a faixa/alertas de SLA usam sla_dias.
    ALTER TABLE crm_stages ADD COLUMN IF NOT EXISTS auto_tarefa_assunto TEXT;
    ALTER TABLE crm_stages ADD COLUMN IF NOT EXISTS auto_tarefa_descricao TEXT;
    ALTER TABLE crm_stages ADD COLUMN IF NOT EXISTS auto_tarefa_tipo TEXT DEFAULT 'tarefa';
    ALTER TABLE crm_stages ADD COLUMN IF NOT EXISTS auto_tarefa_prazo_dias INT; -- prazo da tarefa = entrada + N dias (NULL = usa sla_dias)
    ALTER TABLE crm_stages ADD COLUMN IF NOT EXISTS auto_notificar BOOLEAN DEFAULT TRUE; -- dispara webhook na entrada
    -- Atividade sabe de qual etapa nasceu e se foi automatica
    ALTER TABLE crm_activities ADD COLUMN IF NOT EXISTS stage_id INT REFERENCES crm_stages(id) ON DELETE SET NULL;
    ALTER TABLE crm_activities ADD COLUMN IF NOT EXISTS auto BOOLEAN DEFAULT FALSE;
    CREATE INDEX IF NOT EXISTS idx_crm_act_stage ON crm_activities(stage_id);
EXCEPTION WHEN others THEN NULL; END $$;

-- Documentos da oportunidade (card 10 + aba Documentos) — upload + checklist
CREATE TABLE IF NOT EXISTS crm_opp_documentos (
    id             SERIAL PRIMARY KEY,
    opportunity_id INT NOT NULL REFERENCES crm_opportunities(id) ON DELETE CASCADE,
    nome           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pendente',  -- pendente | enviado | assinado | concluido
    arquivo        BYTEA,                              -- NULL = item de checklist sem arquivo ainda
    nome_arquivo   TEXT,
    content_type   TEXT,
    tamanho        INT,
    observacao     TEXT,
    criado_por_id  INT REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_opp_doc_opp ON crm_opp_documentos(opportunity_id);

-- Tabela de notas (Notas section da opportunity)
CREATE TABLE IF NOT EXISTS crm_opp_notas (
    id              SERIAL PRIMARY KEY,
    opportunity_id  INT NOT NULL REFERENCES crm_opportunities(id) ON DELETE CASCADE,
    titulo          TEXT,
    corpo           TEXT NOT NULL,
    criado_por_id   INT REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_opp_notas_opp ON crm_opp_notas(opportunity_id);

-- ============================================================================
-- WhatsApp (uazapi) — integração, conversas e mensagens
-- ============================================================================
-- Single-tenant: UMA integração ativa por provider. O id é estável entre
-- reconexões (o QR só revincula um celular à MESMA instância) — é isso que
-- impede as conversas de duplicarem ao reconectar.

CREATE TABLE IF NOT EXISTS chat_integracoes (
    id              SERIAL PRIMARY KEY,
    provider        TEXT NOT NULL DEFAULT 'uazapi',
    nome            TEXT,
    api_url         TEXT NOT NULL,             -- ex.: https://xxx.uazapi.com
    token           TEXT NOT NULL,             -- vai no header `token:` (NÃO Bearer)
    telefone_dono   TEXT,                      -- owner da instância (vem do /instance/status)
    webhook_secret  TEXT NOT NULL,             -- viaja na query string ?s=<secret>
    webhook_url     TEXT,                      -- última URL registrada na uazapi
    conectado       BOOLEAN NOT NULL DEFAULT FALSE,
    estado          TEXT NOT NULL DEFAULT 'unknown',   -- open | connecting | close | unknown
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_erro     TEXT,
    criado_por_id   INT REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS chat_integracoes_ativa_idx
    ON chat_integracoes(provider) WHERE ativo = TRUE;

-- Uma conversa por contato. external_id = dígitos do CHATID (o CONTRAPARTE).
-- NUNCA derivar do sender_pn: em mensagens fromMe o sender é o DONO da instância,
-- e chavear por ele criaria "uma conversa com você mesmo".
CREATE TABLE IF NOT EXISTS chat_conversas (
    id                     SERIAL PRIMARY KEY,
    integracao_id          INT NOT NULL REFERENCES chat_integracoes(id) ON DELETE CASCADE,
    external_id            TEXT NOT NULL,      -- só dígitos, extraído do chatid
    chat_jid               TEXT,               -- 55...@s.whatsapp.net
    contato_nome           TEXT,
    contato_telefone       TEXT NOT NULL,
    contato_avatar_url     TEXT,
    lead_id                INT REFERENCES crm_leads(id) ON DELETE SET NULL,
    cliente_id             INT REFERENCES clientes(id) ON DELETE SET NULL,
    status                 TEXT NOT NULL DEFAULT 'aberta',   -- aberta | resolvida
    nao_lidas              INT NOT NULL DEFAULT 0,
    ultima_mensagem_em     TIMESTAMPTZ,
    ultima_mensagem_previa TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chat_conversas_uniq UNIQUE (integracao_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_conversas_ultima
    ON chat_conversas(ultima_mensagem_em DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_chat_conversas_lead ON chat_conversas(lead_id);

-- Mensagens. v1 = só texto; media_url/media_mime_type são GANCHO (sempre NULL).
CREATE TABLE IF NOT EXISTS chat_mensagens (
    id              SERIAL PRIMARY KEY,
    conversa_id     INT NOT NULL REFERENCES chat_conversas(id) ON DELETE CASCADE,
    external_id     TEXT,                       -- messageid da uazapi; NULL enquanto 'pending'
    direcao         TEXT NOT NULL,              -- entrada | saida
    tipo            TEXT NOT NULL DEFAULT 'texto',
    conteudo        TEXT,
    media_url       TEXT,                       -- GANCHO (v1 não baixa mídia)
    media_mime_type TEXT,                       -- GANCHO
    delivery_status TEXT NOT NULL DEFAULT 'pending',  -- pending|sent|delivered|read|failed
    erro            TEXT,
    enviado_por_id  INT REFERENCES usuarios(id) ON DELETE SET NULL,
    mensagem_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Rede de segurança contra o ECHO: a mensagem que ENVIAMOS volta pelo webhook
    -- como fromMe. Em Postgres NULLs não colidem numa UNIQUE, então várias
    -- mensagens 'pending' (external_id NULL) coexistem sem problema.
    CONSTRAINT chat_mensagens_dedup UNIQUE (conversa_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_msg_conversa ON chat_mensagens(conversa_id, id);
CREATE INDEX IF NOT EXISTS idx_chat_msg_external
    ON chat_mensagens(external_id) WHERE external_id IS NOT NULL;

-- Lead automático no inbound: o WhatsApp só traz número, e crm_leads até aqui só
-- deduplicava por cpf_cnpj. Coluna GERADA (regexp_replace/COALESCE/NULLIF são
-- IMMUTABLE) => backfill automático no ALTER e nenhuma mudança nos INSERTs do repo.
-- Sem índice UNIQUE de propósito: leads legados podem já ter telefone repetido, e o
-- EXCEPTION abaixo esconderia a falha. A dedup é serializada por advisory lock no repo.
DO $$ BEGIN
    ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS telefone_normalizado TEXT
        GENERATED ALWAYS AS (
            NULLIF(regexp_replace(
                COALESCE(NULLIF(whatsapp, ''), NULLIF(telefone, ''), ''),
                '\D', '', 'g'), '')
        ) STORED;
EXCEPTION WHEN others THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_crm_leads_tel_norm
    ON crm_leads(telefone_normalizado) WHERE telefone_normalizado IS NOT NULL;

-- ============================================================================
-- Imóveis: dados de empreendimento + Unidades (fonte da verdade p/ o CRM)
-- ============================================================================
-- O "imóvel" é o EMPREENDIMENTO (nome + construtora + cidade já existiam). Agora
-- carrega também endereço/bairro/CEP/tipo — dados que a oportunidade HERDA (copia)
-- ao selecionar o imóvel, em vez de o usuário digitar tudo à mão no Card 2.
DO $$ BEGIN
    ALTER TABLE imoveis ADD COLUMN IF NOT EXISTS endereco TEXT;
    ALTER TABLE imoveis ADD COLUMN IF NOT EXISTS bairro   TEXT;
    ALTER TABLE imoveis ADD COLUMN IF NOT EXISTS cep      TEXT;
    ALTER TABLE imoveis ADD COLUMN IF NOT EXISTS tipo     TEXT;   -- Casa|Apartamento|Terreno|Comercial (texto livre)
EXCEPTION WHEN others THEN NULL; END $$;

-- Unidades de um imóvel (Apto 302, Casa 15, Lote 7...). Cada unidade é vendida uma
-- vez — é a granularidade da regra de não-duplicação e do "Valor do imóvel".
CREATE TABLE IF NOT EXISTS imovel_unidades (
    id            SERIAL PRIMARY KEY,
    imovel_id     INT NOT NULL REFERENCES imoveis(id) ON DELETE CASCADE,
    identificador TEXT NOT NULL,                       -- "Apto 302", "Casa 15"
    valor         NUMERIC(15,2),                       -- valor do imóvel desta unidade
    status        TEXT NOT NULL DEFAULT 'disponivel',  -- disponivel | reservada | vendida
    observacao    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Não repete o mesmo identificador dentro do mesmo empreendimento.
    CONSTRAINT imovel_unidades_uniq UNIQUE (imovel_id, identificador)
);
CREATE INDEX IF NOT EXISTS idx_imovel_unidades_imovel ON imovel_unidades(imovel_id);

-- A oportunidade referencia a UNIDADE (além do imovel_id que já existia). Os 7 campos
-- do Card 2 continuam como snapshot TEXT na própria oportunidade (cópia editável).
DO $$ BEGIN
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS unidade_id INT
        REFERENCES imovel_unidades(id) ON DELETE SET NULL;
EXCEPTION WHEN others THEN NULL; END $$;

-- ┌─ NÃO-DUPLICAÇÃO POR UNIDADE ─────────────────────────────────────────────┐
-- Índice único PARCIAL: no máximo UMA oportunidade não-perdida por unidade.
-- Como o predicado exclui `status = 'perdida'`, uma oportunidade que vira perdida
-- SAI do índice e a unidade fica livre para uma nova oportunidade. `unidade_id` NULL
-- (oportunidade sem unidade) nunca colide. É a rede de segurança no banco; o router
-- ainda faz a checagem para devolver um 409 amigável.
CREATE UNIQUE INDEX IF NOT EXISTS crm_opp_unidade_ativa_uniq
    ON crm_opportunities(unidade_id)
    WHERE unidade_id IS NOT NULL AND status <> 'perdida';

-- ============================================================================
-- Oportunidade: campos de Simulação/Financiamento, Entrada Facilitada e Venda
-- ============================================================================
-- Cards do detalhe reorganizados (card 6 vira "Simulação e Financiamento", card 7
-- "Entrada Facilitada"). Colunas NOVAS abaixo; as demais já existiam
-- (renda_mensal, valor_sinal, valor_fgts, valor_total_financiamento, valor_entrada,
--  valor_imovel, data_contrato, numero_contrato, venda_forma_entrada,
--  venda_valor_parcela_entrada, venda_data_primeira_parcela). Snapshot TEXT/livre.
DO $$ BEGIN
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_simulacao NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS valor_subsidio NUMERIC(15,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS modalidade_amortizacao TEXT;      -- PRICE | SAC
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS correspondente_id INTEGER          -- CCA (Correspondente Caixa) → cadastro correspondentes
        REFERENCES correspondentes(id) ON DELETE SET NULL;
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS situacao_analise_credito TEXT;    -- PENDENTE|APROVADO|CONFORMIDADE|REPROVADO
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS porcentagem_financiada NUMERIC(5,2);
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS ef_tipo_pagamento TEXT;           -- BOLETO|PIX|DEBITO|CREDITO|DINHEIRO
    ALTER TABLE crm_opportunities ADD COLUMN IF NOT EXISTS condicao_entrada TEXT;            -- texto livre
EXCEPTION WHEN others THEN NULL; END $$;
