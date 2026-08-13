from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.attivita_ist import (AttivitaIst, AttivitaIstPartecipante,
                                  AttivitaIstPresenza, TIPI_ATTIVITA)
from models.materia import Dipartimento, Materia, DocenteMateria
from models.docente import Docente
from models.assenza import Assenza
from datetime import date, datetime
import json

attivita_ist_bp = Blueprint('attivita_ist', __name__)

def _anno_scolastico(d=None):
    d = d or date.today()
    return f'{d.year}-{d.year+1}' if d.month >= 9 else f'{d.year-1}-{d.year}'


def _non_in_servizio_per_data(data_evento):
    """
    Docenti non disponibili per un evento in una data specifica.
    Due controlli distinti, applicati insieme:

    1. Non in servizio nell'anno scolastico dell'evento (uscita già
       segnalata, AP uscente, aspettativa) — vedi
       routes/docenti.py::_docenti_non_in_servizio.

    2. SOLO per eventi di luglio/agosto: il contratto potrebbe essere
       già scaduto pur restando nello stesso anno scolastico. I supplenti
       brevi e i TD "fino a GS" (giorno degli scrutini, CCNL — contratto
       prorogato fino al termine delle operazioni di scrutinio, fine
       giugno) NON sono in servizio a luglio/agosto; solo TI e TD annuale
       lo sono, fino al 31 agosto compreso. Stessa regola già in uso in
       routes/recupero_costanti.py::CONTRATTI_OK per le prove di recupero
       di agosto — riusata qui invece di reinventarla.
    """
    from routes.docenti import _docenti_non_in_servizio
    anno_evento = _anno_scolastico(data_evento)
    esclusi = {d.id for d in _docenti_non_in_servizio(anno_evento)}

    if data_evento.month in (7, 8):
        from routes.recupero_costanti import CONTRATTI_OK
        esclusi |= {d.id for d in Docente.query.filter(
            Docente.attivo == True,
            db.or_(Docente.tipo_contratto == None,
                   ~Docente.tipo_contratto.in_(CONTRATTI_OK))
        ).all()}

    return esclusi



def _preset_partecipanti(attivita):
    """
    Genera lista docenti previsti per l'evento in base al tipo, escludendo
    chi non è in servizio alla data dell'evento — vedi
    _non_in_servizio_per_data() (uscita già segnalata, AP uscente/
    aspettativa, e per luglio/agosto anche il tipo di contratto scaduto:
    supplenti brevi e TD fino a GS). Senza questo controllo, un docente
    non più disponibile continuerebbe a comparire come partecipante
    previsto anche dopo che ha lasciato la scuola o dopo la scadenza del
    contratto.
    """
    esclusi_ids = _non_in_servizio_per_data(attivita.data)

    docenti_attivi = [d for d in Docente.query.filter_by(attivo=True).all()
                      if d.id not in esclusi_ids]
    tipo = attivita.tipo

    if tipo in ('collegio', 'incontro_famiglie', 'formazione'):
        return [d.id for d in docenti_attivi]

    if tipo in ('consiglio_classe', 'scrutinio') and attivita.classe:
        from models.orario_docente import OrarioDocente
        ids = {s.id_docente for s in OrarioDocente.query.filter_by(
            classe=attivita.classe).all()}
        return [i for i in ids if i not in esclusi_ids]

    if tipo in ('dipartimento', 'riunione_materia', 'riunione_referenti') \
            and attivita.id_dipartimento:
        # Anno scolastico dell'EVENTO (dalla sua data), non "oggi": una
        # riunione di dipartimento programmata per marzo 2027 deve
        # guardare le materie del 2026-2027, indipendentemente da
        # quando la si sta creando.
        ids = {dm.id_docente for dm in DocenteMateria.query.join(Materia).filter(
            Materia.id_dipartimento == attivita.id_dipartimento,
            DocenteMateria.anno_scol == _anno_scolastico(attivita.data)
        ).all()}
        return [i for i in ids if i not in esclusi_ids]

    if tipo == 'glo':
        return []  # solo manuale

    return [d.id for d in docenti_attivi]


def _auto_presenze(attivita):
    """Crea record presenze per i partecipanti, pre-compilando assenti noti."""
    assenze_giorno = {a.id_docente: a for a in
                      Assenza.query.filter_by(data=attivita.data).all()}
    for part in attivita.partecipanti:
        dup = AttivitaIstPresenza.query.filter_by(
            id_attivita=attivita.id, id_docente=part.id_docente).first()
        if dup:
            continue
        assenza = assenze_giorno.get(part.id_docente)
        stato = 'assente' if assenza else 'presente'
        db.session.add(AttivitaIstPresenza(
            id_attivita          = attivita.id,
            id_docente           = part.id_docente,
            stato                = stato,
            id_assenza_collegata = assenza.id if assenza else None,
        ))


# ── LISTA ────────────────────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist')
def lista():
    from datetime import date
    oggi = date.today()
    anno = request.args.get('anno', _anno_scolastico())
    anno_ini = date(int(anno[:4]), 9, 1)
    anno_fin = date(int(anno[:4]) + 1, 8, 31)
    tipo_f   = request.args.get('tipo', '')
    mese_f   = request.args.get('mese', '')

    q = AttivitaIst.query.filter(
        AttivitaIst.data >= anno_ini,
        AttivitaIst.data <= anno_fin,
    )
    if tipo_f:
        q = q.filter_by(tipo=tipo_f)
    if mese_f:
        q = q.filter(db.func.strftime('%m', AttivitaIst.data) == mese_f.zfill(2))
    eventi = q.order_by(AttivitaIst.data, AttivitaIst.ora_inizio).all()

    # Separa le attività già svolte (data passata) da quelle future/odierne:
    # le prime finiscono in una tabella a parte, in fondo alla pagina,
    # più recenti per prime.
    eventi_futuri  = [e for e in eventi if e.data >= oggi]
    eventi_passati = [e for e in eventi if e.data < oggi]
    eventi_passati.reverse()

    dipartimenti = Dipartimento.query.order_by(Dipartimento.ordine).all()
    return render_template('attivita_ist/lista.html',
        eventi_futuri=eventi_futuri, eventi_passati=eventi_passati,
        oggi=oggi, anno=anno,
        tipi=TIPI_ATTIVITA, tipo_f=tipo_f, mese_f=mese_f,
        dipartimenti=dipartimenti,
    )


# ── NUOVO / MODIFICA ─────────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/nuova', methods=['GET', 'POST'])
@attivita_ist_bp.route('/attivita-ist/<int:id>/modifica', methods=['GET', 'POST'])
def form(id=None):
    evento = AttivitaIst.query.get_or_404(id) if id else None
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    dipartimenti = Dipartimento.query.order_by(Dipartimento.ordine).all()
    classi_db = sorted({s.classe for s in
                        __import__('models.orario_docente', fromlist=['OrarioDocente'])
                        .OrarioDocente.query.all()
                        if s.classe and s.classe not in ('POTENZIAMENTO','---','-x-','')})

    if request.method == 'POST':
        tipo        = request.form['tipo']
        titolo      = request.form['titolo'].strip()
        data_s      = request.form['data']
        ora_ini     = request.form.get('ora_inizio', '').strip() or None
        ora_fin     = request.form.get('ora_fine', '').strip() or None
        note        = request.form.get('note', '').strip() or None
        classe      = request.form.get('classe', '').strip() or None
        id_dip      = request.form.get('id_dipartimento') or None
        doc_ids_raw = request.form.getlist('docenti_ids')
        doc_ids     = [int(x) for x in doc_ids_raw if x.isdigit()]

        if evento:
            # Modifica
            evento.tipo = tipo; evento.titolo = titolo
            evento.data = date.fromisoformat(data_s)
            evento.ora_inizio = ora_ini; evento.ora_fine = ora_fin
            evento.note = note; evento.classe = classe
            evento.id_dipartimento = int(id_dip) if id_dip else None
            # Ricrea partecipanti
            AttivitaIstPartecipante.query.filter_by(id_attivita=evento.id).delete()
        else:
            evento = AttivitaIst(
                tipo=tipo, titolo=titolo,
                data=date.fromisoformat(data_s),
                ora_inizio=ora_ini, ora_fine=ora_fin,
                note=note, classe=classe,
                id_dipartimento=int(id_dip) if id_dip else None,
                origine='manuale',
            )
            db.session.add(evento)
        db.session.flush()

        # Partecipanti: usa preset se nessuna selezione manuale
        if not doc_ids:
            doc_ids = _preset_partecipanti(evento)
        for did in doc_ids:
            db.session.add(AttivitaIstPartecipante(
                id_attivita=evento.id, id_docente=did, preset=True))

        db.session.commit()
        flash(f'Evento {"aggiornato" if id else "registrato"}: {titolo}', 'success')
        return redirect(url_for('attivita_ist.lista'))

    # Pre-selezione docenti per preset
    preset_ids = _preset_partecipanti(evento) if evento else []
    docenti_selezionati = {p.id_docente for p in evento.partecipanti} if evento else set()
    return render_template('attivita_ist/form.html',
        evento=evento, docenti=docenti, dipartimenti=dipartimenti,
        classi=classi_db, tipi=TIPI_ATTIVITA,
        preset_ids=preset_ids,
        docenti_selezionati=docenti_selezionati,
        data_sel=(evento.data.isoformat() if evento
                  else request.args.get('data', date.today().isoformat())),
    )


# ── ELIMINA ──────────────────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/<int:id>/elimina', methods=['POST'])
def elimina(id):
    e = AttivitaIst.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash('Evento eliminato.', 'warning')
    return redirect(url_for('attivita_ist.lista'))


# ── PRESENZE ─────────────────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/<int:id>/presenze', methods=['GET', 'POST'])
def presenze(id):
    evento = AttivitaIst.query.get_or_404(id)

    # Auto-genera presenze mancanti (anche se alcune già esistono)
    presenti_ids = {p.id_docente for p in evento.presenze}
    mancanti = [p for p in evento.partecipanti if p.id_docente not in presenti_ids]
    if mancanti:
        for part in mancanti:
            db.session.add(AttivitaIstPresenza(
                id_attivita=evento.id,
                id_docente=part.id_docente,
                stato='presente',
            ))
        db.session.commit()

    if request.method == 'POST':
        for p in evento.presenze:
            stato    = request.form.get(f'stato_{p.id_docente}', 'presente')
            nota     = request.form.get(f'nota_{p.id_docente}', '').strip() or None
            ora_ini  = request.form.get(f'ora_ini_{p.id_docente}', '').strip() or None
            ora_fin  = request.form.get(f'ora_fin_{p.id_docente}', '').strip() or None
            p.stato          = stato
            p.note           = nota
            # Ore parziali: salva solo se diverse dall'intero evento
            p.ora_inizio_eff = ora_ini if (ora_ini and ora_ini != evento.ora_inizio) else None
            p.ora_fine_eff   = ora_fin if (ora_fin and ora_fin != evento.ora_fine)   else None
        db.session.commit()
        flash('Presenze salvate.', 'success')
        return redirect(url_for('attivita_ist.presenze', id=id))

    assenze_giorno = {a.id_docente: a for a in
                      Assenza.query.filter_by(data=evento.data).all()}

    # Indisponibilità dichiarate per la stessa data (impegni già noti:
    # colloqui, uscite, gare, formazione, ecc.) — non escludono di per sé
    # dalla convocazione (a differenza delle assenze), ma vanno segnalate
    # perché indicano un possibile conflitto da verificare.
    from models.indisponibilita import Indisponibilita
    indisponibilita_giorno = {}
    for i in Indisponibilita.query.filter_by(data=evento.data).all():
        indisponibilita_giorno.setdefault(i.id_docente, []).append(i)

    docenti_extra = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    presenze_map  = {p.id_docente: p for p in evento.presenze}

    # Docenti convocati (già presenti in elenco) ma non più in servizio alla
    # data dell'evento: segnalati con un avviso per ricordare di nominare un
    # sostituto (per gli scrutini si può usare la funzione "Sostituzioni").
    # Include anche, per gli eventi di luglio/agosto, chi ha un contratto già
    # scaduto (supplenti brevi, TD fino a GS) — vedi _non_in_servizio_per_data.
    non_in_servizio_ids = _non_in_servizio_per_data(evento.data)

    return render_template('attivita_ist/presenze.html',
        evento=evento, presenze_map=presenze_map,
        assenze_giorno=assenze_giorno,
        indisponibilita_giorno=indisponibilita_giorno,
        docenti_extra=docenti_extra,
        non_in_servizio_ids=non_in_servizio_ids,
    )


@attivita_ist_bp.route('/attivita-ist/<int:id>/presenze/aggiungi', methods=['POST'])
def aggiungi_partecipante(id):
    evento = AttivitaIst.query.get_or_404(id)
    did = int(request.form['id_docente'])
    dup = AttivitaIstPartecipante.query.filter_by(
        id_attivita=id, id_docente=did).first()
    if not dup:
        db.session.add(AttivitaIstPartecipante(
            id_attivita=id, id_docente=did, preset=False))
        db.session.flush()
    # Aggiunge presenza se non c'è
    dup_p = AttivitaIstPresenza.query.filter_by(
        id_attivita=id, id_docente=did).first()
    if not dup_p:
        assenza = Assenza.query.filter_by(
            id_docente=did, data=evento.data).first()
        db.session.add(AttivitaIstPresenza(
            id_attivita=id, id_docente=did,
            stato='assente' if assenza else 'presente',
            id_assenza_collegata=assenza.id if assenza else None,
        ))
    db.session.commit()
    flash('Docente aggiunto.', 'success')
    return redirect(url_for('attivita_ist.presenze', id=id))


# ── IMPORT PIANO ANNUALE ─────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/import-piano', methods=['GET', 'POST'])
def import_piano():
    if request.method == 'POST':
        n = _import_piano_2025_26()
        flash(f'Importati {n} eventi dal Piano delle Attività 2025/26.', 'success')
        return redirect(url_for('attivita_ist.lista'))
    # Controlla se già importato
    gia = AttivitaIst.query.filter_by(origine='import_piano').count()
    return render_template('attivita_ist/import_piano.html', gia_importati=gia)


def _import_piano_2025_26():
    """
    Importa gli eventi rimanenti del Piano 2025/26 (da giugno 2026 in poi,
    dato che i mesi precedenti sono già passati).
    Solo eventi non ancora presenti (controllo per tipo+data+titolo).
    """
    EVENTI = [
        # ── GIUGNO 2026 ──────────────────────────────────────────────────
        # Scrutini finali 6/6 — ordine da piano attività
        # LL: col6 → LLI
        {'tipo':'scrutinio','titolo':'Scrutinio finale LLI V A','data':'2026-06-06','ora_ini':'10:30','ora_fin':'11:15','classe':'5A LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio finale LLI V B','data':'2026-06-06','ora_ini':'11:15','ora_fin':'12:00','classe':'5B LLI'},
        # LSC: col4 → 12:45
        {'tipo':'scrutinio','titolo':'Scrutinio finale LSC V A','data':'2026-06-06','ora_ini':'12:45','ora_fin':'13:15','classe':'5A LSC'},
        # LSP: col7 → 14:00
        {'tipo':'scrutinio','titolo':'Scrutinio finale LSP V A','data':'2026-06-06','ora_ini':'14:00','ora_fin':'14:45','classe':'5A LSP'},
        # CAT: col3 → 14:45
        {'tipo':'scrutinio','titolo':'Scrutinio finale CAT V A','data':'2026-06-06','ora_ini':'14:45','ora_fin':'15:30','classe':'5A CAT'},
        # AFM/RIM: col2 → 15:30
        {'tipo':'scrutinio','titolo':'Scrutinio finale RIM V A','data':'2026-06-06','ora_ini':'15:30','ora_fin':'16:15','classe':'5A RIM'},
        # LSU: col5 → 16:15 e 17:00
        {'tipo':'scrutinio','titolo':'Scrutinio finale LSU V A','data':'2026-06-06','ora_ini':'16:15','ora_fin':'17:00','classe':'5A LSU'},
        {'tipo':'scrutinio','titolo':'Scrutinio finale LSU V B','data':'2026-06-06','ora_ini':'17:00','ora_fin':'17:45','classe':'5B LSU'},
        # Scrutini classi intermedie (8-10/6)
        {'tipo':'scrutinio','titolo':'Scrutinio RIM IV A','data':'2026-06-08','ora_ini':'08:00','ora_fin':'08:45','classe':'4A RIM'},
        {'tipo':'scrutinio','titolo':'Scrutinio AFM II A','data':'2026-06-08','ora_ini':'08:45','ora_fin':'09:30','classe':'2A AFM'},
        {'tipo':'scrutinio','titolo':'Scrutinio AFM II B','data':'2026-06-08','ora_ini':'09:30','ora_fin':'10:15','classe':'2B AFM'},
        {'tipo':'scrutinio','titolo':'Scrutinio RIM III A','data':'2026-06-08','ora_ini':'10:15','ora_fin':'11:00','classe':'3A RIM'},
        {'tipo':'scrutinio','titolo':'Scrutinio AFM I A','data':'2026-06-08','ora_ini':'11:00','ora_fin':'11:45','classe':'1A AFM'},
        {'tipo':'scrutinio','titolo':'Scrutinio CAT IV A','data':'2026-06-08','ora_ini':'11:45','ora_fin':'12:30','classe':'4A CAT'},
        {'tipo':'scrutinio','titolo':'Scrutinio CAT III A','data':'2026-06-08','ora_ini':'13:30','ora_fin':'14:15','classe':'3A CAT'},
        {'tipo':'scrutinio','titolo':'Scrutinio CAT II A','data':'2026-06-08','ora_ini':'14:15','ora_fin':'15:00','classe':'2A CAT'},
        {'tipo':'scrutinio','titolo':'Scrutinio CAT I A','data':'2026-06-08','ora_ini':'15:00','ora_fin':'15:45','classe':'1A CAT'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSC IV A','data':'2026-06-09','ora_ini':'08:00','ora_fin':'08:45','classe':'4A LSC'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSC III A','data':'2026-06-09','ora_ini':'08:45','ora_fin':'09:30','classe':'3A LSC'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSC II B','data':'2026-06-09','ora_ini':'09:30','ora_fin':'10:15','classe':'2B LSC'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSC II A','data':'2026-06-09','ora_ini':'10:15','ora_fin':'11:00','classe':'2A LSC'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSC I A','data':'2026-06-09','ora_ini':'11:00','ora_fin':'11:45','classe':'1A LSC'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSU IV A','data':'2026-06-09','ora_ini':'11:45','ora_fin':'12:30','classe':'4A LSU'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSU III A','data':'2026-06-09','ora_ini':'13:30','ora_fin':'14:15','classe':'3A LSU'},
        {'tipo':'scrutinio','titolo':'Scrutinio LL II B','data':'2026-06-09','ora_ini':'14:15','ora_fin':'15:00','classe':'2B LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LL II A','data':'2026-06-09','ora_ini':'15:00','ora_fin':'15:45','classe':'2A LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LL I A','data':'2026-06-09','ora_ini':'15:45','ora_fin':'16:30','classe':'1A LLI'},
        # 10/6: col H=LSP (IV,III,II,I), col G=LL/LLI (I A, I B, II B, II A, III A, IV A)
        {'tipo':'scrutinio','titolo':'Scrutinio LSP IV A','data':'2026-06-10','ora_ini':'08:00','ora_fin':'08:45','classe':'4A LSP'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSP III A','data':'2026-06-10','ora_ini':'08:45','ora_fin':'09:30','classe':'3A LSP'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSP II A','data':'2026-06-10','ora_ini':'09:30','ora_fin':'10:15','classe':'2A LSP'},
        {'tipo':'scrutinio','titolo':'Scrutinio LSP I A','data':'2026-06-10','ora_ini':'10:15','ora_fin':'11:00','classe':'1A LSP'},
        {'tipo':'scrutinio','titolo':'Scrutinio LLI I A','data':'2026-06-10','ora_ini':'11:00','ora_fin':'11:45','classe':'1A LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LLI I B','data':'2026-06-10','ora_ini':'11:45','ora_fin':'12:30','classe':'1B LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LLI II B','data':'2026-06-10','ora_ini':'13:30','ora_fin':'14:15','classe':'2B LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LLI II A','data':'2026-06-10','ora_ini':'14:15','ora_fin':'15:00','classe':'2A LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LLI III A','data':'2026-06-10','ora_ini':'15:00','ora_fin':'15:45','classe':'3A LLI'},
        {'tipo':'scrutinio','titolo':'Scrutinio LLI IV A','data':'2026-06-10','ora_ini':'15:45','ora_fin':'16:30','classe':'4A LLI'},
        # Collegio docenti 12/6
        {'tipo':'collegio','titolo':'Collegio dei docenti — giugno 2026','data':'2026-06-12','ora_ini':'11:00','ora_fin':'12:30'},
        # Incontro per materie 12/6
        {'tipo':'riunione_materia','titolo':'Incontro per materie — recupero giugno','data':'2026-06-12','ora_ini':'09:00','ora_fin':'10:30'},
        # Incontro famiglie 12/6
        {'tipo':'incontro_famiglie','titolo':'Incontro con le famiglie — giugno','data':'2026-06-12','ora_ini':'14:00','ora_fin':'15:00'},
        # ── SETTEMBRE 2026 ────────────────────────────────────────────────
        {'tipo':'collegio','titolo':'Collegio dei docenti — settembre 2026','data':'2026-09-01','ora_ini':'08:30','ora_fin':'13:00'},
    ]

    count = 0
    for ev in EVENTI:
        dup = AttivitaIst.query.filter_by(
            tipo=ev['tipo'], data=date.fromisoformat(ev['data']),
            titolo=ev['titolo']).first()
        if dup:
            continue
        obj = AttivitaIst(
            tipo       = ev['tipo'],
            titolo     = ev['titolo'],
            data       = date.fromisoformat(ev['data']),
            ora_inizio = ev.get('ora_ini'),
            ora_fine   = ev.get('ora_fin'),
            classe     = ev.get('classe'),
            origine    = 'import_piano',
        )
        db.session.add(obj)
        db.session.flush()

        # Preset partecipanti
        for did in _preset_partecipanti(obj):
            db.session.add(AttivitaIstPartecipante(
                id_attivita=obj.id, id_docente=did, preset=True))
        count += 1

    db.session.commit()
    return count


# ── IMPORT PIANO ANNUALE DA FILE .XLSX (standard corrente) ─────────────────────

@attivita_ist_bp.route('/attivita-ist/import-xlsx', methods=['GET', 'POST'])
def import_piano_xlsx():
    """
    Importa il Piano Annuale delle Attività da un file .xlsx costruito
    secondo lo standard adottato dalla scuola (banner-giorno a piena
    larghezza, righe-slot per Consigli/GLO, righe-evento per Collegio/
    Formazione/Incontri). Flusso in due passi: anteprima poi conferma,
    per evitare importazioni accidentali.
    """
    from modules.import_piano_xlsx import parse_piano_xlsx

    if request.method == 'POST' and 'eventi_json' in request.form:
        # ── passo 2: conferma import ──
        try:
            eventi = json.loads(request.form['eventi_json'])
        except Exception:
            flash('Dati di importazione non validi. Ripeti il caricamento del file.', 'danger')
            return redirect(url_for('attivita_ist.import_piano_xlsx'))

        n_importati = 0
        n_duplicati = 0
        dipartimenti_map = {d.nome.upper(): d.id for d in Dipartimento.query.all()}

        for ev in eventi:
            data_ev = date.fromisoformat(ev['data'])
            dup = AttivitaIst.query.filter_by(
                tipo=ev['tipo'], data=data_ev, titolo=ev['titolo'],
                classe=ev.get('classe'), ora_inizio=ev.get('ora_ini')).first()
            if dup:
                n_duplicati += 1
                continue

            obj = AttivitaIst(
                tipo       = ev['tipo'],
                titolo     = ev['titolo'],
                data       = data_ev,
                ora_inizio = ev.get('ora_ini'),
                ora_fine   = ev.get('ora_fin'),
                classe     = ev.get('classe'),
                note       = ev.get('note'),
                origine    = 'import_piano',
            )
            db.session.add(obj)
            db.session.flush()

            for did in _preset_partecipanti(obj):
                db.session.add(AttivitaIstPartecipante(
                    id_attivita=obj.id, id_docente=did, preset=True))
            n_importati += 1

        db.session.commit()
        flash(f'Importati {n_importati} eventi. {n_duplicati} già presenti (saltati).', 'success')
        return redirect(url_for('attivita_ist.lista'))

    if request.method == 'POST':
        # ── passo 1: caricamento file → anteprima ──
        f = request.files.get('file_xlsx')
        if not f or not f.filename:
            flash('Nessun file selezionato.', 'warning')
            return redirect(url_for('attivita_ist.import_piano_xlsx'))

        try:
            risultato = parse_piano_xlsx(f.read())
        except Exception as e:
            flash(f'Errore nella lettura del file: {e}', 'danger')
            return redirect(url_for('attivita_ist.import_piano_xlsx'))

        eventi = risultato['eventi']
        if not eventi:
            flash('Nessun evento riconosciuto nel file. Verifica che sia nel formato standard del Piano Annuale.', 'warning')
            return redirect(url_for('attivita_ist.import_piano_xlsx'))

        conteggio_tipi = {}
        for ev in eventi:
            conteggio_tipi[ev['tipo']] = conteggio_tipi.get(ev['tipo'], 0) + 1

        return render_template('attivita_ist/import_piano_xlsx_preview.html',
            fogli=risultato['fogli'], eventi=eventi, avvisi=risultato['avvisi'],
            conteggio_tipi=conteggio_tipi, tipi=TIPI_ATTIVITA,
            eventi_json=json.dumps(eventi),
        )

    return render_template('attivita_ist/import_piano_xlsx.html')


# ── DIPARTIMENTI E MATERIE ────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/dipartimenti', methods=['GET', 'POST'])
def dipartimenti():
    dips = Dipartimento.query.order_by(Dipartimento.ordine).all()
    # Materie non ancora assegnate = quelle nel dipartimento "Non assegnato" (sigla '—')
    dip_non_ass = Dipartimento.query.filter_by(sigla='—').first()
    if dip_non_ass:
        materie_da_assegnare = (Materia.query
                                .filter_by(id_dipartimento=dip_non_ass.id)
                                .order_by(Materia.sigla).all())
    else:
        materie_da_assegnare = []
    # Filtra i dipartimenti reali (escludi "Non assegnato" dall'elenco principale)
    dips_reali = [d for d in dips if d.sigla != '—']

    # Referenti di dipartimento — a differenza di Materie/Dipartimenti
    # (catalogo stabile, non legato all'anno), IncaricaDocente è per
    # anno scolastico. Prima usava sempre get_anno_corrente() (l'anno
    # "di sistema" configurato a mano, spesso disallineato dall'anno su
    # cui si sta effettivamente lavorando — vedi Task 23) senza
    # possibilità di scegliere: ora c'è un selettore, come nelle altre
    # pagine anno-scoped, di default sull'anno con dati reali.
    from routes.impostazione_anno import _anno_default_piano
    from models.incarico import IncaricaDocente, TipoIncarico
    anno_c = request.args.get('anno', _anno_default_piano())
    anni_disponibili = sorted(
        {r.anno_scol for r in IncaricaDocente.query.all()}, reverse=True)
    if anno_c not in anni_disponibili:
        anni_disponibili.insert(0, anno_c)
    tipo_ref = TipoIncarico.query.filter_by(nome='Referente di dipartimento').first()
    referenti = {}  # {id_dipartimento: Docente}
    if tipo_ref:
        nomine = IncaricaDocente.query.filter_by(
            anno_scol=anno_c, id_tipo_incarico=tipo_ref.id).all()
        for n in nomine:
            if n.id_dipartimento:
                referenti[n.id_dipartimento] = n.docente

    return render_template('attivita_ist/dipartimenti.html',
                           dipartimenti=dips_reali,
                           tutte_materie=materie_da_assegnare,
                           referenti=referenti,
                           anno_c=anno_c,
                           anni_disponibili=anni_disponibili,
                           tipi=TIPI_ATTIVITA)


@attivita_ist_bp.route('/attivita-ist/dipartimenti/assegna-materia', methods=['POST'])
def assegna_materia_dipartimento():
    """Assegna una materia esistente a un dipartimento (cambia id_dipartimento)."""
    id_materia = request.form.get('id_materia', type=int)
    id_dip     = request.form.get('id_dipartimento', type=int)
    if id_materia and id_dip:
        m = Materia.query.get(id_materia)
        if m:
            m.id_dipartimento = id_dip
            db.session.commit()
            flash(f'Materia "{m.nome_breve or m.nome}" assegnata al dipartimento.', 'success')
    return redirect(url_for('attivita_ist.dipartimenti'))





@attivita_ist_bp.route('/attivita-ist/dipartimenti/salva', methods=['POST'])
def salva_dipartimento():
    id_d  = request.form.get('id')
    nome  = request.form['nome'].strip()
    sigla = request.form['sigla'].strip().upper()
    ordine = int(request.form.get('ordine', 0))
    if id_d:
        d = Dipartimento.query.get_or_404(int(id_d))
        d.nome = nome; d.sigla = sigla; d.ordine = ordine
    else:
        db.session.add(Dipartimento(nome=nome, sigla=sigla, ordine=ordine))
    db.session.commit()
    flash('Dipartimento salvato.', 'success')
    return redirect(url_for('attivita_ist.dipartimenti'))


@attivita_ist_bp.route('/attivita-ist/materie/salva', methods=['POST'])
def salva_materia():
    import json
    id_m      = request.form.get('id')
    nome      = request.form['nome'].strip()
    sigla     = request.form['sigla'].strip().upper()
    id_dip    = int(request.form['id_dipartimento'])
    cod_or    = request.form.get('codice_orario', '').strip() or None
    indirizzi = request.form.getlist('indirizzi')
    nome_breve = request.form.get('nome_breve', '').strip() or None
    alias      = request.form.get('alias', '').strip().upper() or None

    if id_m:
        m = Materia.query.get_or_404(int(id_m))
        m.nome=nome; m.sigla=sigla; m.id_dipartimento=id_dip
        m.codice_orario=cod_or; m.indirizzi_json=json.dumps(indirizzi)
        m.nome_breve=nome_breve; m.alias=alias
    else:
        db.session.add(Materia(nome=nome, sigla=sigla, id_dipartimento=id_dip,
                               codice_orario=cod_or,
                               indirizzi_json=json.dumps(indirizzi),
                               nome_breve=nome_breve, alias=alias))
    db.session.commit()
    flash('Materia salvata.', 'success')
    return redirect(url_for('attivita_ist.dipartimenti'))


# ── ROSTER DOCENTI-MATERIE ────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/roster', methods=['GET', 'POST'])
def assegnazioni():
    from routes.impostazione_anno import _anno_default_piano
    anno   = request.args.get('anno', _anno_default_piano())
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    materie = Materia.query.join(Dipartimento).order_by(
        Dipartimento.ordine, Materia.nome).all()
    # Assegnazioni correnti
    assegn = {(dm.id_docente, dm.id_materia)
              for dm in DocenteMateria.query.filter_by(anno_scol=anno).all()}

    if request.method == 'POST':
        # Tocca solo le righe 'manuale' (quelle dichiarate da questa
        # pagina): non cancella mai le righe 'auto', sincronizzate
        # automaticamente da Assegnazioni classi -> docenti quando si
        # inseriscono ore su una materia. Prima questo salvataggio
        # cancellava TUTTO il roster dell'anno (tutti i docenti, incluse
        # le righe 'auto') per poi ricrearlo solo dalle caselle di questa
        # pagina — un salvataggio qui avrebbe potuto silenziosamente
        # perdere dati derivati da un'altra pagina. Per togliere una
        # materia 'auto' bisogna farlo da Assegnazioni (togliendo le ore)
        # o dal passo 10 "Docenti <-> Materie", che gestisce entrambe le
        # origini esplicitamente.
        DocenteMateria.query.filter_by(anno_scol=anno, origine='manuale').delete()
        coppie = set()
        for key in request.form:
            if key.startswith('dm_'):
                _, did, mid = key.split('_')
                coppie.add((int(did), int(mid)))
        n_nuove = 0
        for did, mid in coppie:
            esiste = DocenteMateria.query.filter_by(
                id_docente=did, id_materia=mid, anno_scol=anno).first()
            if not esiste:
                db.session.add(DocenteMateria(
                    id_docente=did, id_materia=mid, anno_scol=anno,
                    origine='manuale'))
                n_nuove += 1
        db.session.commit()
        flash(f'Roster aggiornato ({len(coppie)} assegnazioni, {n_nuove} nuove).', 'success')
        return redirect(url_for('attivita_ist.assegnazioni', anno=anno))

    docenti_lista = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    return render_template('attivita_ist/roster.html',
        docenti=docenti_lista, materie=materie, assegn=assegn, anno=anno,
        dipartimenti=Dipartimento.query.order_by(Dipartimento.ordine).all())


# ── SOSTITUZIONI SCRUTINIO ────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/<int:id>/sostituzioni', methods=['GET', 'POST'])
def sostituzione_scrutinio(id):
    from models.sostituzione_scrutinio import SostituzioneScrutinio
    from models.materia import DocenteMateria, Materia
    from models.orario_docente import OrarioDocente
    from models.assenza import Assenza as AssenzaM
    evento = AttivitaIst.query.get_or_404(id)

    if evento.tipo != 'scrutinio':
        flash('Questa funzione è disponibile solo per gli scrutini.', 'warning')
        return redirect(url_for('attivita_ist.presenze', id=id))

    if request.method == 'POST':
        id_assente   = int(request.form['id_assente'])
        id_sostituto = request.form.get('id_sostituto') or None
        n_prot       = request.form.get('n_protocollo', '').strip() or None
        data_nomina  = request.form.get('data_nomina') or None
        note         = request.form.get('note', '').strip() or None

        sost = SostituzioneScrutinio.query.filter_by(
            id_attivita=id, id_assente=id_assente).first()
        if sost:
            sost.id_sostituto = int(id_sostituto) if id_sostituto else None
            sost.n_protocollo = n_prot
            sost.data_nomina  = date.fromisoformat(data_nomina) if data_nomina else None
            sost.note         = note
        else:
            db.session.add(SostituzioneScrutinio(
                id_attivita  = id,
                id_assente   = id_assente,
                id_sostituto = int(id_sostituto) if id_sostituto else None,
                n_protocollo = n_prot,
                data_nomina  = date.fromisoformat(data_nomina) if data_nomina else None,
                note         = note,
            ))
        db.session.commit()
        flash('Sostituzione registrata.', 'success')
        return redirect(url_for('attivita_ist.sostituzione_scrutinio', id=id))

    # Docenti assenti a questo scrutinio
    presenze_assenti = [p for p in evento.presenze
                        if p.stato in ('assente', 'giustificato')]

    # Classi dello scrutinio (per escludere i docenti di quella classe)
    classe_scrutinio = evento.classe  # es. '3A LSC'

    # Docenti della classe (da escludere)
    docenti_classe_ids = set()
    if classe_scrutinio:
        docenti_classe_ids = {
            s.id_docente for s in OrarioDocente.query.filter_by(
                classe=classe_scrutinio).all()
        }

    # Tutti i docenti attivi NON della classe
    tutti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    candidati_base = [d for d in tutti if d.id not in docenti_classe_ids]

    # Assenti quel giorno (non disponibili)
    assenti_giorno = {a.id_docente for a in AssenzaM.query.filter_by(data=evento.data).all()}

    # Già impegnati in un altro scrutinio contemporaneo
    altri_scrutini = AttivitaIst.query.filter(
        AttivitaIst.data == evento.data,
        AttivitaIst.tipo == 'scrutinio',
        AttivitaIst.id != id
    ).all()
    def _to_min(t):
        try:
            h, m = map(int, t.split(':'))
            return h * 60 + m
        except Exception:
            return 0

    impegnati_altri = set()
    ev_ini = _to_min(evento.ora_inizio) if evento.ora_inizio else 0
    ev_fin = _to_min(evento.ora_fine)   if evento.ora_fine   else ev_ini + 45
    for alt in altri_scrutini:
        if not alt.ora_inizio:
            continue
        alt_ini = _to_min(alt.ora_inizio)
        alt_fin = _to_min(alt.ora_fine) if alt.ora_fine else alt_ini + 45
        # Sovrapposizione reale: i due intervalli si intersecano
        if alt_ini < ev_fin and alt_fin > ev_ini:
            impegnati_altri.update(p.id_docente for p in alt.partecipanti)

    def _score_candidato(d, assente_id):
        """
        Priorità (score più basso = priorità più alta):
        1. Stessa materia dell'assente
        2. Stesso dipartimento
        3. Ha un'altra riunione prima o dopo
        4. È disponibile lo stesso giorno (non impegnato in scrutini paralleli)
        5. Generico disponibile
        """
        score = 50
        if d.id in assenti_giorno: return 999  # non disponibile
        if d.id in impegnati_altri: return 998

        # Materia dell'assente — anno scolastico dell'evento (evento.data),
        # non "oggi": uno scrutinio programmato per un anno diverso da
        # quello corrente deve confrontare le materie di quell'anno.
        anno_evento = _anno_scolastico(evento.data)
        assente_mat_ids = {dm.id_materia for dm in DocenteMateria.query.filter_by(
            id_docente=assente_id, anno_scol=anno_evento).all()}
        cand_mat_ids = {dm.id_materia for dm in DocenteMateria.query.filter_by(
            id_docente=d.id, anno_scol=anno_evento).all()}

        if assente_mat_ids & cand_mat_ids:
            score = 10  # stessa materia

        elif assente_mat_ids and cand_mat_ids:
            # Stesso dipartimento?
            assente_dips = {m.id_dipartimento for m in Materia.query.filter(
                Materia.id.in_(assente_mat_ids)).all()}
            cand_dips = {m.id_dipartimento for m in Materia.query.filter(
                Materia.id.in_(cand_mat_ids)).all()}
            if assente_dips & cand_dips:
                score = 20

        # Ha altra riunione quel giorno (vicina orariamente)
        altri_ev = AttivitaIst.query.filter(
            AttivitaIst.data == evento.data,
            AttivitaIst.id != id
        ).all()
        for ev2 in altri_ev:
            if any(p.id_docente == d.id for p in ev2.partecipanti):
                if score > 30:
                    score = 30
                break

        return score

    # Calcola score per ogni candidato rispetto a ogni assente
    sostituzioni_attuali = {s.id_assente: s for s in
                            SostituzioneScrutinio.query.filter_by(id_attivita=id).all()}

    righe = []
    for p in presenze_assenti:
        assente = p.docente
        cands_scored = sorted(
            [(d, _score_candidato(d, assente.id)) for d in candidati_base
             if d.id != assente.id and d.id not in assenti_giorno],
            key=lambda x: x[1]
        )
        sost_att = sostituzioni_attuali.get(assente.id)
        righe.append({
            'presenza': p,
            'assente': assente,
            'candidati': cands_scored[:8],
            'sostituzione': sost_att,
        })

    docenti_disponibili = [d for d in candidati_base
                           if d.id not in assenti_giorno
                           and d.id not in impegnati_altri]

    return render_template('attivita_ist/sostituzioni_scrutinio.html',
        evento=evento,
        righe=righe,
        docenti_disponibili=docenti_disponibili,
        oggi=date.today(),
    )
