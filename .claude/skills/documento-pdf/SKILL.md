---
name: documento-pdf
description: Guia completo para criar novas páginas de documentos (form + list + PDF via template Jinja/Playwright) no Portal AM Imóveis, seguindo o padrão estabelecido por Habitação e Proposta. Usar sempre que o usuário pedir "nova página de documento", "novo tipo de ficha/contrato/recibo com PDF", ou qualquer coisa que envolva gerar PDF a partir de dados de cliente sob o submenu Documentos.
---

# documento-pdf — criar novo módulo de documento PDF

Este skill codifica o padrão usado em **Habitação** e **Proposta** para adicionar um novo tipo de documento (ex.: Parentesco, Autorização, Recibo, Contrato, Declaração…) ao Portal AM Imóveis. Todos os documentos novos devem ficar sob o submenu **Documentos** no sidebar.

---

## Arquitetura do padrão

```
DB (init_v2.sql)  ──►  Repo (app/db/*_repo.py)  ──►  Router (app/routers/*.py)  ──►  API /api/v1/<recurso>
                                                                                         │
                                                                                         ▼
                                                                     Form vanilla (static/<recurso>_form.html)
                                                                     List vanilla  (static/<recurso>_list.html)
                                                                                         │
                                                                                         ▼
                                                          GET /<id>/pdf  ──►  pdf_service  ──►  Jinja template
                                                                                         │         (templates/<recurso>.html)
                                                                                         ▼
                                                                                   Playwright A4 1pg
```

**Princípios invariantes:**

- **Cliente é central.** Todo documento referencia `cliente_id`. NUNCA duplicar campos pessoais (nome, CPF, RG, endereço) — eles vivem em `clientes`. O repo enriquece via JOIN nas queries. **Exceção:** Recibo tem `cliente_id` NULLABLE (recibo p/ não-cadastrado) — usa LEFT JOIN e captura pagador em campos próprios. Já implementados neste padrão: Habitação, Proposta, **Parentesco** (cliente obrigatório, declaração CAIXA), **Recibo** (cliente opcional, logo dinâmica). Ver [[project_recibo_module]].
- **Upsert por CPF.** O form pode criar/editar o cliente junto com o documento. Router aceita `cliente_id` OU um bloco `cliente` com `cpf`, e faz `clientes_repo.upsert_por_cpf`.
- **Snapshot opcional.** Se o campo muda ao longo do tempo (renda, função), armazene **no próprio documento** como snapshot (ex.: `titular_renda_bruta`). Se é estável (nome, CPF, endereço), use sempre via JOIN.
- **PDF em 1 página A4.** Viewport 680px, auto-scale via Playwright, template usa tabelas HTML (não grid/flex complexo). Testar com campos longos E curtos.
- **Submenu Documentos.** Toda página nova de documento entra como submenu em `static/js/sidebar.js` no grupo "Documentos".

---

## Checklist para adicionar um documento novo

Quando o usuário pedir um novo documento, siga ESTES passos em ordem. Use TodoWrite para acompanhar.

### 1. Definir o schema (SQL)

Adicionar a tabela em `init_v2.sql` seguindo o padrão:

```sql
CREATE TABLE IF NOT EXISTS <recurso> (
    id              SERIAL PRIMARY KEY,
    cliente_id      INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    -- campos específicos do documento (use TEXT para valores formatados/moeda;
    -- INT/NUMERIC só se for pra cálculo no banco)
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_<recurso>_cliente ON <recurso>(cliente_id);
```

Regras:
- `cliente_id` é **obrigatório** (NOT NULL).
- `ON DELETE RESTRICT` — nunca deletar cliente em cascata. Se o documento tem filhos (ex.: pagamentos da proposta), aí sim `ON DELETE CASCADE` no filho para o pai-documento.
- Sempre `created_at`/`updated_at` com defaults.
- Campos de texto exibidos em PDF podem ser TEXT (já vêm formatados do front).
- `init_v2.sql` é **idempotente** — rodado em todo startup via `lifespan()` em `app/main.py`.

### 2. Criar o repository

`app/db/<recurso>_repo.py` segue o padrão de `habitacao_repo.py`:

- `_SELECT_FULL`: query base com JOIN em `clientes`, `cidades`, `conjuges` (LEFT), devolvendo `cl.* AS cliente_*`. O router/PDF service consomem esses aliases.
- `listar(page, per_page, search, **filters)`: paginação + busca ILIKE em `cl.nome`, `cl.cpf`, e campos identificadores do recurso.
- `obter(id)`: `_SELECT_FULL WHERE h.id = %s`.
- `_CAMPOS`: lista exaustiva das colunas graváveis (sem id/timestamps).
- `criar(dados)`, `atualizar(id, dados)`, `deletar(id)` — insert/update/delete padronizados.
- Se houver filhos (como `proposta_pagamentos`), adicione `obter_com_<filhos>`, `criar_com_<filhos>`, `atualizar_com_<filhos>` dentro de `with conn() as c:` para transação atômica (veja `propostas_repo.py`).

### 3. Criar o Pydantic schema

`app/schemas/<recurso>.py` — `BaseModel` com `ConfigDict(from_attributes=True)`. Três classes: `<Recurso>Base`, `<Recurso>Create` (herda Base), `<Recurso>Read` (Base + id, cliente_nome, cliente_cpf, created_at, updated_at). Todos os campos opcionais exceto `cliente_id`.

> Nota: os routers do portal hoje aceitam `body: dict` cru e fazem unpacking manual para preservar o bloco `cliente`/`conjuge`. O schema Pydantic serve sobretudo para documentação OpenAPI/Swagger. Mantenha esse padrão.

### 4. Criar o router

`app/routers/<recurso>.py` — **copie `habitacao.py` ou `propostas.py`** e renomeie. Estrutura obrigatória:

```python
router = APIRouter(prefix="/api/v1/<recurso>", tags=["<Recurso>"])

def _resolve_cliente_id(body: dict) -> int:
    # 1) cliente_id explícito → usa
    # 2) bloco cliente com cpf → clientes_repo.upsert_por_cpf
    # 3) bloco conjuge opcional → conjuges_repo.upsert_por_cliente
    # Lança 422 se faltar
```

Endpoints obrigatórios:

| Método | Rota | Dependência | Ação |
|---|---|---|---|
| GET | `/` | `require_permission("<recurso>","ver")` | listar paginado |
| GET | `/{id}` | `require_permission("<recurso>","ver")` | obter |
| POST | `/` | `require_permission("<recurso>","criar")` | criar (resolve cliente + grava doc) |
| PUT | `/{id}` | `require_permission("<recurso>","editar")` | atualizar (opcional: sync cliente/cônjuge) |
| DELETE | `/{id}` | `require_permission("<recurso>","excluir")` | deletar |
| GET | `/{id}/pdf` | `require_permission("<recurso>","ver")` | Response `application/pdf` |

> **RBAC (importante):** a autorização NÃO é mais `require_role("admin")`. Use `require_permission("<recurso>","<acao>")` de `app/auth/permissions.py`. ANTES disso, registre a key `<recurso>` no catálogo `app/auth/recursos.py` (lista `RECURSOS`, com `{key,label,grupo}`) — é a FONTE ÚNICA; o seed recria as permissões no próximo startup. Sem registrar a key, `require_permission` lança erro na importação. No frontend, gate a página com `if(!api.can('<recurso>','ver'))` e botões com `api.can('<recurso>','criar'|'editar'|'excluir')`. Ver [[project_rbac_module]] / skill `rbac-module`.

O endpoint `/pdf` enriquece o dict do repo com campos adicionais do cliente que o template precisa (ver `propostas.py:183-195` para referência) e chama `gerar_pdf_<recurso>()` do `pdf_service`.

> **Export XLSX (opcional):** Habitação tem `GET /{id}/xlsx` → `app/services/excel_service.py` (`gerar_xlsx_habitacao`, openpyxl, reaproveita o mapper do pdf_service). Replicável para qualquer documento que o cliente queira em Excel.

Registrar em `app/main.py`:
```python
from app.routers import <recurso>
app.include_router(<recurso>.router)
```

### 5. Criar o template Jinja do PDF

`templates/<recurso>.html` — regras **inegociáveis** (veja `feedback_pdf`):

```html
<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: Calibri, Arial, sans-serif;
    font-size: 9pt; color: #000; line-height: 1.2;
    width: 180mm;   /* largura útil A4 com 15mm margem */
  }
  table { width: 100%; border-collapse: collapse; }
  td, th { border: 1px solid #000; padding: 2px 4px; vertical-align: middle; }
  .sh { background: #a5a5a5; text-align: center; font-weight: bold; }  /* section header */
  .lb { font-weight: bold; white-space: nowrap; }                      /* label */
  .ct { text-align: center; }
  .b  { font-weight: bold; }
</style></head>
<body>
<div id="wrap">
  <!-- conteúdo em TABELAS. Nada de flex/grid complexo. -->
  <!-- Cada seção é uma <table> com cabeçalho .sh e linhas de dados. -->
  {{ campo_flat }}
</div>
</body></html>
```

**Obrigatório:**
- Wrapper `<div id="wrap">` — o `pdf_service._gerar_pdf` mede `wrap.scrollHeight` e calcula o scale.
- Fonte Calibri/Arial 9pt (pode ir até 10pt se houver folga).
- Body com `width: 180mm` para bater com a área útil (A4 210mm − 2×15mm).
- Usar **tabelas HTML** — parece documento oficial, não Excel/planilha com letras de coluna.
- `{{ autoescape }}` está ON no Jinja — seguro contra XSS, não precisa escapar manualmente.

**NÃO usar:**
- Imagens externas (usar `/static/logoAM.png` via `logo_path` absoluto, como em `gerar_pdf_proposta`).
- CSS externo (tudo inline no `<style>`).
- Fontes web (a página carrega com `file://`, fontes remotas falham).
- Divs com display flex/grid para layout principal — tabelas renderizam muito mais previsível no Chromium headless.

### 6. Adicionar função de alto nível no pdf_service

Em `app/services/pdf_service.py`:

```python
def gerar_pdf_<recurso>(dados: dict) -> bytes:
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("<recurso>.html")
    ctx = _map_<recurso>_to_template(dados)
    ctx["logo_path"] = str(STATIC_DIR / "logoAM.png")  # se usar logo
    return gerar_pdf(template.render(**ctx))


def _map_<recurso>_to_template(d: dict) -> dict:
    """Mapeia o dict do repo (cliente_*, conjuge_*, <recurso>_*)
    para os campos flat que o template espera."""
    d = d or {}
    return {
        "cliente_nome": d.get("cliente_nome") or "",
        "cliente_cpf":  _format_cpf(d.get("cliente_cpf")),
        # ... todos os {{ placeholders }} do template com `or ""` default
    }
```

**Mapper flat é obrigatório.** O template usa `{{ chave_simples }}` (sem `obj.sub.attr`), e o mapper converte o dict aninhado do repo para esse formato. Isso evita `UndefinedError` no Jinja e mantém o template legível pelo cliente (que às vezes pede ajustes visuais direto).

A função `_gerar_pdf()` já existe e cuida do resto: viewport 680px, margens 15mm/10mm, auto-scale se `scrollHeight > USABLE_H_PX`, safety-retry se ainda virar 2+ páginas. **Não mexer nela.**

### 7. Criar os arquivos HTML do frontend

Dois arquivos em `static/`:

**`<recurso>_list.html`** — copiar `habitacao_list.html`, trocar:
- `<title>`, `topbar-title`, `page-title`, `page-subtitle`.
- `href="/habitacao/novo"` → `/<recurso>/novo`.
- `renderSidebar(..., '/<recurso>', usuario)`.
- `new DataGrid(..., { endpoint: '/<recurso>', columns: [...] })` — escolher colunas relevantes.
- Ação "Gerar PDF" na coluna de actions: abre `/api/v1/<recurso>/<id>/pdf` em nova aba (herda o token via cookie/localStorage? NÃO — o portal usa Bearer no header, então o link direto não funciona; use `api.get` + `blob` + `URL.createObjectURL`, como habitacao_list já faz).

**`<recurso>_form.html`** — copiar `habitacao_form.html` e:
- Trocar título, endpoint, campos.
- Manter **exatamente** a ordem de includes: `api.js`, `sidebar.js`, `masks.js`, `forms.js`, `modal.js`, `cpf_lookup.js`.
- `forms.init(form)` DEVE rodar antes de `getElementById` em qualquer `data-field="..."` (esses divs são substituídos por inputs reais só depois do init).
- Secção "01. Identificação do Cliente" usa `<div data-field="cpf">` + `<div data-field="nome">` etc., reaproveitando os componentes de `forms.js`.
- `attachCpfLookup(cpfInput, onFound, onNotFound)` preenche e trava os campos do cliente quando CPF existe; libera quando não existe (novo cliente).
- No `carregarFicha(editId)` — lê os campos pessoais do objeto como `ficha.cliente_nome`, `ficha.cliente_whatsapp1` (vindos do JOIN do repo).
- `montarPayload()`:
  - Se `clienteId` conhecido → `payload.cliente_id = clienteId`.
  - Senão → `payload.cliente = { cpf, nome, whatsapp1, email }`.
  - Se tem cônjuge → `payload.conjuge = { nome, ... }`.
  - Resto dos campos do documento direto no `payload`.
- Submit: `api.post('/<recurso>', payload)` ou `api.put('/<recurso>/<id>', payload)`.

### 8. Registrar as rotas de páginas

Em `app/routers/pages.py`, adicionar:

```python
# ---------------------------------------------------------------------------
# <Recurso>
# ---------------------------------------------------------------------------
router.get("/<recurso>")(         _page("<recurso>_list.html"))
router.get("/<recurso>/novo")(    _page("<recurso>_form.html"))

@router.get("/<recurso>/{id}/editar")
async def <recurso>_editar(id: int):
    path = BASE / "<recurso>_form.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return _em_construcao("Editar <Recurso>", "<recurso>_form")
```

### 9. Adicionar ao submenu Documentos no sidebar

Em `static/js/sidebar.js`, dentro do grupo `Documentos`:

```js
{
    label: 'Documentos', icon: SVG.file, group: true,
    items: [
        { label: 'Habitação', href: '/habitacao' },
        { label: 'Proposta',  href: '/proposta' },
        { label: '<Recurso>', href: '/<recurso>' },   // ← novo
    ]
},
```

O helper `isActive` já trata grupos automaticamente — o grupo expande quando o usuário está na subpágina.

### 10. Build + deploy + smoke test

```bash
cd /home/ubuntu/habitacao
docker build -f Dockerfile.portal -t habitacao-portal:latest .
docker stack deploy -c docker-compose.yml habitacao
docker service update --force habitacao_portal   # OBRIGATÓRIO (ver feedback_deploy)

# Smoke test
curl -sk https://portal.amimoveis.tec.br/healthz
TOKEN=$(curl -sk -X POST https://portal.amimoveis.tec.br/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"senha\":\"$ADMIN_PASSWORD\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Criar registro de teste (nunca deletar dados reais — ver feedback_never_delete)
curl -sk -X POST https://portal.amimoveis.tec.br/api/v1/<recurso> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"cliente":{"cpf":"00000000000","nome":"TESTE DOCUMENTO"},"campo_x":"..."}'

# Verificar PDF: precisa ser arquivo PDF e exatamente 1 página
curl -sk -H "Authorization: Bearer $TOKEN" \
  https://portal.amimoveis.tec.br/api/v1/<recurso>/<id>/pdf -o /tmp/test.pdf
file /tmp/test.pdf                            # deve dizer "PDF document"
pdfinfo /tmp/test.pdf | grep Pages            # deve dizer "Pages: 1"
```

---

## Convenções & gotchas

- **CPF sempre normalizado** (só dígitos) no banco e no pipeline. Formatação `000.000.000-00` **só** no `_format_cpf` do pdf_service.
- **Valores monetários como TEXT** (ex.: "R$ 1.234,56") — o front já formata, o template só imprime.
- **Empreendimentos hardcoded** no form (DIRCEU 8 LOTES, PLANALTO, REVOADA DOS GUARAS FASE 1/2, LUAR DO SERTAO) ou via `/api/v1/lookup/imoveis`. Veja habitacao_form.html:459-469.
- **Cache-bust**: o middleware em `app/main.py:85-110` força `no-cache` em `.html/.js/.css`. Após deploy, não precisa pedir pro usuário dar hard refresh.
- **Autenticação**: JWT Bearer em localStorage. O link direto `<a href="/api/v1/.../pdf">` NÃO funciona — tem que buscar via `fetch` com header Authorization e criar Blob URL. Veja como `habitacao_list.html` faz.
- **NÃO usar `db` como hostname do Postgres** — é VIP do Swarm e dá SCRAM auth fail. Usar `habitacao_db`.
- **Template não está em `static/`** — está em `templates/`. Se copiar acidentalmente para static/ o pdf_service não acha.
- **Testar pelo menos com um registro curto E um longo** antes de declarar pronto. O auto-scale tem piso em 0.6 — se o conteúdo for realmente gigante, pode vir ilegível. Se isso acontecer, reduza tamanhos de fonte, espessura de padding, ou divida em seções menores.
- **Nunca deletar dados reais** durante testes — criar registros "TESTE..." e limpar apenas esses.

---

## Arquivos-referência

| O quê | Onde |
|---|---|
| PDF service (motor Playwright + mapper) | `app/services/pdf_service.py` |
| Repository padrão | `app/db/habitacao_repo.py` |
| Repository com filhos (transação) | `app/db/propostas_repo.py` |
| Router padrão | `app/routers/habitacao.py` |
| Router com nested children | `app/routers/propostas.py` |
| Pydantic schemas | `app/schemas/habitacao.py`, `proposta.py` |
| Template PDF simples | `templates/ficha_habitacional.html` |
| Template PDF com logo e muitos campos | `templates/proposta_imoveis.html` |
| Form vanilla completo (CPF lookup, edit mode) | `static/habitacao_form.html` |
| List com DataGrid + PDF blob download | `static/habitacao_list.html` |
| Rotas de páginas | `app/routers/pages.py` |
| Sidebar / submenu Documentos | `static/js/sidebar.js` |
| Schema canônico | `init_v2.sql` |

---

## Comando rápido

Para scaffoldar um documento novo do zero, use o slash command `/novo-documento <nome>` (veja `.claude/commands/novo-documento.md`).
