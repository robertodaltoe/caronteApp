"""
Piano della Formazione — gestione corsi (Piano Annuale delle Attività,
Fase 1). Ogni corso ha un evento AttivitaIst collegato (tipo='formazione',
bucket A): le iscrizioni sono le righe AttivitaIstPartecipante di quel
evento, stessa forma già usata per gli altri eventi istituzionali — vedi
models/formazione.py per il perché.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.formazione import CorsoFormazione, MODALITA
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.docente import Docente
from datetime import date

formazione_bp = Blueprint('formazione', __name__)


def _anno_scolastico(d=None):
    d = d or date.today()
    return f'{d.year}-{d.year+1}' if d.month >= 9 else f'{d.year-1}-{d.year}'


# ── LISTA ────────────────────────────────────────────────────────────────────

@formazione_bp.route('/formazione')
def lista():
    from routes.impostazione_anno import _anno_default_piano
    anno = request.args.get('anno', _anno_default_piano())
    anni_disponibili = sorted(
        {c.anno_scol for c in CorsoFormazione.query.all()}, reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    corsi = CorsoFormazione.query.filter_by(anno_scol=anno) \
        .order_by(CorsoFormazione.data_inizio).all()
    return render_template('formazione/lista.html',
        corsi=corsi, anno=anno, anni_disponibili=anni_disponibili, modalita=MODALITA)


# ── NUOVO / MODIFICA ─────────────────────────────────────────────────────────

@formazione_bp.route('/formazione/nuovo', methods=['GET', 'POST'])
@formazione_bp.route('/formazione/<int:id>/modifica', methods=['GET', 'POST'])
def form(id=None):
    corso = CorsoFormazione.query.get_or_404(id) if id else None
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    if request.method == 'POST':
        titolo    = request.form['titolo'].strip()
        tipologia = request.form.get('tipologia', '').strip() or None
        ore       = float(request.form['ore'])
        modalita  = request.form.get('modalita', 'presenza')
        ini       = date.fromisoformat(request.form['data_inizio'])
        fin_raw   = request.form.get('data_fine', '').strip()
        fin       = date.fromisoformat(fin_raw) if fin_raw else ini
        obbl      = request.form.get('obbligatorio_tutti') == 'on'
        note      = request.form.get('note', '').strip() or None
        anno_scol = request.form.get('anno_scol', '').strip() or _anno_scolastico(ini)

        if corso:
            corso.titolo = titolo; corso.tipologia = tipologia; corso.ore = ore
            corso.modalita = modalita; corso.data_inizio = ini; corso.data_fine = fin
            corso.obbligatorio_tutti = obbl; corso.note = note
            corso.anno_scol = anno_scol
            evento = corso.attivita
            evento.titolo = titolo
            evento.data = ini
            evento.durata_min = round(ore * 60)
            evento.note = note
        else:
            evento = AttivitaIst(
                tipo='formazione', titolo=titolo, data=ini,
                durata_min=round(ore * 60), note=note, origine='manuale',
            )
            db.session.add(evento)
            db.session.flush()
            corso = CorsoFormazione(
                id_attivita=evento.id, titolo=titolo, tipologia=tipologia,
                ore=ore, modalita=modalita, data_inizio=ini, data_fine=fin,
                obbligatorio_tutti=obbl, anno_scol=anno_scol, note=note,
            )
            db.session.add(corso)
        db.session.flush()

        if obbl:
            # Aggiunge chi manca fra i docenti in servizio, senza duplicare
            # né rimuovere chi era già stato iscritto manualmente.
            from routes.attivita_ist import _non_in_servizio_per_data
            esclusi = _non_in_servizio_per_data(ini)
            attuali = {p.id_docente for p in evento.partecipanti}
            for d in docenti:
                if d.id not in esclusi and d.id not in attuali:
                    db.session.add(AttivitaIstPartecipante(
                        id_attivita=evento.id, id_docente=d.id, preset=True))

        db.session.commit()
        flash(f'Corso {"aggiornato" if id else "creato"}: {titolo}', 'success')
        return redirect(url_for('formazione.lista', anno=anno_scol))

    # Per la tendina "iscrivi un docente" filtra chi non è in servizio
    # alla data del corso (uscita già segnalata per l'anno del corso,
    # non ancora arrivato, ecc. — vedi _non_in_servizio_per_data):
    # senza questo filtro un docente con anno_scol_uscita già impostato
    # per l'anno del corso comparirebbe comunque tra i selezionabili,
    # pur restando attivo=True fino a fine dell'anno corrente. La lista
    # 'docenti' completa resta invariata per mostrare comunque chi è
    # già iscritto anche se nel frattempo è uscito (stesso principio
    # già usato per i partecipanti di AttivitaIst, non sparisce chi è
    # già stato convocato, solo segnalato altrove).
    from routes.attivita_ist import _non_in_servizio_per_data
    data_rif = corso.data_inizio if corso else date.today()
    esclusi_rif = _non_in_servizio_per_data(data_rif)
    docenti_selezionabili = [d for d in docenti if d.id not in esclusi_rif]

    iscritti_ids = {p.id_docente for p in corso.attivita.partecipanti} if corso else set()
    return render_template('formazione/form.html',
        corso=corso, docenti=docenti, docenti_selezionabili=docenti_selezionabili,
        iscritti_ids=iscritti_ids,
        modalita=MODALITA, anno_default=_anno_scolastico())


# ── ISCRIZIONI ───────────────────────────────────────────────────────────────

@formazione_bp.route('/formazione/<int:id>/iscrivi', methods=['POST'])
def iscrivi(id):
    corso = CorsoFormazione.query.get_or_404(id)
    did = int(request.form['id_docente'])
    dup = AttivitaIstPartecipante.query.filter_by(
        id_attivita=corso.id_attivita, id_docente=did).first()
    if not dup:
        db.session.add(AttivitaIstPartecipante(
            id_attivita=corso.id_attivita, id_docente=did, preset=False))
        db.session.commit()
        flash('Docente iscritto.', 'success')
    return redirect(url_for('formazione.form', id=id))


@formazione_bp.route('/formazione/<int:id>/disiscrivi', methods=['POST'])
def disiscrivi(id):
    corso = CorsoFormazione.query.get_or_404(id)
    did = int(request.form['id_docente'])
    AttivitaIstPartecipante.query.filter_by(
        id_attivita=corso.id_attivita, id_docente=did).delete()
    db.session.commit()
    flash('Docente rimosso dal corso.', 'warning')
    return redirect(url_for('formazione.form', id=id))


# ── ELIMINA ──────────────────────────────────────────────────────────────────

@formazione_bp.route('/formazione/<int:id>/elimina', methods=['POST'])
def elimina(id):
    corso = CorsoFormazione.query.get_or_404(id)
    evento = corso.attivita
    anno = corso.anno_scol
    db.session.delete(corso)
    if evento:
        db.session.delete(evento)  # cascade elimina partecipanti/presenze collegate
    db.session.commit()
    flash('Corso eliminato.', 'warning')
    return redirect(url_for('formazione.lista', anno=anno))
