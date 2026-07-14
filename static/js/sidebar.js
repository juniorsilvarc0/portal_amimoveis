/* ============================================================
   sidebar.js — AM Imoveis Portal
   Renderiza sidebar + lógica de toggle, grupos colapsáveis,
   active state, hamburguer mobile.
   Expõe: window.renderSidebar
   ============================================================ */

(function () {
    'use strict';

    /* ---- SVG Icons (Lucide-like, 18x18 stroke) ---- */
    const SVG = {
        home: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',

        users: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',

        file: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',

        doc: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',

        bank: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="12" rx="2"/><path d="M7 8V6a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v2"/><line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/></svg>',

        grid: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',

        shield: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',

        logout: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',

        chevron: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',

        menu: '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',

        collapse: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
    };

    /**
     * Definição do menu.
     * @param {object} user - { perfil: 'admin'|'usuario', nome, ... }
     * @returns {Array}
     */
    function buildMenuItems(user) {
        // Helper de permissão. Se window.api não existir, trata como sem permissão.
        const can = (recurso, acao) =>
            (window.api && typeof window.api.can === 'function')
                ? window.api.can(recurso, acao)
                : false;

        const rawItems = [
            // Dashboard ('/') é sempre visível.
            { label: 'Dashboard',      icon: SVG.home,   href: '/' },
            { label: 'Clientes',       icon: SVG.users,  href: '/clientes', recurso: 'clientes' },
            {
                label: 'CRM', icon: SVG.users, group: true,
                items: [
                    { label: 'Dashboard',     href: '/crm',               recurso: 'crm_leads' },
                    { label: 'Leads',         href: '/crm/leads',         recurso: 'crm_leads' },
                    { label: 'Oportunidades', href: '/crm/opportunities', recurso: 'crm_opportunities' },
                    { label: 'Kanban',        href: '/crm/kanban',        recurso: 'crm_opportunities' },
                    { label: 'Atividades',    href: '/crm/activities',    recurso: 'crm_activities' },
                    { label: 'Campanhas',     href: '/crm/campaigns',     recurso: 'crm_campaigns' },
                    { label: 'Pipelines',     href: '/crm/pipelines',     recurso: 'crm_pipelines' },
                    { label: 'Webhooks',      href: '/crm/webhooks',      recurso: 'crm_webhooks' },
                    { label: 'Importar CSV',  href: '/crm/import',        recurso: 'crm_leads' },
                ]
            },
            {
                label: 'Documentos', icon: SVG.file, group: true,
                items: [
                    { label: 'Habitação',           href: '/habitacao',   recurso: 'habitacao' },
                    { label: 'Proposta',            href: '/proposta',    recurso: 'proposta' },
                    { label: 'Termo de Parentesco', href: '/parentesco',  recurso: 'parentesco' },
                    { label: 'Recibo',              href: '/recibos',     recurso: 'recibo' },
                ]
            },
            { label: 'Financiamento',  icon: SVG.bank,   href: '/financiamento', recurso: 'financiamento' },
            {
                label: 'Cadastros', icon: SVG.grid, group: true,
                items: [
                    { label: 'Cidades',          href: '/cadastros/cidades',          recurso: 'cad_cidades' },
                    { label: 'Agências',         href: '/cadastros/agencias',         recurso: 'cad_agencias' },
                    { label: 'Gerentes',         href: '/cadastros/gerentes',         recurso: 'cad_gerentes' },
                    { label: 'Parceiros',        href: '/cadastros/parceiros',        recurso: 'cad_parceiros' },
                    { label: 'Imóveis',          href: '/cadastros/imoveis',          recurso: 'cad_imoveis' },
                    { label: 'Correspondentes',  href: '/cadastros/correspondentes',  recurso: 'cad_correspondentes' },
                    { label: 'Corretores',       href: '/cadastros/corretores',       recurso: 'cad_corretores' },
                    { label: 'Logos',            href: '/cadastros/logos',            recurso: 'logos' },
                ]
            },
        ];

        // Filtra cada item/grupo pela permissão de VER.
        // Item simples sem 'recurso' (ex.: Dashboard '/') é sempre visível.
        const items = [];
        rawItems.forEach(item => {
            if (item.group) {
                const visibleChildren = (item.items || []).filter(child =>
                    !child.recurso || can(child.recurso, 'ver')
                );
                // Grupo sem nenhum filho visível é omitido.
                if (visibleChildren.length) {
                    items.push(Object.assign({}, item, { items: visibleChildren }));
                }
            } else if (!item.recurso || can(item.recurso, 'ver')) {
                items.push(item);
            }
        });

        // Administração de acessos (gated por 'usuarios').
        if (can('usuarios', 'ver')) {
            items.push({ label: 'Usuários',         icon: SVG.shield, href: '/usuarios' });
            items.push({ label: 'Perfis de Acesso', icon: SVG.shield, href: '/perfis' });
        }

        // 'Sair' é sempre visível.
        items.push({ label: 'Sair', icon: SVG.logout, action: 'logout' });

        return items;
    }

    /**
     * Verifica se um item (ou algum filho de grupo) está ativo.
     */
    function isActive(item, currentPath) {
        if (item.href) {
            if (item.href === '/') return currentPath === '/';
            return currentPath.startsWith(item.href);
        }
        if (item.group && item.items) {
            return item.items.some(child => currentPath.startsWith(child.href));
        }
        return false;
    }

    /**
     * Renderiza a sidebar no container fornecido.
     *
     * @param {HTMLElement|string} container - Elemento .sidebar ou selector
     * @param {string} [currentPath]         - window.location.pathname
     * @param {object} [user]                - { nome, perfil }
     */
    function renderSidebar(container, currentPath, user) {
        if (typeof container === 'string') container = document.querySelector(container);
        if (!container) return;

        currentPath = currentPath || window.location.pathname;
        user = user || (window.api && window.api.currentUser ? window.api.currentUser() : null);

        const items = buildMenuItems(user);

        // Header
        const header = document.createElement('div');
        header.className = 'sidebar-header';

        const logo = document.createElement('img');
        logo.src = '/static/logoBRANCA.png';
        logo.alt = 'AM Imoveis';
        logo.style.height = '48px';

        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'sidebar-toggle';
        toggleBtn.innerHTML = SVG.collapse;
        toggleBtn.title = 'Recolher menu';

        header.appendChild(logo);
        header.appendChild(toggleBtn);

        // Nav
        const nav = document.createElement('ul');
        nav.className = 'sidebar-nav';

        items.forEach(item => {
            const li = document.createElement('li');

            if (item.group) {
                // Grupo colapsável
                const groupDiv = document.createElement('div');
                groupDiv.className = 'sidebar-group';

                const groupActive = isActive(item, currentPath);
                if (groupActive) groupDiv.classList.add('open');

                const groupHeader = document.createElement('div');
                groupHeader.className = 'sidebar-group-header';
                if (groupActive) groupHeader.style.color = 'white';

                groupHeader.innerHTML =
                    '<span class="nav-icon">' + item.icon + '</span>' +
                    '<span class="nav-label">' + _escHtml(item.label) + '</span>' +
                    '<span class="sidebar-group-arrow">' + SVG.chevron + '</span>';

                groupHeader.addEventListener('click', () => {
                    groupDiv.classList.toggle('open');
                });

                const groupItems = document.createElement('ul');
                groupItems.className = 'sidebar-group-items';

                item.items.forEach(child => {
                    const childLi = document.createElement('li');
                    const childA = document.createElement('a');
                    childA.href = child.href;
                    childA.innerHTML = '<span class="nav-label">' + _escHtml(child.label) + '</span>';
                    if (currentPath.startsWith(child.href)) childA.classList.add('active');
                    childLi.appendChild(childA);
                    groupItems.appendChild(childLi);
                });

                groupDiv.appendChild(groupHeader);
                groupDiv.appendChild(groupItems);
                li.appendChild(groupDiv);

            } else if (item.action === 'logout') {
                const a = document.createElement('a');
                a.href = '#';
                a.innerHTML =
                    '<span class="nav-icon">' + (item.icon || '') + '</span>' +
                    '<span class="nav-label">' + _escHtml(item.label) + '</span>';
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (window.api && typeof window.api.logout === 'function') {
                        window.api.logout();
                    } else {
                        window.location.href = '/login';
                    }
                });
                li.appendChild(a);

            } else {
                const a = document.createElement('a');
                a.href = item.href;
                a.innerHTML =
                    '<span class="nav-icon">' + (item.icon || '') + '</span>' +
                    '<span class="nav-label">' + _escHtml(item.label) + '</span>';
                if (isActive(item, currentPath)) a.classList.add('active');
                li.appendChild(a);
            }

            nav.appendChild(li);
        });

        // User info no rodapé
        const footer = document.createElement('div');
        footer.className = 'sidebar-footer';

        if (user) {
            const userInfo = document.createElement('div');
            userInfo.style.cssText = 'padding: 12px 16px; font-size: 12px; color: rgba(255,255,255,0.6); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';
            userInfo.textContent = user.nome || user.email || '';
            const perfil = document.createElement('div');
            perfil.style.cssText = 'padding: 0 16px 10px; font-size: 10px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 0.8px;';
            perfil.textContent = user.perfil || '';
            footer.appendChild(userInfo);
            footer.appendChild(perfil);
        }

        // Monta sidebar
        container.innerHTML = '';
        container.appendChild(header);
        container.appendChild(nav);
        container.appendChild(footer);

        // ---- Lógica de toggle (collapse) ---- //
        toggleBtn.addEventListener('click', () => {
            container.classList.toggle('collapsed');
            const isCollapsed = container.classList.contains('collapsed');
            toggleBtn.style.transform = isCollapsed ? 'rotate(180deg)' : '';
            // Atualiza margin do conteúdo principal se existir
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                mainContent.style.marginLeft = isCollapsed
                    ? 'var(--sidebar-collapsed)'
                    : 'var(--sidebar-width)';
            }
        });

        // ---- Lógica mobile (hamburguer) ---- //
        _setupMobile(container);
    }

    function _setupMobile(sidebar) {
        // Cria backdrop se não existir
        let backdrop = document.querySelector('.sidebar-backdrop');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.className = 'sidebar-backdrop';
            document.body.appendChild(backdrop);
        }

        backdrop.addEventListener('click', () => {
            sidebar.classList.remove('open');
            backdrop.classList.remove('visible');
        });

        // Topbar hamburguer
        const topbar = document.querySelector('.topbar-hamburger');
        if (topbar) {
            topbar.addEventListener('click', () => {
                sidebar.classList.toggle('open');
                backdrop.classList.toggle('visible', sidebar.classList.contains('open'));
            });
        }

        // Fechar ao navegar (mobile)
        sidebar.querySelectorAll('a').forEach(a => {
            if (a.getAttribute('href') && a.getAttribute('href') !== '#') {
                a.addEventListener('click', () => {
                    if (window.innerWidth <= 768) {
                        sidebar.classList.remove('open');
                        backdrop.classList.remove('visible');
                    }
                });
            }
        });
    }

    function _escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    window.renderSidebar = renderSidebar;
    window._SIDEBAR_SVG = SVG; // exposto para uso externo se necessário
})();
