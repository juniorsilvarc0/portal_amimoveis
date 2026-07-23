---
name: detalhe-modo-novo
description: >
  Padrão do Portal AM Imóveis para transformar uma página de DETALHE estilo Salesforce
  (edição inline campo-a-campo, com lápis) numa tela de CRIAÇÃO onde TODOS os campos já
  nascem editáveis e navegáveis, sem clicar em lápis. Usar quando o usuário pedir "criar
  X com todos os campos", "o /novo deve ter tudo que tem no detalhe", "campos editáveis
  na criação", ou "igual foi feito no cliente/oportunidade novo". Cobre a detecção de
  modo, o rascunho local, os inputs persistentes, as cascatas (select→select) e a barra
  de criar. Já aplicado em `cliente_detail.html` (/cliente/novo) e
  `crm_opportunity_detail.html` (/crm/opportunities/novo).
---

# Detalhe Salesforce que também cria (modo NOVO)

No Portal, as telas ricas (Salesforce-like) são páginas de **detalhe** por id: campos
mostrados como texto, com um **lápis** por campo que troca para input inline e salva via
`PATCH` (edição um-a-um). Isso é ótimo para *atualizar*, mas **inviável para criar** um
registro do zero — o usuário teria que clicar no lápis de cada campo.

A solução (padrão): a MESMA página serve `/<recurso>/novo` num **modo NOVO** onde todo
campo já é um input persistente, com navegação natural, cascatas ligadas e uma barra
"Criar". Nada de página de formulário separada — reaproveita o layout, os cards e os
campos do detalhe. **Não altere o backend** para isso: o `POST` de criação já costuma
aceitar um `dict` cru e gravar as colunas conhecidas.

Exemplos vivos (leia-os como referência antes de replicar):
- `static/cliente_detail.html` — `/cliente/novo` (mais simples: campos + Tab/Enter).
- `static/crm_opportunity_detail.html` — `/crm/opportunities/novo` (com cascatas
  cliente / pipeline→etapa / imóvel→unidade e auto-preenchimento).

## Anatomia (6 peças)

### 1. Detecção de modo + rascunho local
No topo do IIFE, distinga `novo` de `detalhe` pela ROTA e monte um rascunho local em vez
de dar `GET .../full`:

```js
const isNew = location.pathname.endsWith('/<recurso>/novo');
const id = isNew ? null : (/* extrai id da URL */);
if (isNew && !api.can('<recurso>', 'criar')) { location.href = '/<lista>'; return; }
const canEdit = isNew ? true : api.can('<recurso>', 'editar');
let obj = isNew ? { /* defaults */ } : null;   // rascunho (buffered), sem servidor
```

`render()` ramifica logo na primeira linha: `if (isNew) { await renderNovo(); return; }`.

### 2. `fld()` vira input no modo novo
O helper que renderiza um campo editável ganha um desvio no início; o de detalhe
continua igual (texto + lápis):

```js
function fld(key, label, value, type) {
    if (isNew && key) return fldInput(key, label, type || 'text');   // input persistente
    /* ... render de detalhe (valor + editBtn) ... */
}
```

`fldInput(key, label, type, opts)` devolve `<div class="field field-new">` com um
`<input|select|textarea class="n-input" data-fieldkey data-fieldtype>` pré-preenchido de
`obj[key]` **cru** (ignora o `value` já formatado que o card passou — dinheiro/data). Tipos:
`text | number | money | date | bool | select | textarea`. Marque obrigatórios com `opts.required`.

### 3. Buffer SEM re-render (senão perde o foco)
Depois de montar o HTML, ligue cada `.n-input` a um listener que escreve em `obj` **sem
re-renderizar a página**. Re-render a cada tecla perderia foco/cursor.

```js
page.querySelectorAll('.n-input').forEach(el => {
    const key = el.dataset.fieldkey, type = el.dataset.fieldtype;
    const buffer = () => {
        let v = el.value;
        if (type === 'bool') v = (v === 'true');
        else if (type === 'money') v = brToNum(el.value);          // "1.234,50" -> 1234.5
        else if (type === 'number' || type === 'select') v = v ? parseInt(v,10) : null;
        else v = (v === '' ? null : v);
        obj[key] = v;
    };
    el.addEventListener('input', buffer);
    el.addEventListener('change', buffer);
});
```

Chame `autoMask(document.getElementById('page'))` (masks.js) para ativar máscaras de
`data-mask` (money/cep/phone). Foque o 1º campo uma única vez (guardar num flag para não
re-focar em rebuilds parciais).

### 4. Cascatas / relacionamentos (o que faz o dado "vir do cadastro")
Selects dependentes são atualizações LOCALIZADAS (troca só o `innerHTML` do select-alvo),
nunca re-render total. Padrões usados na oportunidade:
- **cliente → preview**: ao escolher o cliente, mostra os dados dele (read-only) a partir
  do objeto já carregado em `/clientes?per_page=500`.
- **pipeline → etapa**: no `change` do pipeline, `GET /crm/stages?pipeline_id=` e repinta
  o select de etapa; escolhe a 1ª etapa `tipo='aberto'` como default.
- **imóvel → unidade → auto-fill**: no `change` do imóvel, `GET /lookup/unidades?imovel_id=`
  (traz `ocupada`), repinta o select de unidade **desabilitando as ocupadas**; ao escolher
  a unidade, busca `GET /imoveis/{id}` e **copia** endereço/bairro/cidade-uf/cep/tipo/valor
  para os inputs do snapshot — só preenche o que estiver vazio (respeita override do usuário).
  Botão "+ nova" cria unidade na hora (`POST /imoveis/{id}/unidades`) e já a seleciona.

> Regra: dados de outra entidade (imóvel, cliente) **vêm do cadastro** e são COPIADOS
> (snapshot editável) na criação — o back também preenche no `POST`, mas preencher na UI
> deixa o usuário ver/ajustar. Não espelhe ao vivo.

### 5. Barra "Criar" + validação + POST
Uma barra fixa no rodapé com "Cancelar" e "Criar". `criarObj()` valida os obrigatórios,
monta o payload só com o que tem valor (`!= null && !== ''`) e faz o `POST`, redirecionando
para o detalhe do novo id:

```js
const payload = {};
Object.keys(obj).forEach(k => { if (obj[k] != null && obj[k] !== '') payload[k] = obj[k]; });
const novo = await api.post('/<recurso>', payload);
setTimeout(() => location.href = '/<recurso>/' + novo.id, 600);
```

### 6. Roteamento (pages.py)
Aponte a rota de criação para a MESMA página de detalhe:
```python
router.get("/<recurso>/novo")( _page("<recurso>_detail.html"))   # modo novo
```
Edição por id continua servindo o mesmo arquivo (a página decide pelo pathname).

## Omissões deliberadas no modo novo
Partes que exigem um registro já existente **não** aparecem na criação: abas de
Atividades/Documentos/Histórico/Notas, timeline/SLA/caminho de etapas, "próxima ação",
anexos e upload de arquivos, e campos de sistema (criado por / em). Renderize só as
SEÇÕES de dados. Campos read-only vindos de outra entidade (ex.: e-mail do proprietário)
viram select no funil ou preview.

## Pegadinhas (todas já resolvidas nos exemplos)
- **Re-render mata o foco.** Buffer em `obj`, nunca `render()` a cada tecla. Cascatas
  atualizam só o `innerHTML` do select dependente.
- **Colisão de rota.** `/<recurso>/novo` tem que ser detectada por `endsWith('/novo')`
  ANTES de tentar extrair id numérico da URL.
- **`fld()` passa valor formatado** (fmtMoney/fmtDate). No modo novo o `fldInput` ignora e
  lê `obj[key]` cru — senão o input mostra "R$ 1.234,50" e o parse quebra.
- **Máscara vs buffer** disputam o evento `input`. Ligue a máscara (`autoMask`) ANTES de
  adicionar o listener de buffer, para o buffer ler o valor já formatado e normalizar.
- **Dinheiro** entra mascarado (centavos, padrão do portal): exiba com `numToBr`, grave com
  `brToNum`. O back recebe número.
- **Permissão**: `criar` gate no `isNew`; a página inteira de detalhe usa `editar`.
- **Não duplique lógica de negócio no front.** Dedup/auto-fill definitivo é no back (o
  `POST` recusa/─completa). O front só melhora a UX (desabilita unidade ocupada, mostra 409).

## Checklist para aplicar num novo recurso
1. `isNew` + rascunho + ramo em `render()`.
2. Desvio `isNew` em `fld`/`fldBool` → `fldInput`; adicionar CSS `.n-input`/`.field-new`.
3. `renderNovo()`: carrega lookups, monta head simples + seções de dados + barra criar.
4. Selects e cascatas dos relacionamentos (repintar só o select-alvo).
5. `attachNovoHandlers()`: buffer, cascatas, `autoMask`, foco inicial, botão criar.
6. `pages.py`: `/<recurso>/novo` → `<recurso>_detail.html`.
7. Testar dirigindo o navegador (Playwright, host Chrome): todos os campos editáveis,
   cascatas, criar grava tudo, e o registro nasce completo (conferir no banco).
