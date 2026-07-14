/* ============================================================
   datagrid.js — AM Imoveis Portal
   DataGrid reusável: paginação server-side, ordenação, filtros
   por coluna debounced, busca global, export CSV client-side.
   Mobile: tabela vira lista de cards.
   Expõe: window.DataGrid
   ============================================================ */

(function () {
    'use strict';

    var DEBOUNCE_MS = 400;

    /**
     * @typedef {object} ColumnDef
     * @property {string}   key       - Chave no objeto de dado
     * @property {string}   label     - Cabeçalho exibido
     * @property {boolean}  [sortable=false]
     * @property {boolean}  [filter=false]   - Exibe input de filtro por coluna
     * @property {string}   [filterType='text'] - 'text' | 'select'
     * @property {Array}    [filterOptions]  - [{value, label}] para type=select
     * @property {function} [format]  - function(value, row) → string HTML
     * @property {string}   [align]   - 'left'|'center'|'right'
     * @property {string}   [width]   - CSS width ex: '120px'
     * @property {boolean}  [html=false] - se true, innerHTML; senão textContent
     */

    class DataGrid {
        /**
         * @param {HTMLElement|string} container - Element ou selector
         * @param {object} options
         * @param {ColumnDef[]} options.columns
         * @param {string}      options.endpoint        - ex: '/cadastros'
         * @param {function}    [options.rowActions]    - function(row) → [{label, icon, className, onClick}]
         * @param {boolean}     [options.searchable=true]
         * @param {function}    [options.onRowClick]    - function(row)
         * @param {number}      [options.perPage=25]
         * @param {boolean}     [options.exportable=true]
         * @param {string}      [options.emptyMessage='Nenhum registro encontrado.']
         */
        constructor(container, options) {
            this.container = typeof container === 'string'
                ? document.querySelector(container)
                : container;

            if (!this.container) throw new Error('DataGrid: container não encontrado');

            this.opts = Object.assign({
                columns: [],
                endpoint: null,
                rowActions: null,
                searchable: true,
                onRowClick: null,
                perPage: 25,
                exportable: true,
                emptyMessage: 'Nenhum registro encontrado.',
            }, options);

            this.page = 1;
            this.perPage = this.opts.perPage;
            this.search = '';
            this.filters = {};
            this.sortKey = null;
            this.sortDir = 'asc';
            this.data = [];
            this.total = 0;
            this._debounceTimer = null;
            this._filterTimers = {};

            this._render();
            this.load();
        }

        /* ---- Render: estrutura geral ---- */
        _render() {
            this.container.innerHTML = '';
            this.container.className = (this.container.className + ' datagrid').trim();

            // Toolbar
            this._toolbar = document.createElement('div');
            this._toolbar.className = 'datagrid-toolbar';

            if (this.opts.searchable) {
                this._searchInput = document.createElement('input');
                this._searchInput.type = 'search';
                this._searchInput.placeholder = 'Buscar...';
                this._searchInput.className = 'datagrid-search';
                this._searchInput.addEventListener('input', () => this._onSearchInput());
                this._toolbar.appendChild(this._searchInput);
            }

            if (this.opts.exportable) {
                const expBtn = document.createElement('button');
                expBtn.className = 'btn btn-ghost btn-sm';
                expBtn.innerHTML = _svgDownload() + ' Exportar CSV';
                expBtn.addEventListener('click', () => this.exportCsv());
                this._toolbar.appendChild(expBtn);
            }

            this.container.appendChild(this._toolbar);

            // Table wrapper (scroll horizontal em mobile)
            const tableWrap = document.createElement('div');
            tableWrap.style.overflowX = 'auto';

            this._table = document.createElement('table');
            this._thead = document.createElement('thead');
            this._tbody = document.createElement('tbody');
            this._table.appendChild(this._thead);
            this._table.appendChild(this._tbody);
            tableWrap.appendChild(this._table);
            this.container.appendChild(tableWrap);

            // Footer
            this._footer = document.createElement('div');
            this._footer.className = 'datagrid-footer';
            this._countEl = document.createElement('span');
            this._footer.appendChild(this._countEl);
            this._paginationEl = document.createElement('div');
            this._paginationEl.className = 'datagrid-pagination';
            this._footer.appendChild(this._paginationEl);
            this.container.appendChild(this._footer);

            this._renderHeader();
        }

        _renderHeader() {
            this._thead.innerHTML = '';

            // Header row
            const tr = document.createElement('tr');
            this.opts.columns.forEach(col => {
                const th = document.createElement('th');
                th.textContent = col.label;
                if (col.width) th.style.width = col.width;
                if (col.align) th.style.textAlign = col.align;

                if (col.sortable) {
                    th.className = 'sortable';
                    const sortIcon = document.createElement('span');
                    sortIcon.className = 'sort-icon';
                    th.appendChild(sortIcon);

                    if (this.sortKey === col.key) {
                        th.classList.add('sort-' + this.sortDir);
                    }

                    th.addEventListener('click', () => this._onSort(col.key, th));
                }

                tr.appendChild(th);
            });

            // Actions column header
            if (this.opts.rowActions) {
                const th = document.createElement('th');
                th.textContent = '';
                th.style.width = '1%';
                tr.appendChild(th);
            }

            this._thead.appendChild(tr);

            // Filter row
            const hasFilters = this.opts.columns.some(c => c.filter);
            if (hasFilters) {
                const filterTr = document.createElement('tr');
                filterTr.className = 'filter-row';

                this.opts.columns.forEach(col => {
                    const th = document.createElement('th');
                    if (col.filter) {
                        let input;
                        if (col.filterType === 'select') {
                            input = document.createElement('select');
                            const blank = document.createElement('option');
                            blank.value = '';
                            blank.textContent = 'Todos';
                            input.appendChild(blank);
                            (col.filterOptions || []).forEach(opt => {
                                const o = document.createElement('option');
                                o.value = opt.value;
                                o.textContent = opt.label;
                                input.appendChild(o);
                            });
                            input.addEventListener('change', () => {
                                this.filters[col.key] = input.value;
                                this.page = 1;
                                this.load();
                            });
                        } else {
                            input = document.createElement('input');
                            input.type = 'text';
                            input.placeholder = col.label + '...';
                            input.addEventListener('input', () => {
                                clearTimeout(this._filterTimers[col.key]);
                                this._filterTimers[col.key] = setTimeout(() => {
                                    this.filters[col.key] = input.value;
                                    this.page = 1;
                                    this.load();
                                }, DEBOUNCE_MS);
                            });
                        }
                        th.appendChild(input);
                    }
                    filterTr.appendChild(th);
                });

                if (this.opts.rowActions) filterTr.appendChild(document.createElement('th'));

                this._thead.appendChild(filterTr);
            }
        }

        _renderBody() {
            this._tbody.innerHTML = '';

            if (this._loading) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = this.opts.columns.length + (this.opts.rowActions ? 1 : 0);
                td.className = 'datagrid-loading';
                td.innerHTML = '<span class="spinner spinner-dark"></span> Carregando...';
                tr.appendChild(td);
                this._tbody.appendChild(tr);
                return;
            }

            if (!this.data.length) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = this.opts.columns.length + (this.opts.rowActions ? 1 : 0);
                td.className = 'datagrid-empty';
                td.textContent = this.opts.emptyMessage;
                tr.appendChild(td);
                this._tbody.appendChild(tr);
                return;
            }

            this.data.forEach((row, rowIdx) => {
                const tr = document.createElement('tr');
                if (typeof this.opts.onRowClick === 'function') {
                    tr.style.cursor = 'pointer';
                    tr.addEventListener('click', (e) => {
                        // Não dispara se clicou num botão de ação
                        if (e.target.closest('.actions')) return;
                        this.opts.onRowClick(row);
                    });
                }

                this.opts.columns.forEach(col => {
                    const td = document.createElement('td');
                    td.setAttribute('data-label', col.label);
                    if (col.align) td.style.textAlign = col.align;

                    const rawVal = _getNestedValue(row, col.key);
                    let displayVal;

                    if (typeof col.format === 'function') {
                        displayVal = col.format(rawVal, row);
                        if (col.html) {
                            td.innerHTML = displayVal;
                        } else {
                            td.textContent = displayVal;
                        }
                    } else {
                        td.textContent = rawVal != null ? String(rawVal) : '—';
                    }

                    tr.appendChild(td);
                });

                // Actions
                if (typeof this.opts.rowActions === 'function') {
                    const td = document.createElement('td');
                    td.className = 'actions-cell';
                    td.setAttribute('data-label', '');
                    const actionsDiv = document.createElement('div');
                    actionsDiv.className = 'actions';

                    const actions = this.opts.rowActions(row);
                    (actions || []).forEach(action => {
                        const btn = document.createElement('button');
                        btn.className = 'btn btn-sm ' + (action.className || 'btn-ghost');
                        btn.innerHTML = (action.icon || '') + (action.label ? ' ' + _escText(action.label) : '');
                        btn.title = action.title || action.label || '';
                        btn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            action.onClick(row);
                        });
                        actionsDiv.appendChild(btn);
                    });

                    td.appendChild(actionsDiv);
                    tr.appendChild(td);
                }

                this._tbody.appendChild(tr);
            });
        }

        _renderPagination() {
            const totalPages = Math.max(1, Math.ceil(this.total / this.perPage));
            const cur = this.page;

            this._countEl.textContent = this.total + ' registro' + (this.total !== 1 ? 's' : '');
            this._paginationEl.innerHTML = '';

            // Anterior
            const prevBtn = _mkPageBtn('‹', cur === 1, () => { this.page = cur - 1; this.load(); });
            this._paginationEl.appendChild(prevBtn);

            // Páginas (janela)
            const pages = _pageWindow(cur, totalPages);
            let last = 0;
            pages.forEach(p => {
                if (p - last > 1) {
                    const dots = document.createElement('span');
                    dots.textContent = '…';
                    dots.style.padding = '0 4px';
                    dots.style.color = '#9aa4b0';
                    this._paginationEl.appendChild(dots);
                }
                const btn = _mkPageBtn(String(p), false, () => { this.page = p; this.load(); });
                if (p === cur) btn.classList.add('active');
                this._paginationEl.appendChild(btn);
                last = p;
            });

            // Próxima
            const nextBtn = _mkPageBtn('›', cur >= totalPages, () => { this.page = cur + 1; this.load(); });
            this._paginationEl.appendChild(nextBtn);
        }

        /* ---- Load data ---- */
        async load() {
            if (!this.opts.endpoint) return;
            if (typeof window.api === 'undefined') {
                console.error('DataGrid: window.api não disponível. Inclua api.js antes.');
                return;
            }

            this._loading = true;
            this._renderBody();

            const params = {
                page: this.page,
                per_page: this.perPage,
            };

            if (this.search) params.search = this.search;
            if (this.sortKey) {
                params.sort = this.sortKey;
                params.order = this.sortDir;
            }

            // Filtros por coluna
            Object.keys(this.filters).forEach(k => {
                if (this.filters[k] !== '' && this.filters[k] != null) {
                    params[k] = this.filters[k];
                }
            });

            try {
                const result = await window.api.get(this.opts.endpoint, params);
                // Suporta {items: [], total: N} ou array direto
                if (Array.isArray(result)) {
                    this.data = result;
                    this.total = result.length;
                } else {
                    this.data = result.items || result.data || [];
                    this.total = result.total != null ? result.total : this.data.length;
                }
            } catch (e) {
                this.data = [];
                this.total = 0;
                console.error('DataGrid load error:', e.message);
            } finally {
                this._loading = false;
                this._renderBody();
                this._renderPagination();
            }
        }

        /* ---- Handlers ---- */
        _onSearchInput() {
            clearTimeout(this._debounceTimer);
            this._debounceTimer = setTimeout(() => {
                this.search = this._searchInput.value.trim();
                this.page = 1;
                this.load();
            }, DEBOUNCE_MS);
        }

        _onSort(key, th) {
            if (this.sortKey === key) {
                this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortKey = key;
                this.sortDir = 'asc';
            }
            // Atualiza visual do cabeçalho
            this._thead.querySelectorAll('th').forEach(t => {
                t.classList.remove('sort-asc', 'sort-desc');
            });
            th.classList.add('sort-' + this.sortDir);
            this.page = 1;
            this.load();
        }

        /* ---- Export CSV (client-side dos dados carregados) ---- */
        exportCsv() {
            const cols = this.opts.columns;
            const header = cols.map(c => _csvEsc(c.label)).join(',');
            const rows = this.data.map(row =>
                cols.map(col => {
                    const v = _getNestedValue(row, col.key);
                    return _csvEsc(v != null ? String(v) : '');
                }).join(',')
            );
            const csv = '\uFEFF' + [header, ...rows].join('\r\n');
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'export_' + Date.now() + '.csv';
            document.body.appendChild(a);
            a.click();
            setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 500);
        }

        /* ---- API pública ---- */
        refresh() { return this.load(); }

        setEndpoint(ep) {
            this.opts.endpoint = ep;
            this.page = 1;
            return this.load();
        }

        setFilter(key, value) {
            this.filters[key] = value;
            this.page = 1;
            return this.load();
        }
    }

    /* ---- Helpers ---- */
    function _getNestedValue(obj, key) {
        return key.split('.').reduce((o, k) => (o != null ? o[k] : undefined), obj);
    }

    function _csvEsc(v) {
        const s = String(v);
        if (/[",\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
        return s;
    }

    function _escText(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function _mkPageBtn(label, disabled, onClick) {
        const btn = document.createElement('button');
        btn.innerHTML = label;
        btn.disabled = disabled;
        btn.addEventListener('click', onClick);
        return btn;
    }

    function _pageWindow(cur, total) {
        if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
        const pages = new Set([1, total, cur]);
        for (let i = cur - 2; i <= cur + 2; i++) { if (i >= 1 && i <= total) pages.add(i); }
        return Array.from(pages).sort((a, b) => a - b);
    }

    function _svgDownload() {
        return '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    }

    window.DataGrid = DataGrid;
})();
