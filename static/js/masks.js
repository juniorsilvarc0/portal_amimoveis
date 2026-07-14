/* ============================================================
   masks.js — AM Imoveis Portal
   Máscaras de CPF, telefone, moeda e utilitários.
   Expõe: maskCPF, maskPhone, maskMoney, unmask, attachMask
   ============================================================ */

(function () {
    'use strict';

    /**
     * Remove tudo que não for dígito.
     * @param {string} v
     * @returns {string}
     */
    function unmask(v) {
        return String(v || '').replace(/\D/g, '');
    }

    /**
     * Formata CPF: 000.000.000-00
     * @param {string} v — valor bruto (pode conter máscara)
     * @returns {string}
     */
    function maskCPF(v) {
        const d = unmask(v).slice(0, 11);
        if (d.length <= 3) return d;
        if (d.length <= 6) return d.slice(0, 3) + '.' + d.slice(3);
        if (d.length <= 9) return d.slice(0, 3) + '.' + d.slice(3, 6) + '.' + d.slice(6);
        return d.slice(0, 3) + '.' + d.slice(3, 6) + '.' + d.slice(6, 9) + '-' + d.slice(9, 11);
    }

    /**
     * Formata CNPJ: 00.000.000/0000-00
     * @param {string} v
     * @returns {string}
     */
    function maskCNPJ(v) {
        const d = unmask(v).slice(0, 14);
        if (d.length <= 2) return d;
        if (d.length <= 5) return d.slice(0, 2) + '.' + d.slice(2);
        if (d.length <= 8) return d.slice(0, 2) + '.' + d.slice(2, 5) + '.' + d.slice(5);
        if (d.length <= 12) return d.slice(0, 2) + '.' + d.slice(2, 5) + '.' + d.slice(5, 8) + '/' + d.slice(8);
        return d.slice(0, 2) + '.' + d.slice(2, 5) + '.' + d.slice(5, 8) + '/' + d.slice(8, 12) + '-' + d.slice(12);
    }

    /**
     * Formata CPF ou CNPJ conforme a quantidade de dígitos.
     * @param {string} v
     * @returns {string}
     */
    function maskCpfCnpj(v) {
        const d = unmask(v);
        return d.length > 11 ? maskCNPJ(v) : maskCPF(v);
    }

    /**
     * Formata telefone: (00) 00000-0000  ou  (00) 0000-0000
     * @param {string} v
     * @returns {string}
     */
    function maskPhone(v) {
        const d = unmask(v).slice(0, 11);
        if (d.length <= 2) return d.length ? '(' + d : '';
        if (d.length <= 6) return '(' + d.slice(0, 2) + ') ' + d.slice(2);
        if (d.length <= 10) return '(' + d.slice(0, 2) + ') ' + d.slice(2, 6) + '-' + d.slice(6);
        // 11 dígitos — celular
        return '(' + d.slice(0, 2) + ') ' + d.slice(2, 7) + '-' + d.slice(7);
    }

    /**
     * Formata CEP: 00000-000
     * @param {string} v
     * @returns {string}
     */
    function maskCEP(v) {
        const d = unmask(v).slice(0, 8);
        if (d.length <= 5) return d;
        return d.slice(0, 5) + '-' + d.slice(5);
    }

    /**
     * Formata valor monetário: R$ 1.234,56
     * Aceita string numérica, number ou string já formatada.
     * @param {string|number} v
     * @returns {string}
     */
    function maskMoney(v) {
        // Se vier como número, converte primeiro
        if (typeof v === 'number') {
            return 'R$ ' + v.toFixed(2).replace('.', ',').replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
        }
        // Remove tudo exceto dígitos
        let d = unmask(String(v || ''));
        if (!d) return '';
        // Trata como centavos
        d = d.slice(0, 15); // limite razoável
        let cents = parseInt(d, 10);
        let reais = Math.floor(cents / 100);
        let centavos = cents % 100;

        let reaisStr = String(reais).replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
        return 'R$ ' + reaisStr + ',' + String(centavos).padStart(2, '0');
    }

    /**
     * Converte valor monetário mascarado para float.
     * Ex: "R$ 1.234,56" → 1234.56
     * @param {string} v
     * @returns {number}
     */
    function unmaskedMoney(v) {
        const clean = String(v || '').replace(/[^\d,]/g, '').replace(',', '.');
        return parseFloat(clean) || 0;
    }

    /**
     * Aplica uma função de máscara a um input via eventos.
     * Preserva a posição do cursor corretamente.
     * @param {HTMLInputElement} input
     * @param {function} fn — ex: maskCPF
     */
    function attachMask(input, fn) {
        function apply(e) {
            const start = input.selectionStart;
            const oldLen = input.value.length;
            input.value = fn(input.value);
            const newLen = input.value.length;
            // Tenta manter cursor na posição relativa
            const diff = newLen - oldLen;
            const newPos = Math.max(0, start + diff);
            try { input.setSelectionRange(newPos, newPos); } catch (_) {}
        }

        input.addEventListener('input', apply);
        input.addEventListener('blur', function () {
            input.value = fn(input.value);
        });

        // Aplica ao valor inicial se houver
        if (input.value) input.value = fn(input.value);
    }

    /**
     * Atalho: aplica máscaras a todos os inputs com data-mask="cpf|phone|money"
     * Útil para inicialização automática de páginas.
     * @param {HTMLElement} [root=document]
     */
    function autoMask(root) {
        root = root || document;
        root.querySelectorAll('[data-mask="cpf"]').forEach(function (el) { attachMask(el, maskCPF); });
        root.querySelectorAll('[data-mask="phone"]').forEach(function (el) { attachMask(el, maskPhone); });
        root.querySelectorAll('[data-mask="money"]').forEach(function (el) { attachMask(el, maskMoney); });
        root.querySelectorAll('[data-mask="cep"]').forEach(function (el) { attachMask(el, maskCEP); });
    }

    // Exposição global
    window.maskCPF = maskCPF;
    window.maskCNPJ = maskCNPJ;
    window.maskCpfCnpj = maskCpfCnpj;
    window.maskPhone = maskPhone;
    window.maskMoney = maskMoney;
    window.maskCEP = maskCEP;
    window.unmaskedMoney = unmaskedMoney;
    window.unmask = unmask;
    window.attachMask = attachMask;
    window.autoMask = autoMask;
})();
