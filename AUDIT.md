# AUDITORIA DE APLICAÇÃO WEB

> **Documento reutilizável** para condução de auditoria técnica em qualquer aplicação web,
> independente de stack, linguagem ou framework.
>
> **Como usar:** Para cada item, marque `[x]` quando verificado. Registre os achados
> na coluna de observações ou em documento separado.

---

## 1. INFORMAÇÕES DA APLICAÇÃO

| Campo                  | Valor |
|------------------------|-------|
| Nome da Aplicação      | Habitacao - Fichas Habitacionais PMCMV |
| Versão / Tag           | Sem versionamento (latest) |
| Stack (front/back/db)  | HTML/CSS/JS vanilla + Python 3.12/Flask + PostgreSQL 16 |
| URL(s) de ambiente     | https://habitacao.amimoveis.tec.br |
| Repositório            | /home/ubuntu/habitacao (local, sem remote git) |
| Data da Auditoria      | 2026-04-08 |
| Auditor(es)            | Claude Code (AI) |
| Escopo                 | Completo (segurança, débito técnico, arquitetura) |

---

## 2. SEGURANÇA

### 2.1 Injeção e Validação de Entrada

- [x] **SQL Injection** — Queries usam prepared statements com `%s` (psycopg2). Exceção: `db.py:38` usa f-string para SELECT com colunas, mas FIELDS é hardcoded (risco baixo). **OK com ressalva.**
- [x] **XSS (Cross-Site Scripting)** — Backend: Jinja2 com autoescape=true. **PROBLEMA no frontend:** `list.html:325-339` usa `innerHTML` com dados do usuário sem sanitização. `list.html:338` injeta nome em `onclick`. `list.html:477` concatena erro em innerHTML. **MÉDIO.**
- [x] **Command Injection** — Nenhuma chamada a exec/system/subprocess encontrada. **OK.**
- [x] **Path Traversal** — Upload CSV verifica extensão mas não valida conteúdo (`app.py:436`). PDF usa tempfile no diretório static (race condition possível). **MÉDIO.**
- [x] **SSRF (Server-Side Request Forgery)** — Nenhum endpoint faz requisição HTTP a partir de URL do usuário. **OK.**
- [x] **Template Injection** — Jinja2 com autoescape, dados não interpolados diretamente. **OK.**
- [x] **Mass Assignment** — `app.py:488-493` passa request JSON direto ao db.py, mas db.py filtra por FIELDS. **OK com ressalva** (depende de FIELDS estar correto).
- [x] **Validação no Backend** — Apenas `proponente1_nome` e `proponente1_cpf` validados como obrigatórios. Senha sem validação server-side (mínimo 4 chars só no frontend). **ALTO.**

### 2.2 Autenticação

- [x] **Armazenamento de Senhas** — werkzeug `generate_password_hash` (scrypt com salt). **OK.**
- [x] **Política de Senhas** — Mínimo 4 chars apenas no frontend (`usuarios.html:215`). Sem validação server-side. **ALTO.**
- [x] **Proteção contra Brute Force** — Nenhum rate limiting no `/auth/login`. **ALTO.**
- [x] **MFA (Multi-Factor Authentication)** — Não implementado. **Não aplicável** (sistema interno).
- [x] **Fluxo de Recuperação de Senha** — Não existe. Apenas admin pode resetar senhas. **OK** para escopo.
- [x] **OAuth / SSO** — Não aplicável.

### 2.3 Gestão de Sessão e Tokens

- [x] **JWT** — Não usa JWT, usa sessão Flask. **N/A.**
- [x] **Cookies de Sessão** — Sem flags `HttpOnly`, `Secure`, `SameSite` configuradas explicitamente. Depende dos defaults do Flask. **ALTO.**
- [x] **Refresh Tokens** — N/A (sessão server-side).
- [x] **Invalidação** — `session.clear()` no logout. **OK**, mas sem session timeout configurado.

### 2.4 Autorização e Controle de Acesso

- [x] **IDOR (Insecure Direct Object Reference)** — Qualquer usuário autenticado acessa qualquer ficha por ID (`app.py:496-507`). Sem validação de ownership. **ALTO.**
- [x] **Escalonamento Vertical** — Rotas admin protegidas com `@role_required`. **OK.**
- [x] **Escalonamento Horizontal** — Editors podem editar/deletar fichas de qualquer usuário. **ALTO** (mas pode ser by design, já que não há conceito de "dono da ficha").
- [x] **Controle por Endpoint** — Cada rota tem decorators de auth/role. **OK.**
- [x] **Princípio do Menor Privilégio** — 3 perfis bem definidos (admin/editor/leitor). **OK.**

### 2.5 Exposição de Dados Sensíveis

- [x] **Segredos no Código** — **CRÍTICO:** SECRET_KEY hardcoded (`app.py:22`), DB credentials em docker-compose.yml e db.py, admin password default no seed (`app.py:30`).
- [x] **Dados em Logs** — Logs não registram senhas ou tokens. **OK.**
- [x] **Respostas de API** — `/cadastros` retorna apenas 8 campos resumo. `/cadastros/exportar` retorna tudo mas requer auth. **OK.**
- [x] **Headers de Resposta** — Werkzeug expõe `Server` header. **BAIXO.**
- [x] **Mensagens de Erro** — `str(e)` retornado ao cliente em múltiplos endpoints (`app.py:348,406,461,520,531`). Pode vazar stack traces com debug=true. **ALTO.**

### 2.6 Configuração e Headers de Segurança

- [x] **HTTPS** — Via Traefik (redirect HTTP→HTTPS). **OK.**
- [x] **HSTS** — Não configurado no Flask (pode estar no Traefik). **MÉDIO.**
- [x] **CSP (Content Security Policy)** — Não configurado. **MÉDIO.**
- [x] **X-Frame-Options / frame-ancestors** — Não configurado. **MÉDIO.**
- [x] **X-Content-Type-Options: nosniff** — Não configurado. **MÉDIO.**
- [x] **CORS** — `CORS(app)` sem restrições (`app.py:23`). Permite qualquer origem. **ALTO.**
- [x] **CSRF** — Nenhuma proteção CSRF implementada. **ALTO.**
- [x] **Rate Limiting Global** — Não existe. **ALTO.**

### 2.7 Dependências e Supply Chain

- [x] **Vulnerabilidades Conhecidas** — Não verificado (sem `pip audit` disponível). Versões não pinadas.
- [x] **Versões Desatualizadas** — `requirements.txt` usa `>=` sem pinagem exata. **MÉDIO.**
- [x] **Dependências Abandonadas** — Flask, Playwright, psycopg2 são bem mantidos. **OK.**
- [x] **Lock Files** — Não existe `requirements.lock` ou `Pipfile.lock`. **MÉDIO.**
- [x] **Integridade** — Sem checksums. **BAIXO.**

---

## 3. DÉBITOS TÉCNICOS

### 3.1 Código Morto e Duplicação

- [x] **Código Morto** — Import `url_for` não utilizado (`app.py:4`). `DADOS_EXEMPLO` dict (`app.py:134-181`) usado apenas para rota de exemplo.
- [x] **Arquivos Órfãos** — `habitacao/RAYLSON.html`, `habitacao/VARIAQUES.html`, `habitacao/RAYLSON.pdf`, `static/resources/sheet.css` (3.8MB) não referenciados.
- [x] **Código Comentado** — Não encontrado. **OK.**
- [x] **Duplicação** — Mínima. Padrão de rotas é repetitivo mas aceitável.
- [x] **Feature Flags Abandonadas** — Não encontradas. **OK.**

### 3.2 Complexidade e Legibilidade

- [x] **Funções Longas** — `list.html`: 211 linhas JS inline. `form.html`: 153 linhas JS inline. Deveriam ser extraídos para `.js` separados. **MÉDIO.**
- [x] **Aninhamento Excessivo** — `pdf_service.py:27-102`: 3-4 níveis de context managers. `list.html:374-421`: callbacks aninhados. **MÉDIO.**
- [x] **Complexidade Ciclomática** — Aceitável para a maioria das funções. **OK.**
- [x] **Magic Numbers / Strings** — `pdf_service.py`: 0.6, 0.82, 0.5 sem constantes nomeadas. **MÉDIO.**
- [x] **Nomenclatura** — Consistente em português. Algumas inconsistências: `/cadastros` vs `/cadastro`, `/api/usuarios` vs `/api/usuario`. **BAIXO.**
- [x] **Consistência de Estilo** — Sem linter configurado. CSS inline misturado com classes. **MÉDIO.**

### 3.3 Tratamento de Erros

- [x] **Try/Catch Genéricos** — `app.py:29-32`: seed_admin com `except Exception: pass` (silencioso). **ALTO.**
- [x] **Erros Silenciosos** — Seed do admin falha silenciosamente sem log. **ALTO.**
- [x] **Promises sem Catch** — Frontend tem `.catch()` na maioria dos fetches. **OK.**
- [x] **Erros de Boundary** — Sem error handler global no Flask (404/500 customizados). **MÉDIO.**
- [x] **Fallbacks** — Sem degradação graciosa se DB estiver offline. **MÉDIO.**

### 3.4 Tipagem e Contratos

- [x] **Uso de `any`** — N/A (Python, não TypeScript).
- [x] **Interfaces e Types** — Python sem type hints. **BAIXO.**
- [x] **Validação de Schema** — Sem Pydantic/Marshmallow. Validação manual mínima. **MÉDIO.**
- [x] **Contratos de API** — Sem OpenAPI/Swagger. Documentado em CLAUDE.md/SPEC.md. **MÉDIO.**

### 3.5 Performance

- [x] **Queries N+1** — Não encontradas. Queries são simples SELECT ALL. **OK.**
- [x] **Queries sem Índice** — **ALTO.** Sem índices em: `proponente1_nome`, `proponente1_cpf`, `created_at`, `empreendimento`, `usuarios.email`. Apenas PKs indexados.
- [x] **Payloads Excessivos** — `/cadastros` retorna apenas resumo (bom). `/cadastros/exportar` retorna tudo sem paginação. **MÉDIO.**
- [x] **Cache** — Nenhum cache implementado (HTTP headers, Redis, in-memory). **MÉDIO.**
- [x] **Lazy Loading** — N/A (sem assets pesados além de logos). **OK.**
- [x] **Memory Leaks** — PDF: browser é fechado no finally. Conexões DB abertas/fechadas por request (sem pool). **MÉDIO.**
- [x] **Bundle Size** — N/A (vanilla JS, sem bundler). `sheet.css` com 3.8MB não usado. **BAIXO.**

---

## 4. ARQUITETURA E BOAS PRÁTICAS

### 4.1 Estrutura do Projeto

- [x] **Separação de Camadas** — Apresentação (static/), lógica (app.py), dados (services/db.py), PDF (services/pdf_service.py). **OK**, mas CSV parsing está no route handler ao invés de services/. **MÉDIO.**
- [x] **Responsabilidade Única** — `app.py` acumula rotas + auth + renderização HTML. Mas aceitável para o tamanho. **OK.**
- [x] **Organização de Pastas** — Clara e intuitiva. **OK.**
- [x] **Circular Dependencies** — Não encontradas. **OK.**

### 4.2 API Design

- [x] **Consistência de Endpoints** — Inconsistente: `/cadastros` (plural) GET vs `/cadastro` (singular) POST. `/api/usuarios` vs `/api/usuario`. **MÉDIO.**
- [x] **Paginação** — Nenhuma listagem tem paginação. **MÉDIO** (dataset pequeno atualmente).
- [x] **Versionamento** — Sem versionamento de API. **BAIXO.**
- [x] **Respostas de Erro Padronizadas** — Formato `{"erro": "mensagem"}` consistente. **OK.**
- [x] **Idempotência** — PUT e DELETE são idempotentes. **OK.**

### 4.3 Banco de Dados

- [x] **Migrations** — Sem sistema de migrations. `init.sql` + `_ensure_usuarios_table()` ad-hoc. **MÉDIO.**
- [x] **Seeds e Fixtures** — Admin seed automático no startup. **OK.**
- [x] **Transações** — Context manager `with _conn()` provê transação implícita. **OK.**
- [x] **Soft Delete vs Hard Delete** — Inconsistente: usuarios usa soft delete (`ativo=false`), fichas usa hard delete. **MÉDIO.**
- [x] **Connection Pooling** — **ALTO.** Nova conexão aberta a cada request (`_conn()` retorna nova conexão). Sem pool.

### 4.4 Observabilidade

- [x] **Logging Estruturado** — `logging.basicConfig` simples, não estruturado (não JSON). **MÉDIO.**
- [x] **Correlation ID** — Não implementado. **BAIXO.**
- [x] **Health Check** — Não existe endpoint `/health`. **MÉDIO.**
- [x] **Métricas** — Não coletadas. **MÉDIO.**
- [x] **Alertas** — Não configurados. **MÉDIO.**

### 4.5 Testes

- [x] **Cobertura Geral** — **ZERO testes.** Nenhum arquivo de teste encontrado. **CRÍTICO.**
- [x] **Testes Unitários** — Não existem.
- [x] **Testes de Integração** — Não existem.
- [x] **Testes E2E** — Não existem.
- [x] **Testes de Segurança** — Não existem.
- [x] **Mocks e Fixtures** — N/A.

### 4.6 CI/CD e DevOps

- [x] **Pipeline de CI** — Não existe. **ALTO.**
- [x] **Análise Estática** — Nenhum linter/formatter configurado. **MÉDIO.**
- [x] **Deploy Automatizado** — Manual via `docker build` + `docker stack deploy` + `--force`. **MÉDIO.**
- [x] **Ambientes** — Apenas produção. Sem staging/dev. **MÉDIO.**
- [x] **Infraestrutura como Código** — `docker-compose.yml` versionado. **OK.**

---

## 5. REFATORAÇÃO — MATRIZ DE PRIORIDADE

| Prioridade   | Qtd | Achados Principais |
|--------------|-----|--------------------|
| **Crítica**  | 5   | Segredos hardcoded, zero testes, CORS irrestrito, debug=true default, admin com senha fraca |
| **Alta**     | 12  | Sem rate limiting, sem CSRF, cookies inseguros, IDOR, sem connection pool, sem índices DB, validação fraca de senha, erros silenciosos no seed, mensagens de erro expostas |
| **Média**    | 18  | Sem security headers, sem paginação, JS inline, magic numbers, sem migrations, soft/hard delete inconsistente, sem health check, sem schema validation, arquivos órfãos |
| **Baixa**    | 7   | Naming inconsistente, sem type hints, sem versionamento API, sheet.css não usado, Server header exposto |

---

## 6. REGISTRO DE ACHADOS

### [SEC-01] Segredos Hardcoded no Código

- **Categoria:** Segurança
- **Prioridade:** Crítica
- **Arquivo(s):** app.py:22, services/db.py:5-8, docker-compose.yml:5,34, app.py:30
- **Descrição:** SECRET_KEY Flask, credenciais PostgreSQL e senha admin estão hardcoded no código-fonte.
- **Evidência:** `app.secret_key = os.environ.get("SECRET_KEY", "habitacao-secret-key-change-in-production")`
- **Recomendação:** Usar Docker secrets ou variáveis de ambiente sem fallback hardcoded. Gerar SECRET_KEY aleatório.
- **Referência:** CWE-798 (Use of Hard-coded Credentials)

### [SEC-02] CORS Irrestrito

- **Categoria:** Segurança
- **Prioridade:** Crítica
- **Arquivo(s):** app.py:23
- **Descrição:** `CORS(app)` permite qualquer origem sem restrições.
- **Evidência:** `CORS(app)` — sem parâmetros de origins, methods ou headers.
- **Recomendação:** `CORS(app, origins=["https://habitacao.amimoveis.tec.br"])`.
- **Referência:** CWE-942 (Overly Permissive CORS Policy)

### [SEC-03] Debug Mode Habilitado por Default

- **Categoria:** Segurança
- **Prioridade:** Crítica
- **Arquivo(s):** app.py:617
- **Descrição:** Debug mode default é `true`, expondo stack traces em produção.
- **Evidência:** `debug = os.environ.get("DEBUG", "true").lower() == "true"`
- **Recomendação:** Mudar default para `"false"`.
- **Referência:** CWE-215 (Insertion of Sensitive Information Into Debugging Code)

### [SEC-04] Sem Proteção CSRF

- **Categoria:** Segurança
- **Prioridade:** Alta
- **Arquivo(s):** app.py (global)
- **Descrição:** Nenhum token CSRF em formulários ou requisições state-changing.
- **Recomendação:** Implementar Flask-WTF ou tokens CSRF manuais.
- **Referência:** CWE-352 (Cross-Site Request Forgery)

### [SEC-05] Sem Rate Limiting no Login

- **Categoria:** Segurança
- **Prioridade:** Alta
- **Arquivo(s):** app.py:273-286
- **Descrição:** Endpoint `/auth/login` sem proteção contra brute force.
- **Recomendação:** Implementar Flask-Limiter com limite de 5 tentativas/minuto.
- **Referência:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)

### [SEC-06] XSS no Frontend via innerHTML

- **Categoria:** Segurança
- **Prioridade:** Média
- **Arquivo(s):** list.html:325-339, list.html:338, list.html:477
- **Descrição:** Dados do usuário (nome, CPF) inseridos via innerHTML e onclick sem sanitização.
- **Recomendação:** Usar `textContent` ou DOMPurify para sanitizar antes de inserir no DOM.
- **Referência:** CWE-79 (Cross-site Scripting)

### [SEC-07] Cookies de Sessão Sem Flags de Segurança

- **Categoria:** Segurança
- **Prioridade:** Alta
- **Arquivo(s):** app.py (configuração Flask)
- **Descrição:** Sem SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE.
- **Recomendação:** Adicionar `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`.
- **Referência:** CWE-614 (Sensitive Cookie in HTTPS Without Secure Attribute)

### [DEBT-01] Zero Cobertura de Testes

- **Categoria:** Débito Técnico
- **Prioridade:** Crítica
- **Arquivo(s):** (projeto inteiro)
- **Descrição:** Nenhum teste automatizado encontrado. Zero arquivos de teste.
- **Recomendação:** Implementar pytest com testes para: auth, CRUD fichas, PDF generation, CSV import/export.
- **Referência:** OWASP ASVS V1.1

### [DEBT-02] Sem Connection Pooling

- **Categoria:** Performance
- **Prioridade:** Alta
- **Arquivo(s):** services/db.py:29-30
- **Descrição:** Nova conexão PostgreSQL aberta a cada operação. `_conn()` retorna `psycopg2.connect()` direto.
- **Recomendação:** Usar `psycopg2.pool.SimpleConnectionPool` ou migrar para SQLAlchemy.
- **Referência:** 12 Factor App - Backing Services

### [DEBT-03] Sem Índices no Banco

- **Categoria:** Performance
- **Prioridade:** Alta
- **Arquivo(s):** init.sql
- **Descrição:** Apenas PKs indexados. Faltam índices em: `proponente1_cpf`, `created_at`, `empreendimento`, `usuarios.email`.
- **Recomendação:** `CREATE INDEX idx_fichas_cpf ON fichas(proponente1_cpf); CREATE INDEX idx_fichas_created ON fichas(created_at DESC); CREATE INDEX idx_usuarios_email ON usuarios(email);`
- **Referência:** PostgreSQL Performance Best Practices

### [DEBT-04] Seed Admin Silencioso

- **Categoria:** Débito Técnico
- **Prioridade:** Alta
- **Arquivo(s):** app.py:29-32
- **Descrição:** `except Exception: pass` no seed do admin. Falha de inicialização passa desapercebida.
- **Recomendação:** Adicionar `logger.warning()` no except ou retry com backoff.

### [DEBT-05] Arquivos Órfãos

- **Categoria:** Débito Técnico
- **Prioridade:** Baixa
- **Arquivo(s):** habitacao/RAYLSON.html, habitacao/VARIAQUES.html, habitacao/RAYLSON.pdf, static/resources/sheet.css (3.8MB)
- **Descrição:** Arquivos de referência não utilizados pelo sistema.
- **Recomendação:** Mover para pasta `_archive/` ou remover.

### [ARCH-01] Dockerfile Roda como Root

- **Categoria:** Segurança
- **Prioridade:** Alta
- **Arquivo(s):** Dockerfile
- **Descrição:** Sem diretiva `USER`. Container roda como root.
- **Recomendação:** Adicionar `RUN useradd -m appuser` e `USER appuser`.
- **Referência:** CWE-250 (Execution with Unnecessary Privileges)

### [ARCH-02] Sem Health Check

- **Categoria:** Arquitetura
- **Prioridade:** Média
- **Arquivo(s):** app.py, Dockerfile
- **Descrição:** Sem endpoint `/health` e sem HEALTHCHECK no Dockerfile.
- **Recomendação:** Adicionar rota `/health` que verifica conexão DB.

---

## 7. FERRAMENTAS RECOMENDADAS POR STACK

| Finalidade              | Para Este Projeto (Python)  |
|-------------------------|-----------------------------|
| Lint / Análise Estática | Ruff                        |
| Segurança de Deps       | pip-audit                   |
| SAST                    | Bandit, Semgrep             |
| Testes                  | pytest + pytest-flask       |
| Cobertura               | coverage.py                 |
| Performance             | py-spy, cProfile            |
| Secrets Detection       | Gitleaks, detect-secrets    |
| Container Security      | Trivy                       |

---

## 8. REFERÊNCIAS

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP ASVS (Application Security Verification Standard)](https://owasp.org/www-project-application-security-verification-standard/)
- [CWE (Common Weakness Enumeration)](https://cwe.mitre.org/)
- [NIST Secure Software Development Framework](https://csrc.nist.gov/Projects/ssdf)
- [12 Factor App](https://12factor.net/)
- [Clean Code (Robert C. Martin)](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
- [SANS Top 25 Software Errors](https://www.sans.org/top25-software-errors/)

---

> **Nota:** Este checklist é um ponto de partida. Adapte-o conforme a stack,
> o contexto de negócio e o nível de maturidade da aplicação auditada.
> Nem todos os itens se aplicam a todos os projetos.

---

## RESUMO EXECUTIVO

| Categoria | Crítica | Alta | Média | Baixa | Total |
|-----------|---------|------|-------|-------|-------|
| Segurança | 3 | 7 | 5 | 2 | 17 |
| Débito Técnico | 1 | 2 | 6 | 3 | 12 |
| Arquitetura | 0 | 2 | 6 | 2 | 10 |
| Performance | 0 | 2 | 3 | 0 | 5 |
| **Total** | **4** | **13** | **20** | **7** | **44** |

### Plano de Ação Recomendado

**Semana 1 (Crítico):**
1. Remover segredos hardcoded, usar env vars sem fallback
2. Restringir CORS para origin específica
3. Mudar debug default para `false`
4. Mudar senha admin padrão

**Semana 2-3 (Alto):**
5. Configurar session cookies seguros
6. Adicionar rate limiting no login
7. Implementar CSRF protection
8. Adicionar índices no banco
9. Implementar connection pooling
10. Configurar Dockerfile com non-root user
11. Adicionar logging no seed admin
12. Validação de senha server-side

**Mês 1-2 (Médio):**
13. Adicionar security headers
14. Extrair JS inline para arquivos separados
15. Implementar health check
16. Adicionar testes (pytest)
17. Configurar pipeline CI básico
18. Sanitizar innerHTML no frontend
