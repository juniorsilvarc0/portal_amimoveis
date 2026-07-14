---
name: rbac-module
description: Guia do RBAC granular (perfis customizáveis + matriz recurso×ação ver/criar/editar/excluir) do Portal AM Imóveis. Usar quando o usuário pedir mudanças em permissões/perfis/acesso, ao adicionar um recurso novo que precise de autorização, ou ao depurar 403/acesso negado.
---

# rbac-module — RBAC granular do Portal AM Imóveis

A autorização do portal **não usa mais perfis fixos** (admin/editor/leitor). É um RBAC dinâmico: **perfis customizáveis** (`rbac_roles`) com uma **matriz recurso × ação** (`ver`/`criar`/`editar`/`excluir`), gerenciável pela UI em `/perfis`. Substituiu o antigo `usuarios.perfil` binário (mantido só por compat).

---

## Modelo de dados (init_v2.sql)

```
rbac_roles(nome UNIQUE, descricao, is_system, ativo)
  • is_system=TRUE → perfil "Administrador" protegido (não editável/deletável, tudo True)
rbac_role_permissions(role_id → rbac_roles, recurso, ver, criar, editar, excluir;
                      UNIQUE(role_id, recurso))
usuarios.role_id → rbac_roles (ON DELETE SET NULL)
  • usuarios.perfil (admin|usuario) LEGADO, mantido em sync: perfil='admin' se role.is_system
```

---

## Catálogo de recursos — `app/auth/recursos.py` (FONTE ÚNICA)

- `RECURSOS`: lista de **21 itens** `{key, label, grupo}`. `RECURSO_KEYS`: set das keys. `ACOES = ("ver","criar","editar","excluir")`.
- Usada por **seed**, **enforcement** e **UI** — adicionar/remover recurso é uma edição AQUI.
- Keys atuais: `clientes`, `habitacao`, `proposta`, `parentesco`, `recibo`, `financiamento`, `crm_leads`, `crm_opportunities`, `crm_activities`, `crm_campaigns`, `crm_pipelines`, `crm_webhooks`, `cad_cidades`, `cad_agencias`, `cad_gerentes`, `cad_parceiros`, `cad_imoveis`, `cad_correspondentes`, `cad_corretores`, `logos`, `usuarios`.
- **`settings` fica FORA da matriz** — é admin-only via `require_admin`.

---

## Enforcement — `app/auth/permissions.py`

- `require_permission(recurso, acao)` — dependency FastAPI; 403 se negado. Valida recurso/ação na importação (ValueError se inexistente → o app nem sobe).
- `require_admin` — só `is_system`/admin (usado em `settings`).
- `get_user_permissions(user)` — admin → tudo True; senão 1 query indexada por `role_id`; recurso ausente = tudo False (secure by default).
- `user_can(user, recurso, acao)` — bool.
- **Mapa método → ação:** GET=`ver`, POST=`criar`, PUT/PATCH=`editar`, DELETE=`excluir`. PDF/XLSX=`ver`. Ações especiais CRM (convert/stage/gerar-proposta)=`editar`; import CSV=`crm_leads.criar`.

**Sempre públicos/abertos** (só `get_current_user` ou sem auth — NÃO passam por `require_permission`): todo o `lookup.py`; lookup de cliente por CPF (`?cpf=`, `/por-cpf/{cpf}`); `logos` listar/obter + `/imagem`; CRM `dashboard`; `corretores` POST (self-cadastro, gate por `app_settings.corretores_publico_ativo`); `settings/public/{key}`; `lookup/cidades-publico`.

---

## JWT & sessão

- `login`/`refresh` emitem claims `role_id`, `role_nome`, `is_admin` (de `role.is_system`) + `perfil` legado.
- `get_current_user` faz fallback p/ tokens antigos: `is_admin = (perfil=='admin')`.
- `/auth/me` e `login` retornam `permissoes` (dict `{recurso:{acao:bool}}`) + `is_admin`. Mudanças de permissão **propagam sem re-login** (re-resolvidas por request no backend; o frontend lê do objeto salvo até o próximo /me).

---

## API — `/api/v1/perfis` (router `rbac.py`, repo `rbac_repo.py`, schema `rbac.py`)

| Método | Rota | Notas |
|---|---|---|
| GET | `/` | lista perfis (+ `usuarios_count`) |
| GET | `/recursos` | catálogo (21 recursos × 4 ações) p/ montar a matriz — qualquer autenticado |
| GET | `/{id}` | perfil + matriz preenchida (une RECURSOS com perms do banco) |
| POST | `/` | criar perfil + matriz |
| PUT | `/{id}` | 403 se `is_system` |
| DELETE | `/{id}` | 403 se `is_system`; 409 se há usuários ativos vinculados |

Guard: `require_permission("usuarios", <acao>)`.

---

## Seed (lifespan `main.py`, após `run_init_sql`)

`rbac_repo.seed_roles_e_migrar()` (idempotente, todo startup):
- Garante **"Administrador"** (`is_system`, tudo True — reaplicado sempre).
- Garante **"Somente Leitura"** (`ver`=True em tudo, escrita False).
- Migra usuários sem `role_id`: `perfil='admin'` → Administrador; resto → Somente Leitura.

---

## Frontend

- `api.can(recurso, acao)` em `static/js/api.js` — true se `is_admin`, senão lê `usuario.permissoes[recurso][acao]`.
- `sidebar.js` esconde itens/grupos por `can(recurso,'ver')`; mostra "Usuários" + "Perfis de Acesso" sob `usuarios.ver`.
- Padrão em cada página: guard `if(!api.can(rec,'ver')) location='/'` + `canWrite = can(rec,'criar')||can(rec,'editar')` + `canDelete = can(rec,'excluir')`.
- `static/perfis_list.html` (lista) e `static/perfis_form.html` (a **matriz**: linhas=recursos agrupados, colunas Visualizar/Criar/Editar/Excluir com toggles de linha/coluna/tudo; `is_system` abre read-only com banner).
- Form de usuário usa `select role_id` (de `/perfis`) em vez do antigo select de perfil fixo.

---

## Como adicionar um recurso novo ao RBAC

1. Adicionar a key em `app/auth/recursos.py` → `RECURSOS` (`{key, label, grupo}`). É a fonte única; o seed recria as permissões no próximo startup.
2. No router, gate cada endpoint com `Depends(require_permission("<key>", "<acao>"))`.
3. No frontend, gate a página/botões com `api.can("<key>", "<acao>")` e some no sidebar por `can("<key>","ver")`.
4. Build + deploy + `docker service update --force habitacao_portal` (ver [[feedback_deploy]]). O startup migra/garante perms; o Administrador já recebe tudo.
5. (Opcional) Conceder a key aos perfis não-admin via UI `/perfis`.

---

## Gotchas

- **Não esquecer o passo 1** — usar `require_permission` com uma key não registrada quebra a importação do módulo (o app não sobe). Registre a key ANTES.
- **`is_system` é intocável** — não tente editar/deletar o Administrador via API (403); ele é re-seedado com tudo True a cada startup.
- **`settings` não é um recurso da matriz** — é `require_admin`.
- **Endpoints públicos continuam públicos** — não envolver com `require_permission` (quebraria o self-cadastro de corretor, lookups públicos, imagem de logo).
- **Frontend é só UX** — `api.can` esconde botões, mas a verdade é o backend (`require_permission`). Nunca confie só no gate de UI.

---

## Arquivos-referência

| O quê | Onde |
|---|---|
| Catálogo de recursos (fonte única) | `app/auth/recursos.py` |
| Enforcement | `app/auth/permissions.py` |
| Repo + seed | `app/db/rbac_repo.py` |
| Router (/api/v1/perfis) | `app/routers/rbac.py` |
| Schemas | `app/schemas/rbac.py` |
| api.can | `static/js/api.js` |
| UI matriz | `static/perfis_form.html`, `static/perfis_list.html` |
| Testes | `tests/test_rbac.py` |
| Memória | [[project_rbac_module]] |
