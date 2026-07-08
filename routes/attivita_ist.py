from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.attivita_ist import (AttivitaIst, AttivitaIstPartecipante,
                                  AttivitaIstPresenza, TIPI_ATTIVITA)
from models.materia import Dipartimento, Materia, DocenteMateria
from models.docente import Docente
from models.assenza import Assenza
from datetime import date, datetime

attivita_ist_bp = Blueprint('attivita_ist', __name__)

from config_anno import get_anno_corrente as _get_anno
ANNO_SCOL_CORRENTE = _get_anno()


def _anno_scolastico(d=None):
    d = d or date.today()
    return f'{d.year}-{d.year+1}' if d.month >= 9 else f'{d.year-1}-{d.year}'



def _preset_partecipanti(attivita):
    """Genera lista docenti attivi previsti per l'evento in base al tipo."""
    docenti_attivi = Docente.query.filter_by(attivo=True).all()
    tipo = attivita.tipo

    if tipo in ('collegio', 'incontro_famiglie', 'formazione'):
        return [d.id for d in docenti_attivi]

    if tipo in ('consiglio_classe', 'scrutinio') and attivita.classe:
        from models.orario_docente import OrarioDocente
        ids = {s.id_docente for s in OrarioDocente.query.filter_by(
            classe=attivita.classe).all()}
        return list(ids)

    if tipo in ('dipartimento', 'riunione_materia', 'riunione_referenti') \
            and attivita.id_dipartimento:
        ids = {dm.id_docente for dm in DocenteMateria.query.join(Materia).filter(
            Materia.id_dipartimento == attivita.id_dipartimento,
            DocenteMateria.anno_scol == ANNO_SCOL_CORRENTE
        ).all()}
        return list(ids)

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

    dipartimenti = Dipartimento.query.order_by(Dipartimento.ordine).all()
    return render_template('attivita_ist/lista.html',
        eventi=eventi, oggi=oggi, anno=anno,
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
    docenti_extra = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    presenze_map  = {p.id_docente: p for p in evento.presenze}
    return render_template('attivita_ist/presenze.html',
        evento=evento, presenze_map=presenze_map,
        assenze_giorno=assenze_giorno,
        docenti_extra=docenti_extra,
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


# ── DIPARTIMENTI E MATERIE ────────────────────────────────────────────────────

@attivita_ist_bp.route('/attivita-ist/dipartimenti', methods=['GET', 'POST'])
def dipartimenti():
    dips = Dipartimento.query.order_by(Dipartimento.ordine).all()
    return render_template('attivita_ist/dipartimenti.html', dipartimenti=dips,
                           tipi=TIPI_ATTIVITA)


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
    anno   = request.args.get('anno', ANNO_SCOL_CORRENTE)
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    materie = Materia.query.join(Dipartimento).order_by(
        Dipartimento.ordine, Materia.nome).all()
    # Assegnazioni correnti
    assegn = {(dm.id_docente, dm.id_materia)
              for dm in DocenteMateria.query.filter_by(anno_scol=anno).all()}

    if request.method == 'POST':
        DocenteMateria.query.filter_by(anno_scol=anno).delete()
        coppie = set()
        for key in request.form:
            if key.startswith('dm_'):
                _, did, mid = key.split('_')
                coppie.add((int(did), int(mid)))
        for did, mid in coppie:
            db.session.add(DocenteMateria(
                id_docente=did, id_materia=mid, anno_scol=anno))
        db.session.commit()
        flash(f'Roster aggiornato ({len(coppie)} assegnazioni).', 'success')
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

        # Materia dell'assente
        assente_mat_ids = {dm.id_materia for dm in DocenteMateria.query.filter_by(
            id_docente=assente_id, anno_scol=ANNO_SCOL_CORRENTE).all()}
        cand_mat_ids = {dm.id_materia for dm in DocenteMateria.query.filter_by(
            id_docente=d.id, anno_scol=ANNO_SCOL_CORRENTE).all()}

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
