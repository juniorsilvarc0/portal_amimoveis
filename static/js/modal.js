/* ============================================================
   modal.js — AM Imoveis Portal
   Classe Modal vanilla com overlay, animação fade/slide,
   suporte a Esc, fullscreen mobile.
   Expõe: window.Modal
   ============================================================ */

(function () {
    'use strict';

    // Contador de modais abertos (para gerenciar scroll do body)
    var openCount = 0;

    class Modal {
        /**
         * @param {object} opts
         * @param {string}   opts.title
         * @param {string}   [opts.bodyHtml]
         * @param {string}   [opts.footerHtml]
         * @param {function} [opts.onClose]
         * @param {boolean}  [opts.fullscreenMobile=true]
         * @param {string}   [opts.width='900px']
         * @param {boolean}  [opts.closeOnBackdrop=true]
         */
        constructor(opts) {
            this.opts = Object.assign({
                title: '',
                bodyHtml: '',
                footerHtml: '',
                onClose: null,
                fullscreenMobile: true,
                width: '900px',
                closeOnBackdrop: true,
            }, opts);

            this._build();
        }

        _build() {
            // Overlay
            this._overlay = document.createElement('div');
            this._overlay.className = 'modal-overlay';
            this._overlay.setAttribute('role', 'dialog');
            this._overlay.setAttribute('aria-modal', 'true');

            // Modal box
            this._box = document.createElement('div');
            this._box.className = 'modal';
            this._box.style.maxWidth = this.opts.width;

            // Header
            this._header = document.createElement('div');
            this._header.className = 'modal-header';

            this._titleEl = document.createElement('h2');
            this._titleEl.className = 'modal-title';
            this._titleEl.textContent = this.opts.title;

            const closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close';
            closeBtn.setAttribute('aria-label', 'Fechar');
            closeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
            closeBtn.addEventListener('click', () => this.close());

            this._header.appendChild(this._titleEl);
            this._header.appendChild(closeBtn);

            // Body
            this._bodyEl = document.createElement('div');
            this._bodyEl.className = 'modal-body';
            this._bodyEl.innerHTML = this.opts.bodyHtml;

            // Footer
            this._footerEl = document.createElement('div');
            this._footerEl.className = 'modal-footer';
            if (this.opts.footerHtml) {
                this._footerEl.innerHTML = this.opts.footerHtml;
            } else {
                this._footerEl.style.display = 'none';
            }

            this._box.appendChild(this._header);
            this._box.appendChild(this._bodyEl);
            this._box.appendChild(this._footerEl);
            this._overlay.appendChild(this._box);

            // Fechar ao clicar no backdrop
            if (this.opts.closeOnBackdrop) {
                this._overlay.addEventListener('click', (e) => {
                    if (e.target === this._overlay) this.close();
                });
            }

            // Fechar com Esc
            this._escHandler = (e) => {
                if (e.key === 'Escape') this.close();
            };
        }

        open() {
            document.body.appendChild(this._overlay);
            document.addEventListener('keydown', this._escHandler);

            openCount++;
            if (openCount === 1) document.body.style.overflow = 'hidden';

            // Força reflow para animação
            this._overlay.getBoundingClientRect();
            this._overlay.classList.add('visible');

            return this;
        }

        close() {
            this._overlay.classList.remove('visible');
            document.removeEventListener('keydown', this._escHandler);

            openCount = Math.max(0, openCount - 1);
            if (openCount === 0) document.body.style.overflow = '';

            // Remove após animação
            const onEnd = () => {
                if (this._overlay.parentNode) this._overlay.parentNode.removeChild(this._overlay);
                if (typeof this.opts.onClose === 'function') this.opts.onClose();
            };
            this._overlay.addEventListener('transitionend', onEnd, { once: true });
            // Fallback se transição não disparar
            setTimeout(onEnd, 300);

            return this;
        }

        setTitle(title) {
            this._titleEl.textContent = title;
            return this;
        }

        setBody(html) {
            this._bodyEl.innerHTML = html;
            return this;
        }

        setFooter(html) {
            this._footerEl.innerHTML = html;
            this._footerEl.style.display = '';
            return this;
        }

        getBody() {
            return this._bodyEl;
        }

        getFooter() {
            return this._footerEl;
        }

        /**
         * Exibe um alerta simples (sem Promise, apenas OK).
         * @param {string} msg
         * @param {string} [title='Aviso']
         */
        static alert(msg, title) {
            title = title || 'Aviso';
            const m = new Modal({
                title,
                bodyHtml: '<p style="font-size:14px;line-height:1.6;">' + _escHtml(msg) + '</p>',
                footerHtml: '<button class="btn btn-primary" id="_modalAlertOk">OK</button>',
                width: '480px',
            });
            m.open();
            setTimeout(() => {
                const ok = document.getElementById('_modalAlertOk');
                if (ok) ok.addEventListener('click', () => m.close());
            }, 0);
            return m;
        }

        /**
         * Exibe uma confirmação. Retorna Promise<boolean>.
         * @param {string} msg
         * @param {string} [title='Confirmar']
         * @returns {Promise<boolean>}
         */
        static confirm(msg, title) {
            title = title || 'Confirmar';
            return new Promise((resolve) => {
                const m = new Modal({
                    title,
                    bodyHtml: '<p style="font-size:14px;line-height:1.6;">' + msg + '</p>',
                    footerHtml:
                        '<button class="btn btn-ghost" id="_modalCancelBtn">Cancelar</button>' +
                        '<button class="btn btn-primary" id="_modalConfirmBtn">Confirmar</button>',
                    width: '480px',
                    onClose: () => resolve(false),
                    closeOnBackdrop: false,
                });
                m.open();
                setTimeout(() => {
                    const ok = document.getElementById('_modalConfirmBtn');
                    const cancel = document.getElementById('_modalCancelBtn');
                    if (ok) ok.addEventListener('click', () => { m.opts.onClose = null; m.close(); resolve(true); });
                    if (cancel) cancel.addEventListener('click', () => { m.opts.onClose = null; m.close(); resolve(false); });
                }, 0);
            });
        }

        /**
         * Exibe um formulário com corpo HTML customizado e botões Cancelar/Salvar.
         * `onConfirm` é chamado ao confirmar; pode ser async. O modal permanece
         * aberto enquanto `onConfirm` executa e fecha ao terminar. Se `onConfirm`
         * retornar exatamente `false`, o modal NÃO fecha (validação falhou). Se
         * lançar exceção, o modal permanece aberto para nova tentativa.
         * @param {string}   title
         * @param {string}   bodyHtml
         * @param {function} onConfirm
         * @param {object}   [opts] { confirmLabel='Salvar', cancelLabel='Cancelar', width='480px', closeOnBackdrop=false }
         * @returns {Modal}
         */
        static prompt(title, bodyHtml, onConfirm, opts) {
            opts = opts || {};
            const confirmLabel = opts.confirmLabel || 'Salvar';
            const cancelLabel = opts.cancelLabel || 'Cancelar';
            const m = new Modal({
                title: title || '',
                bodyHtml: bodyHtml || '',
                footerHtml:
                    '<button class="btn btn-ghost" id="_modalPromptCancel">' + _escHtml(cancelLabel) + '</button>' +
                    '<button class="btn btn-primary" id="_modalPromptOk">' + _escHtml(confirmLabel) + '</button>',
                width: opts.width || '480px',
                closeOnBackdrop: opts.closeOnBackdrop !== undefined ? opts.closeOnBackdrop : false,
            });
            m.open();
            setTimeout(() => {
                const ok = m.getFooter().querySelector('#_modalPromptOk');
                const cancel = m.getFooter().querySelector('#_modalPromptCancel');
                const first = m.getBody().querySelector('input, select, textarea');
                if (first) { try { first.focus(); } catch (e) {} }
                if (cancel) cancel.addEventListener('click', () => m.close());
                if (ok) {
                    let busy = false;
                    const prevText = ok.textContent;
                    ok.addEventListener('click', async () => {
                        if (busy) return;
                        busy = true;
                        ok.disabled = true;
                        ok.textContent = 'Salvando…';
                        const reset = () => { busy = false; ok.disabled = false; ok.textContent = prevText; };
                        try {
                            const result = (typeof onConfirm === 'function') ? await onConfirm() : undefined;
                            if (result === false) { reset(); return; }
                            m.close();
                        } catch (e) {
                            reset();
                        }
                    });
                }
            }, 0);
            return m;
        }
    }

    function _escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    window.Modal = Modal;
})();
