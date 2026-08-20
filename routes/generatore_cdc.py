"""
Generatore Consigli di Classe — Piano Annuale delle Attività, Fase 3.
Route: gestione vincoli (orario fisso, manuali pre-generazione) e il
generatore vero e proprio (bozza modificabile, mai un piano imposto —
vedi modules/generatore_cdc.py per la logica).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.generatore_cdc import (VincoloOrarioClasse, VincoloGeneratoreCdc,
                                    GIORNI_SETTIMANA, TIPI_VINCOLO_CDC)
from datetime import date

generatore_cdc_bp = Blueprint('generatore_cdc', __name__)

# Tipi generabili con lo stesso motore, tutti scoped per classe (si
# seleziona l'elenco classi del turno, come per Consigli/Scrutini). Il
# Collegio docenti resta fuori di proposito: coinvolge tutti i docenti
# insieme, non ha nulla da mettere in parallelo (non è "tante classi
# che si dividono gli slot").
#
# GLO: _preset_partecipanti() lo tratta altrove come "solo manuale"
# (nessun preset automatico, perché la composizione reale dipende
# dall'alunno seguito, non dall'intera classe) — qui invece, per
# evitare sovrapposizioni in fase di generazione, si usa comunque
# l'insieme docenti dell'intera classe come segnale di conflitto: è
# una stima per eccesso (i docenti coinvolti in un GLO specifico sono
# di solito un sottoinsieme più piccolo, tipicamente il sostegno più
# pochi curricolari), quindi il generatore potrebbe evitare
# sovrapposizioni non realmente necessarie e proporre meno slot del
# possibile — mai il contrario (nessun rischio di doppio impegno). I
# partecipanti dell'evento creato restano comunque una proposta,
# modificabile come sempre dalla pagina presenze.
TIPI_GENERABILI = {
    'consiglio_classe': {'label': 'Consiglio di classe', 'durata_default': 60},
    'scrutinio':         {'label': 'Scrutinio',           'durata_default': 45},
    'glo':                {'label': 'GLO',                 'durata_default': 45},
}


def _anno_scolastico(d=None):
    d = d or date.today()
    return f'{d.year}-{d.year+1}' if d.month >= 9 else f'{d.year-1}-{d.year}'


def _anni_disponibili_assegnazioni(anno_corrente):
    """Anni con Assegnazioni già inserite, più recenti prima — stesso
    ruolo di _anno_default_piano() ma come elenco per il selettore a
    pillole. Il piano annuale è un'attività preparatoria per il nuovo
    anno (come Assegnazioni/richiesta organico), quindi l'anno di
    default deve essere quello in preparazione, non quello corrente."""
    from models.assegnazione import AssegnazioneDocente
    anni = sorted({a.anno_scol for a in AssegnazioneDocente.query.all()}, reverse=True)
    if anno_corrente not in anni:
        anni.insert(0, anno_corrente)
    return anni


# ── VINCOLI ORARIO FISSI (finestre settimanali indisponibili) ────────────────

@generatore_cdc_bp.route('/generatore-cdc/vincoli-orario', methods=['GET', 'POST'])
def vincoli_orario():
    if request.method == 'POST':
        azione = request.form.get('azione')
        if azione == 'aggiungi':
            db.session.add(VincoloOrarioClasse(
                giorno_settimana=int(request.form['giorno_settimana']),
                ora_inizio=request.form['ora_inizio'],
                ora_fine=request.form['ora_fine'],
                indirizzi=request.form['indirizzi'].strip().upper(),
                anno_corso_min=int(request.form['anno_corso_min']) if request.form.get('anno_corso_min') else None,
                anno_corso_max=int(request.form['anno_corso_max']) if request.form.get('anno_corso_max') else None,
                descrizione=request.form.get('descrizione', '').strip() or None,
            ))
            db.session.commit()
            flash('Vincolo orario aggiunto.', 'success')
        elif azione == 'elimina':
            v = VincoloOrarioClasse.query.get_or_404(int(request.form['id']))
            db.session.delete(v)
            db.session.commit()
            flash('Vincolo orario eliminato.', 'warning')
        return redirect(url_for('generatore_cdc.vincoli_orario'))

    vincoli = VincoloOrarioClasse.query.order_by(
        VincoloOrarioClasse.giorno_settimana, VincoloOrarioClasse.ora_inizio).all()
    return render_template('generatore_cdc/vincoli_orario.html',
        vincoli=vincoli, giorni=list(enumerate(GIORNI_SETTIMANA)))


# ── VINCOLI MANUALI PRE-GENERAZIONE ──────────────────────────────────────────

@generatore_cdc_bp.route('/generatore-cdc/vincoli-manuali', methods=['GET', 'POST'])
def vincoli_manuali():
    from routes.impostazione_anno import _anno_default_piano
    anno = request.args.get('anno', _anno_default_piano())
    anni_disponibili = _anni_disponibili_assegnazioni(anno)

    if request.method == 'POST':
        azione = request.form.get('azione')
        if azione == 'aggiungi':
            tipo = request.form.get('tipo', 'entro_data')
            db.session.add(VincoloGeneratoreCdc(
                anno_scol=request.form.get('anno_scol', anno),
                classe=request.form['classe'].strip().upper(),
                tipo=tipo,
                scadenza=date.fromisoformat(request.form['scadenza']) if tipo == 'entro_data' and request.form.get('scadenza') else None,
                data_fissa=date.fromisoformat(request.form['data_fissa']) if tipo == 'fissa' and request.form.get('data_fissa') else None,
                ora_fissa=request.form.get('ora_fissa') if tipo == 'fissa' else None,
                note=request.form.get('note', '').strip() or None,
            ))
            db.session.commit()
            flash('Vincolo aggiunto.', 'success')
        elif azione == 'elimina':
            v = VincoloGeneratoreCdc.query.get_or_404(int(request.form['id']))
            db.session.delete(v)
            db.session.commit()
            flash('Vincolo eliminato.', 'warning')
        return redirect(url_for('generatore_cdc.vincoli_manuali', anno=anno))

    vincoli = VincoloGeneratoreCdc.query.filter_by(anno_scol=anno).order_by(
        VincoloGeneratoreCdc.classe).all()
    return render_template('generatore_cdc/vincoli_manuali.html',
        vincoli=vincoli, anno=anno, anni_disponibili=anni_disponibili, tipi=TIPI_VINCOLO_CDC)


# ── GENERATORE ────────────────────────────────────────────────────────────────

@generatore_cdc_bp.route('/generatore-cdc', methods=['GET', 'POST'])
def index():
    from modules.generatore_cdc import docenti_reali_per_classe, genera_bozza_cdc
    from routes.impostazione_anno import _anno_default_piano

    anno = request.args.get('anno') or request.form.get('anno_scol') or _anno_default_piano()
    anni_disponibili = _anni_disponibili_assegnazioni(anno)
    classi_disponibili = sorted(docenti_reali_per_classe(anno).keys())

    if request.method == 'POST' and request.form.get('azione') == 'genera':
        tipo = request.form.get('tipo', 'consiglio_classe')
        if tipo not in TIPI_GENERABILI:
            tipo = 'consiglio_classe'
        classi_sel = request.form.getlist('classi')
        data_inizio = date.fromisoformat(request.form['data_inizio'])
        data_fine = date.fromisoformat(request.form['data_fine'])
        ora_inizio_giorno = request.form['ora_inizio_giorno']
        ora_fine_giorno = request.form['ora_fine_giorno']
        durata_min = int(request.form.get('durata_min', 60))
        classi_ds = set(request.form.getlist('classi_ds'))

        if not classi_sel:
            flash('Seleziona almeno una classe.', 'warning')
            return redirect(url_for('generatore_cdc.index', anno=anno))

        bozza = genera_bozza_cdc(
            anno, classi_sel, data_inizio, data_fine,
            ora_inizio_giorno, ora_fine_giorno, durata_min=durata_min,
            classi_richiedono_ds=classi_ds)

        return render_template('generatore_cdc/bozza.html',
            anno=anno, bozza=bozza, durata_min=durata_min,
            classi_ds=classi_ds, tipo=tipo, tipo_label=TIPI_GENERABILI[tipo]['label'])

    if request.method == 'POST' and request.form.get('azione') == 'conferma':
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
        from modules.generatore_cdc import docenti_reali_per_classe as _drc
        tipo = request.form.get('tipo', 'consiglio_classe')
        if tipo not in TIPI_GENERABILI:
            tipo = 'consiglio_classe'
        tipo_label = TIPI_GENERABILI[tipo]['label']
        n_ini = int(request.form.get('n_righe', 0))
        docenti_map = _drc(anno)
        creati = 0
        for i in range(n_ini):
            classe = request.form.get(f'classe_{i}', '').strip()
            data_s = request.form.get(f'data_{i}', '').strip()
            ora_ini = request.form.get(f'ora_inizio_{i}', '').strip()
            ora_fin = request.form.get(f'ora_fine_{i}', '').strip()
            richiede_ds = request.form.get(f'ds_{i}') == 'on'
            if not (classe and data_s and ora_ini and ora_fin):
                continue  # riga lasciata vuota/in conflitto: non creata, va piazzata a mano
            ev = AttivitaIst(
                tipo=tipo, titolo=f'{tipo_label} {classe}',
                data=date.fromisoformat(data_s), ora_inizio=ora_ini, ora_fine=ora_fin,
                classe=classe, origine='import_piano', richiede_ds=richiede_ds,
            )
            db.session.add(ev)
            db.session.flush()
            for id_doc in docenti_map.get(classe, ()):
                db.session.add(AttivitaIstPartecipante(
                    id_attivita=ev.id, id_docente=id_doc, preset=True))
            creati += 1
        db.session.commit()
        flash(f'{creati} eventi "{tipo_label}" creati.', 'success')
        return redirect(url_for('attivita_ist.piano_annuale', anno=anno))

    return render_template('generatore_cdc/index.html',
        anno=anno, anni_disponibili=anni_disponibili, classi_disponibili=classi_disponibili,
        tipi_generabili=TIPI_GENERABILI)
