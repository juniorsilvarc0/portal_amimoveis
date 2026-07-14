---
description: Scaffold de um novo módulo de documento PDF no Portal AM Imóveis (tabela + repo + schema + router + template Jinja + form/list vanilla + submenu Documentos). Segue o padrão de Habitação/Proposta descrito no skill `documento-pdf`.
argument-hint: <nome-singular> [campos-separados-por-virgula]
---

# /novo-documento — scaffold de módulo de documento PDF

Argumentos: `$ARGUMENTS`

Exemplos:
- `/novo-documento parentesco`
- `/novo-documento autorizacao grau,parente,observacao`
- `/novo-documento recibo valor,referencia,data_emissao`

## O que este comando deve fazer

Você é o agente. Antes de começar, **leia o skill completo** em `.claude/skills/documento-pdf/SKILL.md` — ele é a fonte de verdade do padrão. Este command apenas orquestra os passos.

Siga **em ordem**, usando TodoWrite para acompanhar:

1. **Parse dos argumentos.** O primeiro token é o nome singular do recurso (ex.: `parentesco`). Derive:
   - `recurso` = snake_case plural simples (ex.: `parentescos`) — usado em tabela, prefixo API, rotas.
   - `Recurso` = PascalCase singular (ex.: `Parentesco`) — usado em labels, títulos.
   - `campos` = lista opcional a partir do 2º argumento em diante (split por vírgula). Se vazio, usar apenas um placeholder `observacoes TEXT`.
   - Se o usuário não passou argumento nenhum, pergunte qual é o nome do documento e quais campos ele quer antes de prosseguir.

2. **Confirmar com o usuário** (uma mensagem curta) o plano: nome do recurso, tabela, campos, rotas que serão criadas. Só prosseguir com OK.

3. **Criar/alterar os arquivos** seguindo o checklist do skill. Em ordem:
   1. Adicionar `CREATE TABLE IF NOT EXISTS <recurso> (...)` no final de `init_v2.sql` com FK em `clientes(id)` + `created_at`/`updated_at` + índice `cliente_id`.
   2. Criar `app/db/<recurso>_repo.py` copiando o padrão de `habitacao_repo.py`, adaptando `_SELECT_FULL`, `_CAMPOS`, busca, etc.
   3. Criar `app/schemas/<recurso>.py` com Base/Create/Update/Read.
   4. Criar `app/routers/<recurso>.py` copiando `habitacao.py` e trocando prefix/tag/imports/nomes. Incluir `_resolve_cliente_id`, CRUD completo e endpoint `/{id}/pdf`.
   5. Registrar o router em `app/main.py` (import + `include_router`).
   6. Criar `templates/<recurso>.html` com as regras do skill (wrapper `#wrap`, tabelas, Calibri 9pt, 180mm). Inclua todos os campos passados como argumento, agrupados em seções lógicas com `.sh` headers.
   7. Adicionar `gerar_pdf_<recurso>` e `_map_<recurso>_to_template` em `app/services/pdf_service.py`.
   8. Criar `static/<recurso>_list.html` (DataGrid + botão PDF via blob) e `static/<recurso>_form.html` (CPF lookup, edit mode, submit).
   9. Registrar as 3 rotas de página em `app/routers/pages.py` (`/<recurso>`, `/<recurso>/novo`, `/<recurso>/{id}/editar`).
   10. Adicionar item no submenu `Documentos` em `static/js/sidebar.js`.

4. **Build + deploy + smoke test** seguindo o bloco no skill (build, stack deploy, `--force`, healthz, login, POST de teste com nome "TESTE …", GET /pdf, verificar `file` e `pdfinfo`).

5. **Reportar ao usuário:**
   - Lista de arquivos criados/alterados com caminhos em markdown links.
   - Output do `pdfinfo` provando 1 página.
   - Instrução de como testar no browser (`https://portal.amimoveis.tec.br/<recurso>`).
   - Qualquer decisão não-óbvia que você tomou (ex.: nome de coluna, agrupamento de seções no template).

## Regras importantes (não violar)

- **NUNCA delete dados reais** durante o teste. Crie registro com nome `TESTE <RECURSO>` usando CPF `00000000000` (ou outro explicitamente de teste) e deixe para o usuário decidir se apaga.
- **SEMPRE rodar `docker service update --force habitacao_portal`** depois do `docker stack deploy`.
- **Template PDF tem que caber em 1 página A4**. Se `pdfinfo` mostrar 2+ páginas, volte no template e reduza: fonte para 8pt, padding das células, elimine seções vazias, ou encolha margens do body.
- **Nunca mexer em Habitação ou Proposta** existentes, só acrescentar o novo recurso. Sidebar: apenas adicionar uma linha no array `items` do grupo Documentos.
- **CPF normalizado** (só dígitos) no banco; formatação só no `_format_cpf` do pdf_service.
- Usar Português-BR nas labels, títulos, mensagens de erro e nomes de colunas.
- Se o schema precisar de filhos (tipo `proposta_pagamentos`), siga o padrão transacional de `propostas_repo.py` com `criar_com_<filhos>` / `atualizar_com_<filhos>`.

## Quando NÃO usar este comando

- Se o usuário quer apenas **editar** um documento existente (use edição direta dos arquivos).
- Se o documento precisa de lógica **muito custom** (integração com API externa, cálculo financeiro complexo) — nesse caso, crie o scaffold com este comando e depois adicione a lógica separadamente.
- Se o usuário está pedindo um **relatório/dashboard**, não um documento individual por cliente — isso não é um "documento PDF" no sentido deste padrão.
