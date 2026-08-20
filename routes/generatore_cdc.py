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

# Riunioni di dipartimento/materia: NIENTE motore di scheduling — a
# differenza delle classi, dipartimenti diversi non condividono mai
# docenti per definizione (segnalato da Roberto), quindi non serve
# verificare sovrapposizioni. Vanno solo piazzate in data — vedi
# route dipartimenti() più sotto, che infatti non usa
# modules/generatore_cdc.py::genera_bozza_cdc.
#
# 'riunione_referenti' è tenuta distinta dalle altre due (segnalato da
# Roberto): riservata ai soli capidipartimento, pesa diversamente nel
# conteggio ore proprio per questo — i partecipanti vengono da
# referenti_per_dipartimento(), non da docenti_per_dipartimento()
# (tutti i docenti del dipartimento) usata per le altre due.
TIPI_DIPARTIMENTO = {
    'dipartimento':       {'label': 'Riunione dipartimento',       'durata_default': 60},
    'riunione_materia':   {'label': 'Riunione per materia',        'durata_default': 45},
    'riunione_referenti': {'label': 'Riunione referenti (capidipartimento)', 'durata_default': 45},
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
        ora_inizio_giorno = request.form['ora_inizio_giorno']
        ora_fine_giorno = request.form['ora_fine_giorno']
        durata_min = int(request.form.get('durata_min', 60))
        classi_ds = set(request.form.getlist('classi_ds'))

        if not classi_sel:
            flash('Seleziona almeno una classe.', 'warning')
            return redirect(url_for('generatore_cdc.index', anno=anno))

        # Più turni nello stesso invio (es. CdC di ottobre, dicembre,
        # marzo, maggio): stesse classi/orario/DS per ognuno, generati
        # indipendentemente uno dall'altro — un turno non "sa" dello
        # slot usato da un altro, ha senso così perché sono periodi
        # diversi dell'anno, non in competizione per lo stesso spazio.
        n_turni = int(request.form.get('n_turni', 1))
        bozza = []
        turni_letti = 0
        for t in range(n_turni):
            ini_raw = request.form.get(f'data_inizio_{t}', '').strip()
            fin_raw = request.form.get(f'data_fine_{t}', '').strip()
            if not (ini_raw and fin_raw):
                continue
            data_inizio = date.fromisoformat(ini_raw)
            data_fine = date.fromisoformat(fin_raw)
            turni_letti += 1
            bozza_turno = genera_bozza_cdc(
                anno, classi_sel, data_inizio, data_fine,
                ora_inizio_giorno, ora_fine_giorno, durata_min=durata_min,
                classi_richiedono_ds=classi_ds)
            for r in bozza_turno:
                r['turno'] = turni_letti
                r['turno_periodo'] = f"{data_inizio.strftime('%d/%m')}–{data_fine.strftime('%d/%m/%Y')}"
            bozza.extend(bozza_turno)

        if not bozza:
            flash('Indica almeno un periodo valido (dal/al) per un turno.', 'warning')
            return redirect(url_for('generatore_cdc.index', anno=anno))

        return render_template('generatore_cdc/bozza.html',
            anno=anno, bozza=bozza, durata_min=durata_min, n_turni=turni_letti,
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


# ── RIUNIONI DIPARTIMENTO/MATERIA (nessun motore, solo piazzamento) ──────────

@generatore_cdc_bp.route('/generatore-cdc/dipartimenti', methods=['GET', 'POST'])
def dipartimenti():
    from models.materia import Dipartimento
    from modules.generatore_cdc import docenti_per_dipartimento, referenti_per_dipartimento
    from routes.impostazione_anno import _anno_default_piano

    anno = request.args.get('anno') or request.form.get('anno_scol') or _anno_default_piano()
    anni_disponibili = _anni_disponibili_assegnazioni(anno)
    dips = Dipartimento.query.order_by(Dipartimento.ordine).all()

    if request.method == 'POST' and request.form.get('azione') == 'genera':
        tipo = request.form.get('tipo', 'dipartimento')
        if tipo not in TIPI_DIPARTIMENTO:
            tipo = 'dipartimento'
        dip_ids = [int(i) for i in request.form.getlist('dipartimenti')]
        data_s = request.form.get('data', '').strip()
        ora_inizio = request.form.get('ora_inizio', '').strip()
        durata_min = int(request.form.get('durata_min', 60))

        if not dip_ids:
            flash('Seleziona almeno un dipartimento.', 'warning')
            return redirect(url_for('generatore_cdc.dipartimenti', anno=anno))
        if not (data_s and ora_inizio):
            flash('Indica data e ora.', 'warning')
            return redirect(url_for('generatore_cdc.dipartimenti', anno=anno))

        # Nessuna verifica di sovrapposizione: dipartimenti diversi non
        # condividono mai docenti, possono benissimo stare tutti nello
        # stesso slot — si piazzano semplicemente, come richiesto.
        h, m = map(int, ora_inizio.split(':'))
        fine_min = h * 60 + m + durata_min
        ora_fine = f'{fine_min // 60:02d}:{fine_min % 60:02d}'
        # Per i referenti, segnala già in bozza i dipartimenti senza
        # nessuno nominato — non blocca (crea comunque l'evento, senza
        # partecipanti, correggibile a mano), ma è meglio saperlo prima.
        referenti_map = referenti_per_dipartimento(anno) if tipo == 'riunione_referenti' else {}
        dips_sel = [d for d in dips if d.id in dip_ids]
        righe = [dict(id_dipartimento=d.id, sigla=d.sigla, nome=d.nome,
                      data=data_s, ora_inizio=ora_inizio, ora_fine=ora_fine,
                      senza_referente=(tipo == 'riunione_referenti' and not referenti_map.get(d.id)))
                 for d in dips_sel]

        return render_template('generatore_cdc/dipartimenti_bozza.html',
            anno=anno, righe=righe, tipo=tipo, tipo_label=TIPI_DIPARTIMENTO[tipo]['label'])

    if request.method == 'POST' and request.form.get('azione') == 'conferma':
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
        tipo = request.form.get('tipo', 'dipartimento')
        if tipo not in TIPI_DIPARTIMENTO:
            tipo = 'dipartimento'
        tipo_label = TIPI_DIPARTIMENTO[tipo]['label']
        n_ini = int(request.form.get('n_righe', 0))
        docenti_map = (referenti_per_dipartimento(anno) if tipo == 'riunione_referenti'
                       else docenti_per_dipartimento(anno))
        creati = 0
        for i in range(n_ini):
            id_dip = request.form.get(f'id_dipartimento_{i}', '').strip()
            sigla = request.form.get(f'sigla_{i}', '').strip()
            data_s = request.form.get(f'data_{i}', '').strip()
            ora_ini = request.form.get(f'ora_inizio_{i}', '').strip()
            ora_fin = request.form.get(f'ora_fine_{i}', '').strip()
            if not (id_dip and data_s and ora_ini and ora_fin):
                continue
            id_dip = int(id_dip)
            ev = AttivitaIst(
                tipo=tipo, titolo=f'{tipo_label} {sigla}',
                data=date.fromisoformat(data_s), ora_inizio=ora_ini, ora_fine=ora_fin,
                id_dipartimento=id_dip, origine='import_piano',
            )
            db.session.add(ev)
            db.session.flush()
            for id_doc in docenti_map.get(id_dip, ()):
                db.session.add(AttivitaIstPartecipante(
                    id_attivita=ev.id, id_docente=id_doc, preset=True))
            creati += 1
        db.session.commit()
        flash(f'{creati} eventi "{tipo_label}" creati.', 'success')
        return redirect(url_for('attivita_ist.piano_annuale', anno=anno))

    return render_template('generatore_cdc/dipartimenti_index.html',
        anno=anno, anni_disponibili=anni_disponibili, dipartimenti=dips,
        tipi_dipartimento=TIPI_DIPARTIMENTO)


# ── EVENTI UNICI (Collegio, Incontro scuola-famiglia) ────────────────────────
# Un solo evento per l'intero istituto, non "tante unità che si
# dividono gli slot" come Consigli/dipartimenti — niente bozza con più
# righe, si crea direttamente. L'unica scelta non banale è per
# l'Incontro scuola-famiglia: tutti i docenti o solo i coordinatori di
# classe (segnalato da Roberto — è sempre una sola riunione, cambia
# solo chi vi partecipa).
TIPI_UNICI = {
    'collegio':          {'label': 'Collegio docenti',         'durata_default': 120},
    'incontro_famiglie': {'label': 'Incontro scuola-famiglia', 'durata_default': 120},
}


@generatore_cdc_bp.route('/generatore-cdc/eventi-unici', methods=['GET', 'POST'])
def eventi_unici():
    from routes.impostazione_anno import _anno_default_piano
    anno = request.args.get('anno') or request.form.get('anno_scol') or _anno_default_piano()
    anni_disponibili = _anni_disponibili_assegnazioni(anno)

    if request.method == 'POST':
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
        from models.docente import Docente
        from routes.attivita_ist import _non_in_servizio_per_data
        from modules.generatore_cdc import coordinatori_di_classe

        tipo = request.form.get('tipo', 'collegio')
        if tipo not in TIPI_UNICI:
            tipo = 'collegio'
        titolo = request.form.get('titolo', '').strip() or TIPI_UNICI[tipo]['label']
        data_s = request.form['data']
        ora_inizio = request.form['ora_inizio']
        durata_min = int(request.form.get('durata_min', 60))
        partecipanti_sel = request.form.get('partecipanti', 'tutti')

        data_ev = date.fromisoformat(data_s)
        h, m = map(int, ora_inizio.split(':'))
        fine_min = h * 60 + m + durata_min
        ora_fine = f'{fine_min // 60:02d}:{fine_min % 60:02d}'

        esclusi = _non_in_servizio_per_data(data_ev)
        if tipo == 'incontro_famiglie' and partecipanti_sel == 'coordinatori':
            id_docenti = coordinatori_di_classe(anno) - esclusi
        else:
            id_docenti = {d.id for d in Docente.query.filter_by(attivo=True).all()} - esclusi

        ev = AttivitaIst(
            tipo=tipo, titolo=titolo, data=data_ev,
            ora_inizio=ora_inizio, ora_fine=ora_fine, origine='import_piano',
        )
        db.session.add(ev)
        db.session.flush()
        for id_doc in id_docenti:
            db.session.add(AttivitaIstPartecipante(
                id_attivita=ev.id, id_docente=id_doc, preset=True))
        db.session.commit()
        flash(f'Evento "{titolo}" creato ({len(id_docenti)} partecipanti).', 'success')
        return redirect(url_for('attivita_ist.piano_annuale', anno=anno))

    return render_template('generatore_cdc/eventi_unici.html',
        anno=anno, anni_disponibili=anni_disponibili, tipi_unici=TIPI_UNICI)
