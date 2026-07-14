/* =============================================================
   forms.js — Helpers canônicos de formulário do portal AM Imoveis.

   Auto-inicialização:
   - Máscaras via `data-mask="cpf|phone|money|cep"` (delegado a masks.js)
   - Cards colapsáveis via `<div class="form-card-header" data-collapsible>`
   - Error banner global: showError(el, msg), clearError(el)
   - Coleta de payload: readForm(form) → {name: value, ...}
   - Populate: fillForm(form, data)
   - Validação básica via required + data-validate="cpf|email"

   Como usar (todos forms devem seguir):
     <script src="/static/js/masks.js"></script>
     <script src="/static/js/forms.js"></script>
     <script>
         forms.init(document.getElementById('myForm'));
         // ... popular, submit, etc
     </script>
============================================================= */

(function () {
    'use strict';

    /* =============================================================
       CATÁLOGO DE COMPONENTES DE CAMPO
       Fonte única de verdade. Um preset aqui é usado em todos os forms.
       Uso no HTML:
           <div data-field="cpf"></div>
           <div data-field="nascimento" data-name="prop_nasc" data-label="Data de nascimento"></div>
       Uso no JS:
           forms.field('cpf', { name: 'cpf', required: true })
           forms.renderPlaceholders(rootEl)  // escaneia data-field="..." e substitui
    ============================================================= */

    const OPT_ESTADO_CIVIL = [
        ['', 'Selecione'],
        ['solteiro', 'Solteiro(a)'],
        ['casado', 'Casado(a)'],
        ['uniao_estavel', 'União Estável'],
        ['divorciado', 'Divorciado(a)'],
        ['viuvo', 'Viúvo(a)'],
    ];

    const OPT_REGIME_BENS = [
        ['', 'Selecione'],
        ['comunhao_parcial', 'Comunhão Parcial'],
        ['comunhao_universal', 'Comunhão Universal'],
        ['separacao_total', 'Separação Total'],
        ['participacao_final', 'Participação Final nos Aquestos'],
    ];

    // Cada template define o comportamento canônico do componente.
    // Name/label podem ser sobrescritos via overrides. `fullWidth` coloca grid-column: 1/-1.
    const FIELD_CATALOG = {
        // --- Documentos / Identidade ---
        cpf:           { type: 'text',  mask: 'cpf',   placeholder: '000.000.000-00', maxlength: 14, inputmode: 'numeric', validate: 'cpf', label: 'CPF', required: true },
        rg:            { type: 'text',  label: 'RG' },
        rg_orgao:      { type: 'text',  label: 'Órgão expedidor / UF', placeholder: 'SSP/PI' },

        // --- Pessoal ---
        nome:          { type: 'text',  label: 'Nome completo', placeholder: 'Nome completo', fullWidth: true, required: true, autocomplete: 'name' },
        nascimento:    { type: 'date',  label: 'Data de nascimento' },
        nacionalidade: { type: 'text',  label: 'Nacionalidade', placeholder: 'Brasileiro(a)', value: 'Brasileiro(a)' },
        estado_civil:  { type: 'select', label: 'Estado civil', options: OPT_ESTADO_CIVIL },
        regime_bens:   { type: 'select', label: 'Regime de bens', options: OPT_REGIME_BENS },
        profissao:     { type: 'text',  label: 'Profissão', placeholder: 'Profissão' },

        // --- Contato ---
        email:         { type: 'email', label: 'E-mail', placeholder: 'email@exemplo.com', autocomplete: 'email' },
        whatsapp:      { type: 'text',  mask: 'phone', label: 'WhatsApp', placeholder: '(00) 00000-0000', inputmode: 'numeric' },
        telefone_fixo: { type: 'text',  mask: 'phone', label: 'Telefone fixo', placeholder: '(00) 0000-0000', inputmode: 'numeric' },

        // --- Endereço ---
        endereco:      { type: 'text',  label: 'Endereço residencial', placeholder: 'Rua, número, complemento', fullWidth: true },
        bairro:        { type: 'text',  label: 'Bairro' },
        cep:           { type: 'text',  mask: 'cep', label: 'CEP', placeholder: '00000-000', maxlength: 9, inputmode: 'numeric' },
        cidade_select: { type: 'select', label: 'Cidade', options: [['', 'Carregando...']], dataLookup: '/lookup/cidades' },

        // --- Financeiro ---
        money:         { type: 'text', mask: 'money', placeholder: 'R$ 0,00' },
        idade:         { type: 'text', label: 'Idade', placeholder: 'Ex: 35' },

        // --- Datas legado ---
        data:          { type: 'date' },
    };

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    /**
     * Renderiza um form-group HTML a partir de um preset + overrides.
     * @param {string} presetName — chave do FIELD_CATALOG
     * @param {Object} [overrides] — { name, label, required, fullWidth, value, placeholder, options }
     * @returns {string} HTML do form-group
     */
    function field(presetName, overrides) {
        const preset = FIELD_CATALOG[presetName] || {};
        const cfg = Object.assign({}, preset, overrides || {});
        const name = cfg.name || presetName;
        const id = cfg.id || name;
        const label = cfg.label || name;
        const required = cfg.required ? ' required' : '';
        const requiredMark = cfg.required ? ' <span class="required">*</span>' : '';
        const fullWidth = cfg.fullWidth ? ' full-width' : '';

        let control;
        if (cfg.type === 'select') {
            const opts = (cfg.options || []).map(function (o) {
                const v = Array.isArray(o) ? o[0] : o;
                const t = Array.isArray(o) ? o[1] : o;
                const sel = (cfg.value != null && String(cfg.value) === String(v)) ? ' selected' : '';
                return '<option value="' + _esc(v) + '"' + sel + '>' + _esc(t) + '</option>';
            }).join('');
            const dl = cfg.dataLookup ? ' data-lookup="' + _esc(cfg.dataLookup) + '"' : '';
            control = '<select id="' + _esc(id) + '" name="' + _esc(name) + '"' + required + dl + '>' + opts + '</select>';
        } else if (cfg.type === 'textarea') {
            const ph = cfg.placeholder ? ' placeholder="' + _esc(cfg.placeholder) + '"' : '';
            control = '<textarea id="' + _esc(id) + '" name="' + _esc(name) + '"' + required + ph + '>' + _esc(cfg.value || '') + '</textarea>';
        } else {
            const attrs = [
                'type="' + _esc(cfg.type || 'text') + '"',
                'id="' + _esc(id) + '"',
                'name="' + _esc(name) + '"',
            ];
            if (cfg.mask) attrs.push('data-mask="' + _esc(cfg.mask) + '"');
            if (cfg.validate) attrs.push('data-validate="' + _esc(cfg.validate) + '"');
            if (cfg.placeholder) attrs.push('placeholder="' + _esc(cfg.placeholder) + '"');
            if (cfg.maxlength) attrs.push('maxlength="' + _esc(cfg.maxlength) + '"');
            if (cfg.inputmode) attrs.push('inputmode="' + _esc(cfg.inputmode) + '"');
            if (cfg.autocomplete) attrs.push('autocomplete="' + _esc(cfg.autocomplete) + '"');
            if (cfg.value != null && cfg.value !== '') attrs.push('value="' + _esc(cfg.value) + '"');
            if (cfg.required) attrs.push('required');
            control = '<input ' + attrs.join(' ') + '>';
        }

        return (
            '<div class="form-group' + fullWidth + '">' +
                '<label for="' + _esc(id) + '">' + _esc(label) + requiredMark + '</label>' +
                control +
                '<small class="field-error"></small>' +
            '</div>'
        );
    }

    /**
     * Escaneia um root procurando <div data-field="preset"> e substitui
     * cada um pelo HTML canônico renderizado pelo catálogo.
     * Atributos extras do placeholder viram overrides:
     *     data-name="prop_nasc" data-label="Data nasc." data-required data-full-width
     * @param {HTMLElement} [root=document]
     */
    function renderPlaceholders(root) {
        root = root || document;
        const placeholders = Array.from(root.querySelectorAll('[data-field]'));
        placeholders.forEach(function (ph) {
            const preset = ph.getAttribute('data-field');
            const overrides = {
                name:       ph.getAttribute('data-name')       || undefined,
                label:      ph.getAttribute('data-label')      || undefined,
                placeholder:ph.getAttribute('data-placeholder')|| undefined,
                value:      ph.getAttribute('data-value')      || undefined,
            };
            if (ph.hasAttribute('data-required')) overrides.required = true;
            if (ph.hasAttribute('data-full-width')) overrides.fullWidth = true;
            Object.keys(overrides).forEach(k => overrides[k] === undefined && delete overrides[k]);
            const html = field(preset, overrides);
            const tmp = document.createElement('div');
            tmp.innerHTML = html;
            ph.replaceWith(tmp.firstElementChild);
        });
    }


    /**
     * Inicializa um form: aplica máscaras, wires collapsibles, foca primeiro field.
     * @param {HTMLElement} [root=document]
     */
    function init(root) {
        root = root || document;

        // 0. Expande placeholders <div data-field="..."> em form-groups canônicos
        renderPlaceholders(root);

        if (typeof window.autoMask === 'function') {
            window.autoMask(root);
        }

        // Cards colapsáveis
        root.querySelectorAll('.form-card-header[data-collapsible]').forEach(function (header) {
            if (header._formsInit) return;
            header._formsInit = true;
            header.addEventListener('click', function () {
                header.classList.toggle('collapsed');
                var body = header.nextElementSibling;
                if (body && body.classList.contains('form-card-body')) {
                    body.classList.toggle('hidden');
                }
            });
        });

        // Clear error on input + uppercase no blur
        root.querySelectorAll('.form-group input, .form-group select, .form-group textarea').forEach(function (el) {
            if (el._formsInit) return;
            el._formsInit = true;
            el.addEventListener('input', function () {
                var group = el.closest('.form-group');
                if (group) group.classList.remove('has-error');
            });
            // UPPERCASE: aplica em text/textarea/search; pula email/date/number/etc
            // ou se tiver atributo data-no-upper.
            if (_shouldUppercase(el)) {
                el.addEventListener('blur', function () {
                    if (el.value && typeof el.value === 'string') {
                        el.value = el.value.toLocaleUpperCase('pt-BR');
                    }
                });
            }
        });
    }

    function _shouldUppercase(el) {
        if (!el || el.hasAttribute('data-no-upper')) return false;
        if (el.tagName === 'SELECT') return false;
        if (el.tagName === 'TEXTAREA') return true;
        var t = (el.getAttribute('type') || 'text').toLowerCase();
        if (['email', 'password', 'url', 'date', 'time', 'datetime-local', 'number', 'color', 'file', 'range', 'checkbox', 'radio'].indexOf(t) >= 0) return false;
        return true;
    }

    /**
     * Marca um field com erro e mostra mensagem.
     * @param {HTMLElement|string} target — elemento ou id/name
     * @param {string} msg
     */
    function showError(target, msg) {
        var el = _resolve(target);
        if (!el) return;
        var group = el.closest('.form-group');
        if (!group) return;
        group.classList.add('has-error');
        var err = group.querySelector('.field-error');
        if (err) err.textContent = msg || 'Campo inválido';
    }

    function clearError(target) {
        var el = _resolve(target);
        if (!el) return;
        var group = el.closest('.form-group');
        if (group) group.classList.remove('has-error');
    }

    function clearAllErrors(root) {
        root = root || document;
        root.querySelectorAll('.form-group.has-error').forEach(function (g) {
            g.classList.remove('has-error');
        });
    }

    /**
     * Mostra banner global de erro.
     * @param {string} msg
     * @param {HTMLElement} [el] — container .alert-error; default: #alertError
     */
    function alertError(msg, el) {
        el = el || document.getElementById('alertError');
        if (!el) {
            console.warn('forms.alertError: #alertError não encontrado', msg);
            return;
        }
        el.textContent = msg;
        el.classList.add('show');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function alertClear(el) {
        el = el || document.getElementById('alertError');
        if (el) el.classList.remove('show');
    }

    /**
     * Lê os valores de um form num objeto plano.
     * Aplica unmask automaticamente em campos com data-mask.
     * @param {HTMLFormElement} form
     * @returns {Object}
     */
    function readForm(form) {
        var out = {};
        Array.from(form.elements).forEach(function (el) {
            if (!el.name) return;
            if (el.type === 'checkbox') {
                out[el.name] = el.checked;
            } else if (el.type === 'radio') {
                if (el.checked) out[el.name] = el.value;
            } else {
                var v = el.value;
                var mask = el.getAttribute('data-mask');
                if (mask === 'cpf' || mask === 'phone' || mask === 'cep') {
                    v = (v || '').replace(/\D/g, '');
                } else if (mask === 'money') {
                    // Mantém o valor formatado — backend aceita string
                    v = v;
                }
                out[el.name] = v === '' ? null : v;
            }
        });
        return out;
    }

    /**
     * Popula um form a partir de um objeto. Seguro contra campos inexistentes.
     * Aplica máscara se o campo tiver data-mask.
     * @param {HTMLFormElement} form
     * @param {Object} data
     */
    function fillForm(form, data) {
        if (!form || !data) return;
        Object.keys(data).forEach(function (k) {
            var el = form.elements[k];
            if (!el) return;
            var v = data[k];
            if (v == null) v = '';
            if (el.type === 'checkbox') {
                el.checked = !!v;
            } else {
                // UPPERCASE para text/textarea (mantém máscaras numéricas e e-mail intactos)
                if (typeof v === 'string' && _shouldUppercase(el)) {
                    v = v.toLocaleUpperCase('pt-BR');
                }
                el.value = v;
                // Reaplica máscara
                var mask = el.getAttribute('data-mask');
                if (mask && window[maskName(mask)]) {
                    el.value = window[maskName(mask)](el.value);
                }
            }
        });
    }

    function maskName(type) {
        return ({
            cpf: 'maskCPF',
            phone: 'maskPhone',
            money: 'maskMoney',
            cep: 'maskCEP',
        })[type] || null;
    }

    /**
     * Validação básica: required + data-validate="cpf|email".
     * Retorna true se tudo OK; false e marca erros se houver.
     * @param {HTMLFormElement} form
     * @returns {boolean}
     */
    function validate(form) {
        clearAllErrors(form);
        var ok = true;
        Array.from(form.elements).forEach(function (el) {
            if (!el.name || el.disabled) return;
            var v = (el.value || '').trim();
            if (el.required && !v) {
                showError(el, 'Campo obrigatório');
                ok = false;
                return;
            }
            var check = el.getAttribute('data-validate');
            if (!check || !v) return;
            if (check === 'cpf' && !isValidCPF(v)) {
                showError(el, 'CPF inválido');
                ok = false;
            } else if (check === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
                showError(el, 'E-mail inválido');
                ok = false;
            }
        });
        return ok;
    }

    /** Valida CPF via dígitos verificadores. */
    function isValidCPF(v) {
        var d = String(v).replace(/\D/g, '');
        if (d.length !== 11) return false;
        if (/^(\d)\1+$/.test(d)) return false;
        var sum = 0;
        for (var i = 0; i < 9; i++) sum += parseInt(d.charAt(i), 10) * (10 - i);
        var r = (sum * 10) % 11;
        if (r === 10) r = 0;
        if (r !== parseInt(d.charAt(9), 10)) return false;
        sum = 0;
        for (var j = 0; j < 10; j++) sum += parseInt(d.charAt(j), 10) * (11 - j);
        r = (sum * 10) % 11;
        if (r === 10) r = 0;
        return r === parseInt(d.charAt(10), 10);
    }

    function _resolve(target) {
        if (!target) return null;
        if (typeof target === 'string') {
            return document.getElementById(target) || document.querySelector('[name="' + target + '"]');
        }
        return target;
    }

    window.forms = {
        init: init,
        field: field,
        renderPlaceholders: renderPlaceholders,
        showError: showError,
        clearError: clearError,
        clearAllErrors: clearAllErrors,
        alertError: alertError,
        alertClear: alertClear,
        readForm: readForm,
        fillForm: fillForm,
        validate: validate,
        isValidCPF: isValidCPF,
        CATALOG: FIELD_CATALOG,
    };
})();
