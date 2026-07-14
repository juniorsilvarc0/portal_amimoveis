# PRD - Sistema de Fichas Habitacionais AM Imoveis

## Visão Geral

Sistema web para cadastro e geração de fichas de entrevista habitacional (PMCMV) em PDF. Operado pela AM Imoveis (Andreia Miranda Imoveis) em parceria com ZM (correspondente bancário).

**URL:** https://habitacao.amimoveis.tec.br

## Problema

Fichas de entrevista habitacional eram preenchidas manualmente via Google Sheets, exportadas como PDF. Gerava inconsistência, retrabalho, falta de controle de acesso e dificuldade de gestão.

## Solução

Aplicação web completa com:
- Formulário web com validação e máscara de campos monetários
- Geração automática de PDF profissional (1 página A4)
- Banco de dados para persistência dos cadastros
- Sistema de autenticação com 3 níveis de acesso
- Interface responsiva (desktop + mobile)
- Importação/exportação de dados via CSV
- Filtro por empreendimento na listagem

## Funcionalidades

### Cadastro de Fichas (CRUD)
- Formulário com 46 campos organizados em 9 seções
- Campos monetários com máscara R$ em tempo real (11 campos)
- Campo idade aceita apenas número, PDF exibe "X ANOS"
- Uppercase automático em campos de texto
- Coobrigado opcional (toggle)
- Valores padrão: Construtora Roper, proprietários construtora
- Campo empreendimento com 5 opções fixas
- Auto-preenchimento: prop1_nome herda de proponente1_nome

### Listagem e Filtros
- Busca por nome ou CPF em tempo real
- Filtro multi-select por empreendimento (checkbox dropdown)
- Empreendimentos: Dirceu 8 Lotes, Planalto, Revoada dos Guaras Fase 1/2, Luar do Sertao
- Tabela com colunas: #, Empreendimento, Nome, CPF, Telefone, Valor Total, Financiado, Data, Ações
- Badges de total de cadastros e usuário logado
- Ações por linha: PDF, Editar, Excluir (conforme perfil)

### Importação/Exportação CSV
- Exportar todos os cadastros como CSV
- Download de modelo CSV vazio (template)
- Importar cadastros via upload CSV (admin/editor)
- Validação: nome + CPF obrigatórios por linha
- Relatório de linhas importadas vs ignoradas

### Geração de PDF
- Documento profissional com tabelas (sem aparência de planilha)
- Sempre 1 página A4 (auto-scale proporcional)
- Estrutura idêntica ao modelo de referência (exemplo.pdf)
- Margens equilibradas, documento centralizado
- Declaração + linhas de assinatura no rodapé

### Autenticação e Controle de Acesso
- Login com email + senha (sessão Flask)
- 3 perfis: admin (tudo), editor (CRUD fichas), leitor (ver + PDF)
- CRUD de usuários (admin only)
- UI adaptativa por perfil (botões aparecem/somem)
- Soft delete de usuários (desativação)

### Campos do Formulário (46 variáveis)

| Seção | Campos |
|---|---|
| Empreendimento | empreendimento (select com 5 opções) |
| Dados Participantes | proponente1_nome, proponente1_idade, proponente1_cpf, coobrigado_nome, dependentes, contato_telefone, contato_email |
| Rendimento Prop. 1 | prop1_nome, prop1_funcao, prop1_empresa, prop1_admissao, prop1_renda_bruta, prop1_renda_liquida, prop1_extras |
| Rendimento Prop. 2 | prop2_nome, prop2_funcao, prop2_empresa, prop2_admissao, prop2_renda_bruta, prop2_renda_liquida, prop2_extras |
| Compromissos | emprestimos, moradia_tipo, transportes |
| Relacionamento Caixa | conta, conta_salario, open_finance, opt_in, biometria, cartao_credito, crot |
| Financiamento | valor_total, subsidio, entrada, negociacao, financiado, parcela, prazo, amortizacao, utilizar_fgts |
| Moradia/Imóvel | endereco_imovel, proprietarios, construtora, proprietarios_construtora |
| Taxas e Seguros | taxa_vista_contrato, seguridade |

## Stack Técnica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.12 + Flask |
| Banco de Dados | PostgreSQL 16 (container dedicado) |
| PDF Generation | Playwright (headless Chromium) |
| Template | Jinja2 |
| Auth | Flask session + werkzeug (scrypt) |
| Frontend | HTML/CSS/JS vanilla, DM Sans font |
| Deploy | Docker Swarm + Traefik (SSL automático) |
| DNS | habitacao.amimoveis.tec.br |

## Design

- Marca: AM Imoveis (Andreia Miranda)
- Cor primária: #E5094B (rosa/vermelho)
- Cor secundária: #065676 (azul escuro)
- Font: DM Sans (Google Fonts)
- Responsivo: mobile-first (320px, 480px, 768px)

## Referência

- Inspirado na rota /contrato do projeto rdguara (Node.js + Express + Puppeteer)
- Modelo de referência: habitacao/exemplo.pdf
