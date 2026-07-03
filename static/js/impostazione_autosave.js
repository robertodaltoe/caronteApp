/**
 * Autosave per le pagine di Impostazione Anno Scolastico.
 * Intercetta i campi con data-autosave="campo:id" e li salva
 * automaticamente via fetch all'endpoint /impostazione-anno/api/save.
 *
 * Attributi HTML:
 *   data-autosave="nome_campo:id_record"
 *   data-autosave-extra='{"chiave": "valore"}'  (opzionale)
 *
 * Comportamento:
 *   - input[type=text], textarea: debounce 800ms dopo l'ultimo tasto
 *   - input[type=number]:         debounce 600ms
 *   - select, input[type=checkbox]: salvataggio immediato al change
 */

(function () {
    'use strict';

    const API_URL = '/impostazione-anno/api/save';
    const timers  = {};

    // Indicatore visivo: mostra ✓ o ✗ vicino al campo
    function mostraStato(el, ok, msg) {
        let badge = el._saveBadge;
        if (!badge) {
            badge = document.createElement('span');
            badge.style.cssText =
                'margin-left:5px; font-size:.7rem; font-weight:700; transition:opacity .4s;';
            el.parentNode.insertBefore(badge, el.nextSibling);
            el._saveBadge = badge;
        }
        badge.textContent = ok ? '✓' : '✗';
        badge.style.color  = ok ? '#16a34a' : '#dc2626';
        badge.style.opacity = '1';
        clearTimeout(badge._fadeTimer);
        badge._fadeTimer = setTimeout(() => { badge.style.opacity = '0'; }, ok ? 1800 : 4000);
        if (!ok && msg) badge.title = msg;
    }

    // Spinner durante il salvataggio
    function mostraSpinner(el, on) {
        let spin = el._saveSpinner;
        if (!spin) {
            spin = document.createElement('span');
            spin.textContent = '…';
            spin.style.cssText = 'margin-left:4px; font-size:.7rem; color:#6b7280;';
            el.parentNode.insertBefore(spin, el.nextSibling);
            el._saveSpinner = spin;
        }
        spin.style.display = on ? 'inline' : 'none';
    }

    async function salva(el) {
        const raw   = el.dataset.autosave || '';       // "campo:id"
        const parts = raw.split(':');
        if (parts.length < 2) return;

        const campo = parts[0];
        const id    = parts[1];
        const extra = el.dataset.autosaveExtra
            ? JSON.parse(el.dataset.autosaveExtra)
            : {};

        let valore;
        if (el.type === 'checkbox') {
            valore = el.checked;
        } else {
            valore = el.value;
        }

        mostraSpinner(el, true);

        try {
            const resp = await fetch(API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ campo, id, valore, extra }),
            });
            const json = await resp.json();
            mostraStato(el, json.ok, json.msg);

            // Aggiornamenti reattivi speciali
            if (json.ok && campo === 'cc_piano') {
                // Aggiorna lo stile del select se è diventato atipico o no
                const atipica = json.atipica;
                el.style.borderColor  = atipica ? '#f59e0b' : '#e5e7eb';
                el.style.background   = atipica ? '#fef3c7' : 'white';
                // Aggiorna/rimuovi icona ⚠️
                let icona = el._atipicoIcon;
                if (atipica && !icona) {
                    icona = document.createElement('span');
                    icona.textContent = '⚠️';
                    icona.title = 'Atipicità: CC diversa dal default normativo';
                    icona.style.fontSize = '.7rem';
                    el.parentNode.insertBefore(icona, el.nextSibling);
                    el._atipicoIcon = icona;
                } else if (!atipica && icona) {
                    icona.remove();
                    el._atipicoIcon = null;
                }
            }
        } catch (err) {
            mostraStato(el, false, 'Errore di rete');
        } finally {
            mostraSpinner(el, false);
        }
    }

    function aggiungiListeners(root) {
        root.querySelectorAll('[data-autosave]').forEach(el => {
            if (el._autosaveInit) return;
            el._autosaveInit = true;

            const tipo = el.type || el.tagName.toLowerCase();

            if (tipo === 'checkbox' || tipo === 'select' || el.tagName === 'SELECT') {
                el.addEventListener('change', () => salva(el));

            } else if (tipo === 'number') {
                el.addEventListener('input', () => {
                    clearTimeout(timers[el._autosaveId]);
                    timers[el._autosaveId] = setTimeout(() => salva(el), 600);
                });

            } else {
                // text, textarea
                el.addEventListener('input', () => {
                    clearTimeout(timers[el._autosaveId]);
                    timers[el._autosaveId] = setTimeout(() => salva(el), 800);
                });
            }

            // ID univoco per i timer
            el._autosaveId = Math.random().toString(36).slice(2);
        });
    }

    // Inizializza su DOM caricato e su MutationObserver per contenuti dinamici
    document.addEventListener('DOMContentLoaded', () => aggiungiListeners(document));

    const observer = new MutationObserver(mutations => {
        mutations.forEach(m => m.addedNodes.forEach(n => {
            if (n.nodeType === 1) aggiungiListeners(n);
        }));
    });
    observer.observe(document.body, { childList: true, subtree: true });

})();
