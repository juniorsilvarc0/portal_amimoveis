/* ============================================================
   api.js — AM Imoveis Portal
   Wrapper fetch + JWT interceptor. Expõe window.api
   ============================================================ */

(function () {
    'use strict';

    const API_BASE = '/api/v1';

    function getToken() {
        return localStorage.getItem('token');
    }

    function setToken(t) {
        localStorage.setItem('token', t);
    }

    function clearToken() {
        localStorage.removeItem('token');
        localStorage.removeItem('usuario');
    }

    async function apiCall(path, options) {
        options = options || {};

        const token = getToken();
        const headers = new Headers(options.headers || {});

        if (token) {
            headers.set('Authorization', 'Bearer ' + token);
        }

        // Auto-set Content-Type for JSON bodies (skip FormData)
        if (options.body && !(options.body instanceof FormData)) {
            headers.set('Content-Type', 'application/json');
            if (typeof options.body !== 'string') {
                options.body = JSON.stringify(options.body);
            }
        }

        let resp;
        try {
            resp = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
        } catch (networkErr) {
            const e = new Error('Falha de rede: ' + networkErr.message);
            e.status = 0;
            throw e;
        }

        // 401 → logout e redireciona (exceto na própria rota de login)
        if (resp.status === 401 && path !== '/auth/login') {
            clearToken();
            window.location.href = '/login?erro=' + encodeURIComponent('Sessão expirada. Faça login novamente.');
            throw new Error('Unauthorized');
        }

        const contentType = resp.headers.get('content-type') || '';
        let body;
        try {
            body = contentType.includes('application/json') ? await resp.json() : await resp.text();
        } catch (_) {
            body = null;
        }

        if (!resp.ok) {
            const msg = (body && (body.detail || body.erro || body.message)) || ('Erro ' + resp.status);
            const e = new Error(msg);
            e.status = resp.status;
            e.body = body;
            throw e;
        }

        return body;
    }

    const api = {
        /* --- HTTP helpers --- */
        get(path, params) {
            const qs = params ? '?' + new URLSearchParams(params).toString() : '';
            return apiCall(path + qs);
        },

        post(path, body) {
            return apiCall(path, { method: 'POST', body });
        },

        put(path, body) {
            return apiCall(path, { method: 'PUT', body });
        },

        patch(path, body) {
            return apiCall(path, { method: 'PATCH', body });
        },

        del(path) {
            return apiCall(path, { method: 'DELETE' });
        },

        upload(path, formData) {
            return apiCall(path, { method: 'POST', body: formData });
        },

        /* --- Auth --- */
        async login(email, senha) {
            const r = await apiCall('/auth/login', {
                method: 'POST',
                body: { email, senha }
            });
            if (r.access_token) setToken(r.access_token);
            if (r.usuario) localStorage.setItem('usuario', JSON.stringify(r.usuario));
            return r.usuario;
        },

        me() {
            return apiCall('/auth/me');
        },

        logout() {
            clearToken();
            window.location.href = '/login';
        },

        currentUser() {
            try {
                return JSON.parse(localStorage.getItem('usuario'));
            } catch (_) {
                return null;
            }
        },

        isLoggedIn() {
            return !!getToken();
        },

        /* --- Permissões (RBAC) --- */
        can(recurso, acao) {
            try {
                const u = this.currentUser();
                if (!u) return false;
                if (u.is_admin) return true;
                const p = u.permissoes && u.permissoes[recurso];
                return !!(p && p[acao]);
            } catch (_) {
                return false;
            }
        },

        /* --- Utilitário: checa sessão e redireciona se não logado --- */
        async requireAuth() {
            if (!getToken()) {
                window.location.href = '/login?erro=' + encodeURIComponent('Acesso restrito. Faça login.');
                throw new Error('Not authenticated');
            }
            try {
                const usuario = await api.me();
                localStorage.setItem('usuario', JSON.stringify(usuario));
                return usuario;
            } catch (e) {
                if (e.status === 401) return; // já redirecionado em apiCall
                throw e;
            }
        },

        /* --- Download/preview de PDF autenticado --- */
        async downloadPdf(path, filename) {
            const _err = (msg) => {
                if (window.Modal && typeof window.Modal.alert === 'function') {
                    window.Modal.alert(msg);
                } else if (typeof window.showToast === 'function') {
                    window.showToast(msg, 'error');
                } else {
                    alert(msg);
                }
            };
            const token = getToken();
            let resp;
            try {
                resp = await fetch(API_BASE + path, {
                    headers: { Authorization: 'Bearer ' + token }
                });
            } catch (networkErr) {
                _err('Falha de rede ao gerar PDF: ' + networkErr.message);
                return;
            }

            if (resp.status === 401) {
                clearToken();
                window.location.href = '/login?erro=' + encodeURIComponent('Sessão expirada. Faça login novamente.');
                return;
            }

            if (!resp.ok) {
                _err('Erro ao gerar PDF: ' + resp.status + ' ' + resp.statusText);
                return;
            }

            const contentType = resp.headers.get('content-type') || '';
            if (!contentType.includes('application/pdf')) {
                _err('Resposta inesperada do servidor (não é PDF).');
                return;
            }

            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const win = window.open(url, '_blank');
            if (!win) {
                // fallback: forçar download se popup bloqueado
                const a = document.createElement('a');
                a.href = url;
                a.download = filename || 'documento.pdf';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }
            setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
        },

        /* --- Download genérico de arquivo autenticado (xlsx, csv, etc.) --- */
        async downloadFile(path, filename) {
            const _err = (msg) => {
                if (window.Modal && typeof window.Modal.alert === 'function') {
                    window.Modal.alert(msg);
                } else if (typeof window.showToast === 'function') {
                    window.showToast(msg, 'error');
                } else {
                    alert(msg);
                }
            };
            const token = getToken();
            let resp;
            try {
                resp = await fetch(API_BASE + path, {
                    headers: { Authorization: 'Bearer ' + token }
                });
            } catch (networkErr) {
                _err('Falha de rede ao baixar arquivo: ' + networkErr.message);
                return;
            }

            if (resp.status === 401) {
                clearToken();
                window.location.href = '/login?erro=' + encodeURIComponent('Sessão expirada. Faça login novamente.');
                return;
            }

            if (!resp.ok) {
                _err('Erro ao gerar arquivo: ' + resp.status + ' ' + resp.statusText);
                return;
            }

            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename || 'arquivo';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
        },
    };

    window.api = api;
    window.apiCall = apiCall; // exposto para uso interno dos demais scripts
})();
