/*
 * select_ricerca.js — trasforma un <select> con molte opzioni (es. i
 * 70+ docenti) in un campo con ricerca "scrivi e filtra", senza
 * toccare il markup del form: il <select> originale resta l'unico
 * campo che viene davvero inviato (name/id invariati), solo nascosto
 * alla vista — un input di testo e un menu a tendina personalizzati
 * lo pilotano, e ogni scelta genera un evento 'change' nativo così
 * tutta la logica onchange/addEventListener già esistente sui select
 * (es. aggiornaOrarioDocente() nel form assenze) continua a funzionare
 * senza modifiche.
 *
 * Uso: aggiungere l'attributo data-search="1" al <select> da
 * potenziare. Applicato anche a select creati dinamicamente dopo il
 * caricamento (es. righe della dashboard) richiamando
 * window.inizializzaSelectRicerca() dopo averle inserite nel DOM.
 */
(function () {
    function testoOpzione(opt) {
        // Il markup Jinja delle <option> va spesso su più righe: il
        // browser normalizza gli spazi solo nella tendina nativa, ma
        // opt.textContent restituisce il testo grezzo con newline e
        // indentazione — senza normalizzarlo comparirebbe anche nel
        // campo di ricerca personalizzato.
        return opt.textContent.replace(/\s+/g, ' ').trim();
    }

    function etichettaSelezionata(select) {
        var opt = select.selectedOptions[0];
        return (opt && opt.value) ? testoOpzione(opt) : '';
    }

    function opzioniValide(select) {
        return Array.prototype.filter.call(select.options, function (o) {
            return o.value !== '';
        });
    }

    function creaSelectRicerca(select) {
        if (select.dataset.ricercaInit) return;
        select.dataset.ricercaInit = '1';

        var wrap = document.createElement('div');
        wrap.className = 'sel-ricerca-wrap';
        select.parentNode.insertBefore(wrap, select);
        wrap.appendChild(select);
        select.hidden = true;

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'sel-ricerca-input';
        if (select.className) input.className += ' ' + select.className;
        // Un eventuale style inline sul <select> originale (es. un
        // max-width per stare dentro una riga stretta di tabella) va
        // riportato sull'input visibile, altrimenti si perde.
        if (select.getAttribute('style')) input.setAttribute('style', select.getAttribute('style'));
        input.autocomplete = 'off';
        input.placeholder = select.dataset.placeholder || 'Cerca o scegli…';
        if (select.disabled) input.disabled = true;
        wrap.appendChild(input);

        var menu = document.createElement('div');
        menu.className = 'sel-ricerca-menu';
        menu.hidden = true;
        wrap.appendChild(menu);

        input.value = etichettaSelezionata(select);

        function chiudiMenu() {
            menu.hidden = true;
            wrap.classList.remove('aperto');
        }

        function scegli(opt, item) {
            select.value = opt.value;
            input.value = testoOpzione(opt);
            chiudiMenu();
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function renderMenu(filtro) {
            var f = filtro.trim().toLowerCase();
            menu.innerHTML = '';
            var trovati = 0;
            opzioniValide(select).forEach(function (opt) {
                var testo = testoOpzione(opt);
                if (!f || testo.toLowerCase().indexOf(f) !== -1) {
                    trovati++;
                    var item = document.createElement('div');
                    item.className = 'sel-ricerca-item';
                    item.textContent = testo;
                    if (opt.value === select.value) item.classList.add('selezionato');
                    item.addEventListener('mousedown', function (e) {
                        e.preventDefault();
                        scegli(opt, item);
                    });
                    menu.appendChild(item);
                }
            });
            if (!trovati) {
                var vuoto = document.createElement('div');
                vuoto.className = 'sel-ricerca-vuoto';
                vuoto.textContent = 'Nessun risultato';
                menu.appendChild(vuoto);
            }
        }

        function apriMenu() {
            var etichetta = etichettaSelezionata(select);
            renderMenu(input.value === etichetta ? '' : input.value);
            menu.hidden = false;
            wrap.classList.add('aperto');
        }

        input.addEventListener('focus', function () {
            input.select();
            apriMenu();
        });
        input.addEventListener('input', apriMenu);
        input.addEventListener('blur', function () {
            // Ritardo per lasciare che il mousedown sull'opzione scelga
            // prima che il blur ripristini l'etichetta corrente.
            setTimeout(function () {
                chiudiMenu();
                input.value = etichettaSelezionata(select);
            }, 150);
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                chiudiMenu();
                input.value = etichettaSelezionata(select);
                input.blur();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                var primo = menu.querySelector('.sel-ricerca-item');
                if (primo) primo.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            }
        });

        // Un cambio di valore fatto da codice esterno (reset form,
        // precompilazione) deve aggiornare l'etichetta visibile.
        select.addEventListener('change', function () {
            if (document.activeElement !== input) input.value = etichettaSelezionata(select);
        });
    }

    function inizializza() {
        document.querySelectorAll('select[data-search]').forEach(creaSelectRicerca);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inizializza);
    } else {
        inizializza();
    }

    window.inizializzaSelectRicerca = inizializza;
})();
