# SPEC - Especificação Técnica

## Arquitetura

```
habitacao/
├── app.py                          # Flask app (auth + CRUD + PDF + CSV routes)
├── docker-compose.yml              # Docker Swarm stack (webapp + db)
├── Dockerfile                      # Python 3.12 + Playwright + Chromium deps
├── init.sql                        # DDL: tabelas fichas + usuarios + admin seed
├── requirements.txt                # flask, flask-cors, playwright, psycopg2-binary
├── .dockerignore
├── services/
│   ├── __init__.py
│   ├── db.py                       # Camada de acesso ao PostgreSQL (18 funções)
│   └── pdf_service.py              # Geração PDF (Playwright, auto-scale A4)
├── templates/
│   └── ficha_habitacional.html     # Template Jinja2 (46 variáveis)
├── static/
│   ├── login.html                  # Página de login
│   ├── list.html                   # Listagem de cadastros (home) + filtros
│   ├── form.html                   # Formulário criar/editar (9 seções)
│   ├── usuarios.html               # CRUD usuários (admin)
│   ├── logoAndreiaMiranda.png      # Logo colorida (tela login)
│   ├── logoAndreiaMirandab.png     # Logo branca (headers)
│   └── resources/sheet.css         # CSS legado (não usado atualmente)
└── habitacao/                      # Referência original (RAYLSON.html, etc)
```

## Docker Compose

```yaml
services:
  webapp:
    image: habitacao:latest
    environment: DATABASE_URL=postgresql://habitacao:${POSTGRES_PASSWORD}@habitacao_db:5432/habitacao
    networks: [earthnet, habitacao-internal]
    deploy:
      replicas: 1
      update_config: order: start-first, failure_action: rollback, delay: 5s
    # Traefik labels para habitacao.amimoveis.tec.br (HTTPS + redirect)

  db:
    image: postgres:16-alpine
    environment: POSTGRES_DB/USER/PASSWORD
    volumes: [habitacao-pgdata, init.sql]
    networks: [habitacao-internal]
    deploy.endpoint_mode: dnsrr  # IMPORTANTE: VIP causa auth failure
```

**Nota:** hostname do DB deve ser `habitacao_db` (nome do serviço no stack), não `db`. O VIP do Docker Swarm overlay causa falha de autenticação SCRAM-SHA-256. Usar DNSRR + nome completo do serviço resolve.

## Rotas (23 endpoints)

### Páginas (GET → HTML)
| Rota | Perfil | Descrição |
|---|---|---|
| `/login` | público | Tela de login |
| `/` | auth | Lista de cadastros (home) |
| `/cadastro/novo` | admin/editor | Formulário nova ficha |
| `/cadastro/<id>/editar` | admin/editor | Formulário edição |
| `/usuarios` | admin | Gerenciar usuários |

### API Auth
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/login` | Login (email + senha) |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Dados do usuário logado |

### API Fichas (CRUD)
| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/cadastros` | auth | Lista fichas (campos resumo) |
| POST | `/cadastro` | admin/editor | Cria nova ficha |
| GET | `/cadastro/<id>` | auth | Dados completos de uma ficha |
| PUT | `/cadastro/<id>` | admin/editor | Atualiza ficha |
| DELETE | `/cadastro/<id>` | admin/editor | Deleta ficha |
| GET | `/cadastro/<id>/pdf` | auth | Gera PDF da ficha |

### API CSV (Import/Export)
| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/cadastros/modelo` | auth | Download modelo CSV vazio |
| GET | `/cadastros/exportar` | auth | Exporta todos cadastros como CSV |
| POST | `/cadastros/importar` | admin/editor | Importa cadastros de CSV |

### API Usuários (admin only)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/usuarios` | Lista usuários ativos |
| POST | `/api/usuario` | Cria usuário |
| PUT | `/api/usuario/<id>` | Atualiza usuário |
| DELETE | `/api/usuario/<id>` | Desativa usuário (soft delete) |

### API Direta (sem DB)
| Método | Rota | Descrição |
|---|---|---|
| POST | `/contrato` | Gera PDF direto de JSON |
| GET | `/contrato/campos` | Lista 46 campos disponíveis |

## Schema do Banco

### fichas (46 campos + metadados)
```sql
id SERIAL PRIMARY KEY
created_at TIMESTAMPTZ DEFAULT NOW()
updated_at TIMESTAMPTZ DEFAULT NOW()
proponente1_nome TEXT NOT NULL
proponente1_cpf TEXT NOT NULL
-- ... 44 campos TEXT DEFAULT ''
-- Inclui: empreendimento, proponente1_idade, coobrigado_nome, dependentes,
-- contato_telefone, contato_email, prop1/prop2 (nome/funcao/empresa/admissao/
-- renda_bruta/renda_liquida/extras), emprestimos, moradia_tipo, transportes,
-- conta, conta_salario, open_finance, opt_in, biometria, cartao_credito, crot,
-- valor_total, subsidio, entrada, negociacao, financiado, parcela, prazo,
-- amortizacao, utilizar_fgts, endereco_imovel, proprietarios, construtora,
-- proprietarios_construtora, taxa_vista_contrato, seguridade
```

### usuarios
```sql
id SERIAL PRIMARY KEY
created_at TIMESTAMPTZ DEFAULT NOW()
nome TEXT NOT NULL
email TEXT NOT NULL UNIQUE
senha_hash TEXT NOT NULL  -- werkzeug scrypt
perfil TEXT NOT NULL DEFAULT 'leitor' CHECK (perfil IN ('admin', 'editor', 'leitor'))
ativo BOOLEAN DEFAULT TRUE
```

## Funções services/db.py (18)

**Fichas:** `listar_fichas()` (resumo), `listar_fichas_completas()` (export CSV), `obter_ficha(id)`, `criar_ficha(dados)`, `atualizar_ficha(id, dados)`, `deletar_ficha(id)`

**Usuários:** `obter_usuario_por_email(email)`, `obter_usuario(id)`, `listar_usuarios()`, `criar_usuario(nome, email, senha_hash, perfil)`, `atualizar_usuario(id, nome, email, perfil, senha_hash?)`, `deletar_usuario(id)` (soft delete), `contar_admins()`, `seed_admin(senha_hash)`

**Infra:** `_conn()`, `_ensure_usuarios_table()`, `FIELDS` (46 campos), `DATABASE_URL`

## Fluxo de Geração de PDF

1. `GET /cadastro/<id>/pdf` recebe request
2. `obter_ficha(id)` busca dados do PostgreSQL
3. `_renderizar_html(dados)` renderiza template Jinja2
   - Limpa campo idade (remove "anos" de dados antigos, mantém só número)
   - Template adiciona " ANOS" via Jinja2 `{% if %}`
4. `gerar_pdf(html)` via Playwright:
   - Viewport = 680px (largura útil A4 com margens 15mm)
   - Mede `scrollHeight` do conteúdo
   - Calcula scale: `min(1.0, 1047px / content_height)` (min 0.6)
   - Se ainda 2+ páginas, reduz scale * 0.82
   - Margens: 15mm laterais, 10mm topo/base
5. Retorna PDF inline (Content-Disposition: inline)

## Autenticação

- **Mecanismo:** Flask session (cookie-based)
- **Hash:** werkzeug `generate_password_hash` (scrypt)
- **Decorators:** `@login_required`, `@role_required("admin", "editor")`
- **Seed:** admin padrão criado em startup se nenhum admin existe (`admin@roper.com`; senha via `ADMIN_PASSWORD` no `.env`)
- **Rotas públicas:** `/login`, `/auth/login` (POST)
- **Redirect:** todas as rotas protegidas redirecionam para `/login` se não autenticado

## Validações no Frontend

- **Campos monetários (11):** máscara R$ em tempo real (class="moeda")
  - valor_total, subsidio, entrada, financiado, parcela
  - prop1_renda_bruta, prop1_renda_liquida, prop1_extras
  - prop2_renda_bruta, prop2_renda_liquida, prop2_extras
- **Idade:** input type="number" (min=0, max=120)
- **Uppercase:** automático em todos campos texto (exceto moeda)
- **Auto-fill:** prop1_nome herda de proponente1_nome até edição manual
- **Obrigatórios:** proponente1_nome, proponente1_cpf
- **Coobrigado:** seção toggle (mostrar/ocultar)
- **Empreendimento:** select com 5 opções fixas (hardcoded no form)

## Empreendimentos (hardcoded)

Lista fixa em list.html (filtro) e form.html (select):
1. Dirceu 8 Lotes
2. Planalto
3. Revoada dos Guaras Fase 1
4. Revoada dos Guaras Fase 2
5. Luar do Sertao

## Responsividade

Breakpoints: 320px, 480px, 768px
- **Login:** card adapta largura, logo reduz
- **Lista:** header empilha, colunas menos importantes somem, touch targets 44px
- **Form:** grids colapsam para 1 coluna, botões empilham
- **Usuários:** modal scrollável, colunas se escondem
- Inputs 16px no mobile (previne zoom iOS)

## Badges de Perfil (usuarios.html)

| Perfil | Cor |
|---|---|
| admin | #2563eb (azul) |
| editor | #16a34a (verde) |
| leitor | #9333ea (roxo) |
