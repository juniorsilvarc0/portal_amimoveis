/* ============================================================
   cpf_lookup.js — AM Imoveis Portal
   Auto-lookup de cliente por CPF ao digitar.

   Endpoint: GET /api/v1/clientes?cpf={cpf_sem_mascara}
     - 200 + objeto  → cliente encontrado
     - 404           → não cadastrado

   Uso:
     attachCpfLookup(
       document.getElementById('cpf'),
       function onFound(cliente) { ... preenche campos ... },
       function onNotFound() { ... libera campos ... }
     );
   ============================================================ */

(function () {
    'use strict';

    var DEBOUNCE_MS = 400;

    /**
     * Cria estado visual de "buscando" no input.
     */
    function setLookupState(input, state) {
        var badge = input.parentElement.querySelector('.cpf-found-badge');

        if (state === 'loading') {
            input.style.borderColor = '#d97706';
            if (badge) badge.remove();
        } else if (state === 'found') {
            input.style.borderColor = '#16a34a';
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'cpf-found-badge';
                badge.textContent = 'Cliente encontrado';
                input.parentElement.appendChild(badge);
            }
        } else if (state === 'notfound') {
            input.style.borderColor = '';
            if (badge) badge.remove();
        } else {
            // idle / reset
            input.style.borderColor = '';
            if (badge) badge.remove();
        }
    }

    /**
     * Vincula busca automática de cliente por CPF a um input.
     *
     * @param {HTMLInputElement} cpfInput - Input do CPF (com ou sem máscara).
     * @param {function} onFound - Callback chamado com o objeto cliente quando encontrado.
     *   Ex: function(cliente) { form.nome.value = cliente.nome; }
     * @param {function} onNotFound - Callback chamado quando CPF não está cadastrado.
     *   Ex: function() { form.nome.removeAttribute('readonly'); }
     */
    function attachCpfLookup(cpfInput, onFound, onNotFound) {
        if (!cpfInput) return;

        var timer = null;
        var lastCpf = '';

        cpfInput.addEventListener('input', function () {
            var raw = (typeof window.unmask === 'function')
                ? window.unmask(cpfInput.value)
                : cpfInput.value.replace(/\D/g, '');

            // Só dispara quando tiver 11 dígitos (CPF completo)
            if (raw.length !== 11) {
                clearTimeout(timer);
                lastCpf = '';
                setLookupState(cpfInput, 'idle');
                if (typeof onNotFound === 'function') onNotFound();
                return;
            }

            // Evita buscas duplicadas
            if (raw === lastCpf) return;

            clearTimeout(timer);

            timer = setTimeout(function () {
                lastCpf = raw;
                setLookupState(cpfInput, 'loading');
                doLookup(raw, cpfInput, onFound, onNotFound);
            }, DEBOUNCE_MS);
        });
    }

    async function doLookup(cpf, cpfInput, onFound, onNotFound) {
        if (typeof window.api === 'undefined') {
            console.error('cpf_lookup.js: window.api não disponível. Inclua api.js antes.');
            return;
        }

        try {
            const cliente = await window.api.get('/clientes', { cpf: cpf });
            // 200 — cliente encontrado
            setLookupState(cpfInput, 'found');
            if (typeof onFound === 'function') onFound(cliente);
        } catch (e) {
            if (e.status === 404) {
                // CPF não cadastrado — libera campos
                setLookupState(cpfInput, 'notfound');
                if (typeof onNotFound === 'function') onNotFound();
            } else if (e.status !== 0) {
                // Erro inesperado (não é falha de rede silenciosa)
                console.warn('cpf_lookup: erro ao buscar CPF', cpf, e.message);
                setLookupState(cpfInput, 'idle');
            }
        }
    }

    window.attachCpfLookup = attachCpfLookup;
})();
