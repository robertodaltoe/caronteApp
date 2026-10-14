"""
routes/piano_personale.py — Piano delle attività personale per i docenti
a cattedra non completa (Sessione 57).

Due pubblici distinti in questo stesso blueprint:
- Route PUBBLICHE (nessun login — vedi app.py::ROUTE_PUBBLICHE, elencate
  per nome esplicito): il docente apre il proprio link personale
  (token lungo e casuale, vedi models/piano_attivita_personale.py::
  genera_token) e sceglie gli impegni. Nessun account per i docenti in
  questa app, quindi l'unico controllo d'accesso è il token stesso —
  non deve mai comparire nei log applicativi né in URL condivise
  pubblicamente.
- Route riservate allo staff (gate normale via check_auth, sezione
  'piano_personale'): generare/rigenerare il link per un docente,
  consultare lo stato dei piani, bloccarli/sbloccarli.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db
from models.docente import Docente
from models.attivita_ist import AttivitaIst, TIPI_ATTIVITA, BUCKET_A, BUCKET_B, label_bucket
from models.piano_attivita_personale import (
    PianoAttivitaPersonale, PianoAttivitaPersonaleVoce,
    genera_token, frazione_cattedra, deve_compilare_piano, quota_ore_bucket,
)
from datetime import datetime, date

piano_personale_bp = Blueprint('piano_personale', __name__)


def _anno_scolastico(d=None):
    d = d or date.today()
    return f'{d.year}-{d.year+1}' if d.month >= 9 else f'{d.year-1}-{d.year}'


# ── STAFF ──────────────────────────────────────────────────────────────────

@piano_personale_bp.route('/attivita-ist/piano-personale')
def lista():
    from config_anno import get_anno_corrente
    from routes.docenti import _shift_anno
    # Anno OPERATIVO (get_anno_corrente), non _anno_default_piano(): il
    # Piano delle Attività da cui i docenti scelgono è quello dell'anno
    # in corso, non quello in preparazione per il successivo (i due
    # concetti vanno tenuti separati — vedi guida rapida del progetto,
    # causa ricorrente di bug in passato). Ogni anno ha le sue righe
    # PianoAttivitaPersonale (chiave unica docente+anno_scol): passare da
    # un anno all'altro non tocca né azzera i link/le scelte degli anni
    # precedenti, restano consultabili qui cambiando anno.
    anno_default = get_anno_corrente()
    anno = request.args.get('anno', anno_default)

    anni_disponibili = ({_shift_anno(anno_default, n) for n in (-1, 0, 1)} |
        {p.anno_scol for p in PianoAttivitaPersonale.query.with_entities(
            PianoAttivitaPersonale.anno_scol).distinct()} |
        {anno})
    anni_disponibili = sorted(anni_disponibili, reverse=True)

    # Esclude i docenti non in servizio in anno (non ancora arrivati,
    # già usciti) — stesso controllo di routes/attivita_ist.py::
    # _preset_partecipanti, mancava qui: un docente con anno_scol_inizio
    # futuro poteva comparire come da compilare per un anno in cui non
    # è ancora in servizio.
    from routes.attivita_ist import _non_in_servizio_per_data
    from config_anno import intervallo_anno_scolastico
    _inizio_anno, _ = intervallo_anno_scolastico(anno)
    esclusi_servizio = _non_in_servizio_per_data(_inizio_anno)
    docenti = [d for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
               if d.id not in esclusi_servizio and deve_compilare_piano(d, anno)]
    piani = {p.id_docente: p for p in PianoAttivitaPersonale.query.filter_by(anno_scol=anno).all()}

    from models.docente import tipo_contratto_label_per_anno
    righe = []
    for d in docenti:
        p = piani.get(d.id)
        quota_a, quota_b = quota_ore_bucket(d, anno)
        ore_a, ore_b = p.ore_scelte_bucket() if p else (0.0, 0.0)
        righe.append({
            'docente': d, 'frazione': frazione_cattedra(d, anno),
            'piano': p, 'quota_a': quota_a, 'quota_b': quota_b,
            'ore_a': ore_a, 'ore_b': ore_b,
            'contratto_label': tipo_contratto_label_per_anno(d, anno),
        })

    return render_template('attivita_ist/piano_personale_lista.html',
        righe=righe, anno=anno, anno_default=anno_default,
        anni_disponibili=anni_disponibili,
        tipi_a=label_bucket(BUCKET_A), tipi_b=label_bucket(BUCKET_B))


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id_docente>/genera', methods=['POST'])
def genera(id_docente):
    from config_anno import get_anno_corrente
    anno = request.form.get('anno') or get_anno_corrente()
    d = Docente.query.get_or_404(id_docente)

    p = PianoAttivitaPersonale.query.filter_by(id_docente=id_docente, anno_scol=anno).first()
    if not p:
        p = PianoAttivitaPersonale(id_docente=id_docente, anno_scol=anno, token=genera_token())
        db.session.add(p)
        db.session.commit()
        flash(f'Link personale generato per {d.cognome}.', 'success')
    else:
        flash(f'{d.cognome} ha già un piano per l\'anno {anno} — link non rigenerato.', 'warning')

    return redirect(url_for('piano_personale.lista', anno=anno))


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id_docente>/rigenera-link', methods=['POST'])
def rigenera_link(id_docente):
    """Rigenera il token (link precedente non più valido) — utile se il
    link è stato condiviso per errore o il docente lo ha perso."""
    from config_anno import get_anno_corrente
    anno = request.form.get('anno') or get_anno_corrente()
    p = PianoAttivitaPersonale.query.filter_by(id_docente=id_docente, anno_scol=anno).first_or_404()
    p.token = genera_token()
    db.session.commit()
    flash('Link rigenerato: quello precedente non è più valido.', 'success')
    return redirect(url_for('piano_personale.lista', anno=anno))


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id>/blocca', methods=['POST'])
def blocca(id):
    p = PianoAttivitaPersonale.query.get_or_404(id)
    p.stato = 'bloccato'
    p.bloccato_il = datetime.utcnow()
    p.bloccato_da = g.utente.username if getattr(g, 'utente', None) else None
    db.session.commit()
    flash(f'Piano di {p.docente.cognome} bloccato: non più modificabile dal docente.', 'success')
    return redirect(url_for('piano_personale.lista', anno=p.anno_scol))


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id>/sblocca', methods=['POST'])
def sblocca(id):
    p = PianoAttivitaPersonale.query.get_or_404(id)
    p.stato = 'inviato' if p.inviato_il else 'bozza'
    p.bloccato_il = None
    p.bloccato_da = None
    db.session.commit()
    flash(f'Piano di {p.docente.cognome} sbloccato: di nuovo modificabile dal docente.', 'success')
    return redirect(url_for('piano_personale.lista', anno=p.anno_scol))


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id>/disabilita-link', methods=['POST'])
def disabilita_link(id):
    """Disattiva il link personale — a differenza di 'blocca' (che
    impedisce solo ulteriori modifiche restando comunque apribile),
    qui il link smette del tutto di funzionare, in lettura e scrittura
    (Roberto: "poter disabilitare un link generato" — es. generato per
    errore, o docente non più tenuto a compilarlo). Le scelte già
    fatte restano salvate, pronte a riapparire se il link viene
    riabilitato."""
    p = PianoAttivitaPersonale.query.get_or_404(id)
    p.link_disabilitato = True
    db.session.commit()
    flash(f'Link di {p.docente.cognome} disattivato.', 'warning')
    return redirect(url_for('piano_personale.lista', anno=p.anno_scol))


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id>/riabilita-link', methods=['POST'])
def riabilita_link(id):
    p = PianoAttivitaPersonale.query.get_or_404(id)
    p.link_disabilitato = False
    db.session.commit()
    flash(f'Link di {p.docente.cognome} riattivato.', 'success')
    return redirect(url_for('piano_personale.lista', anno=p.anno_scol))


# ── PUBBLICO (token, nessun login) ──────────────────────────────────────────

_TIPI_BUCKET_AB = [t for t, info in TIPI_ATTIVITA.items() if info['bucket'] in (BUCKET_A, BUCKET_B)]


def _eventi_selezionabili(anno_scol):
    """Eventi del Piano delle Attività selezionabili in un piano
    personale: solo bucket A/B (collegiali, CdC, dipartimenti...) —
    gli scrutini restano sempre obbligatori per tutti, fuori da qui —
    e solo quelli dell'anno scolastico del piano (1° settembre - 31
    agosto), altrimenti eventi di altri anni resterebbero selezionabili."""
    inizio_as = date(int(anno_scol[:4]), 9, 1)
    fine_as   = date(int(anno_scol[:4]) + 1, 8, 31)
    eventi = (AttivitaIst.query
              .filter(AttivitaIst.tipo.in_(_TIPI_BUCKET_AB),
                      AttivitaIst.data >= inizio_as, AttivitaIst.data <= fine_as)
              .order_by(AttivitaIst.data, AttivitaIst.ora_inizio).all())
    return [e for e in eventi if e.bucket in (BUCKET_A, BUCKET_B)]


@piano_personale_bp.route('/piano-personale/<token>')
def pubblico(token):
    p = PianoAttivitaPersonale.query.filter_by(token=token).first_or_404()
    if p.link_disabilitato or p.link_scaduto:
        return render_template('piano_personale_disabilitato.html', docente=p.docente,
                                scaduto=p.link_scaduto and not p.link_disabilitato)
    eventi = _eventi_selezionabili(p.anno_scol)
    quota_a, quota_b = quota_ore_bucket(p.docente, p.anno_scol)
    ore_a, ore_b = p.ore_scelte_bucket()
    return render_template('piano_personale_pubblico.html',
        piano=p, docente=p.docente, eventi=eventi,
        selezionati=p.ids_attivita_scelte,
        quota_a=quota_a, quota_b=quota_b, ore_a=ore_a, ore_b=ore_b,
        frazione=frazione_cattedra(p.docente, p.anno_scol),
        BUCKET_A=BUCKET_A, BUCKET_B=BUCKET_B,
        tipi_a=label_bucket(BUCKET_A), tipi_b=label_bucket(BUCKET_B))


def _salva_scelte(p, form):
    """Sovrascrive le voci del piano con quanto selezionato nel form —
    condivisa da salva() e invia(), cosi' 'Salva e invia' non perde le
    spunte appena fatte (l'invio da solo non le salverebbe)."""
    ids_validi = {e.id for e in _eventi_selezionabili(p.anno_scol)}
    scelti = {int(v) for v in form.getlist('evento') if v.isdigit()} & ids_validi

    PianoAttivitaPersonaleVoce.query.filter_by(id_piano=p.id).delete()
    for eid in scelti:
        db.session.add(PianoAttivitaPersonaleVoce(id_piano=p.id, id_attivita=eid))

    p.note = form.get('note', '').strip() or None


@piano_personale_bp.route('/piano-personale/<token>/salva', methods=['POST'])
def salva(token):
    p = PianoAttivitaPersonale.query.filter_by(token=token).first_or_404()
    if p.link_disabilitato or p.link_scaduto:
        return render_template('piano_personale_disabilitato.html', docente=p.docente,
                                scaduto=p.link_scaduto and not p.link_disabilitato)
    if p.stato == 'bloccato':
        flash('Il piano è stato confermato dalla segreteria e non è più modificabile — '
              'per una modifica contattaci direttamente.', 'error')
        return redirect(url_for('piano_personale.pubblico', token=token))

    _salva_scelte(p, request.form)
    db.session.commit()
    flash('Scelte salvate.', 'success')
    return redirect(url_for('piano_personale.pubblico', token=token))


@piano_personale_bp.route('/piano-personale/<token>/invia', methods=['POST'])
def invia(token):
    p = PianoAttivitaPersonale.query.filter_by(token=token).first_or_404()
    if p.link_disabilitato or p.link_scaduto:
        return render_template('piano_personale_disabilitato.html', docente=p.docente,
                                scaduto=p.link_scaduto and not p.link_disabilitato)
    if p.stato == 'bloccato':
        return redirect(url_for('piano_personale.pubblico', token=token))

    _salva_scelte(p, request.form)
    if p.stato == 'bozza':
        p.stato = 'inviato'
    p.inviato_il = datetime.utcnow()
    db.session.commit()
    flash('Piano inviato alla segreteria. Resta modificabile finché non viene confermato.', 'success')
    return redirect(url_for('piano_personale.pubblico', token=token))


# ── SCHEDE EXCEL (per chi non può usare il link da fuori scuola) ────────────

def _scheda_docente(d, anno):
    p = PianoAttivitaPersonale.query.filter_by(id_docente=d.id, anno_scol=anno).first()
    sel = p.ids_attivita_scelte if p else set()
    qa, qb = quota_ore_bucket(d, anno)
    return (d, _eventi_selezionabili(anno), sel, qa, qb)


@piano_personale_bp.route('/attivita-ist/piano-personale/<int:id_docente>/scheda.xlsx')
def scheda_xlsx(id_docente):
    import io
    from flask import send_file
    from config_anno import get_anno_corrente
    from modules.piano_personale_xlsx import genera_xlsx, nome_file_scheda
    anno = request.args.get('anno') or get_anno_corrente()
    d = Docente.query.get_or_404(id_docente)
    buf = io.BytesIO()
    genera_xlsx([_scheda_docente(d, anno)], anno).save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=nome_file_scheda(d, anno),
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@piano_personale_bp.route('/attivita-ist/piano-personale/schede.zip')
def schede_zip():
    """Una scheda per ogni docente elencato in lista() per l'anno."""
    import io, zipfile
    from flask import send_file
    from config_anno import get_anno_corrente, intervallo_anno_scolastico
    from routes.attivita_ist import _non_in_servizio_per_data
    from modules.piano_personale_xlsx import genera_xlsx, nome_file_scheda
    anno = request.args.get('anno') or get_anno_corrente()
    esclusi = _non_in_servizio_per_data(intervallo_anno_scolastico(anno)[0])
    docenti = [d for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
               if d.id not in esclusi and deve_compilare_piano(d, anno)]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for d in docenti:
            f = io.BytesIO()
            genera_xlsx([_scheda_docente(d, anno)], anno).save(f)
            z.writestr(nome_file_scheda(d, anno), f.getvalue())
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f'schede_piano_attivita_{anno}.zip',
                     mimetype='application/zip')


def _analizza_scheda(s):
    """Confronta una scheda letta dal file con lo stato attuale in Caronte.
    Ritorna dict per l'anteprima (anche con 'errore')."""
    d = db.session.get(Docente, s['id_docente'])
    if not d:
        return {'errore': f'Docente id {s["id_docente"]} non trovato', 'id_docente': s['id_docente']}
    anno = s['anno_scol']
    validi = {e.id: e for e in _eventi_selezionabili(anno)}
    scelti = s['scelti'] & set(validi)
    sconosciuti = len(s['scelti'] - set(validi))
    nuovi_eventi = len(set(validi) - s['id_presenti'])
    p = PianoAttivitaPersonale.query.filter_by(id_docente=d.id, anno_scol=anno).first()
    attuali = p.ids_attivita_scelte if p else set()
    ore_a = sum(validi[i].durata_ore for i in scelti if validi[i].bucket == BUCKET_A)
    ore_b = sum(validi[i].durata_ore for i in scelti if validi[i].bucket == BUCKET_B)
    qa, qb = quota_ore_bucket(d, anno)
    avvisi = []
    if p and (p.stato == 'bloccato'):
        avvisi.append('Piano BLOCCATO: verrà aggiornato solo se spunti la conferma')
    if p and p.link_disabilitato:
        avvisi.append('Il link del docente è disabilitato (le scelte si salvano comunque)')
    if sconosciuti:
        avvisi.append(f'{sconosciuti} impegni scelti non esistono più nel piano e vengono ignorati')
    if nuovi_eventi:
        avvisi.append(f'{nuovi_eventi} eventi creati dopo l\'esportazione non erano nella scheda')
    if ore_a > qa + 0.01 or ore_b > qb + 0.01:
        avvisi.append('Ore scelte oltre la quota')
    elif ore_a < qa - 0.01 or ore_b < qb - 0.01:
        avvisi.append('Ore scelte sotto la quota')
    return {'docente': d, 'anno': anno, 'scelti': sorted(scelti), 'n_scelti': len(scelti),
            'ore_a': round(ore_a, 2), 'ore_b': round(ore_b, 2), 'quota_a': qa, 'quota_b': qb,
            'aggiunti': len(scelti - attuali), 'tolti': len(attuali - scelti),
            'ha_scelte_attuali': bool(attuali), 'bloccato': bool(p and p.stato == 'bloccato'),
            'avvisi': avvisi, 'errore': None}


@piano_personale_bp.route('/attivita-ist/piano-personale/importa', methods=['GET', 'POST'])
def importa_schede():
    from modules.piano_personale_xlsx import leggi_xlsx
    if request.method == 'GET':
        return render_template('attivita_ist/piano_personale_importa.html', anteprima=None)

    anteprima, errori = [], []
    for f in request.files.getlist('file'):
        if not f or not f.filename:
            continue
        try:
            for s in leggi_xlsx(f):
                a = _analizza_scheda(s)
                a['file'] = f.filename
                (errori if a['errore'] else anteprima).append(a)
        except ValueError as e:
            errori.append({'file': f.filename, 'errore': str(e)})
    return render_template('attivita_ist/piano_personale_importa.html',
                           anteprima=anteprima, errori=errori)


@piano_personale_bp.route('/attivita-ist/piano-personale/importa/conferma', methods=['POST'])
def importa_conferma():
    """Applica le schede mostrate in anteprima. Ogni scheda arriva come
    campo 'scheda' = 'id_docente|anno|id1,id2,...'; si rivalidano gli id
    sugli eventi attuali."""
    applicate = saltate = 0
    for raw in request.form.getlist('scheda'):
        try:
            id_doc_s, anno, ids_s = raw.split('|', 2)
            d = db.session.get(Docente, int(id_doc_s))
            ids = {int(x) for x in ids_s.split(',') if x}
        except (ValueError, TypeError):
            continue
        if not d:
            continue
        p = PianoAttivitaPersonale.query.filter_by(id_docente=d.id, anno_scol=anno).first()
        if p and p.stato == 'bloccato' and request.form.get(f'forza_{d.id}') != '1':
            saltate += 1
            continue
        if not p:
            p = PianoAttivitaPersonale(id_docente=d.id, anno_scol=anno, token=genera_token())
            db.session.add(p)
            db.session.flush()
        validi = {e.id for e in _eventi_selezionabili(anno)}
        PianoAttivitaPersonaleVoce.query.filter_by(id_piano=p.id).delete()
        for eid in ids & validi:
            db.session.add(PianoAttivitaPersonaleVoce(id_piano=p.id, id_attivita=eid))
        if p.stato == 'bozza':
            p.stato = 'inviato'
        p.inviato_il = datetime.utcnow()
        applicate += 1
    db.session.commit()
    flash(f'{applicate} piani aggiornati dalle schede Excel.'
          + (f' {saltate} piani bloccati lasciati invariati.' if saltate else ''),
          'success' if applicate else 'warning')
    return redirect(url_for('piano_personale.lista'))
