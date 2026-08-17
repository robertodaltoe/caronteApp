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

    docenti = [d for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
               if deve_compilare_piano(d, anno)]
    piani = {p.id_docente: p for p in PianoAttivitaPersonale.query.filter_by(anno_scol=anno).all()}

    righe = []
    for d in docenti:
        p = piani.get(d.id)
        quota_a, quota_b = quota_ore_bucket(d, anno)
        ore_a, ore_b = p.ore_scelte_bucket() if p else (0.0, 0.0)
        righe.append({
            'docente': d, 'frazione': frazione_cattedra(d, anno),
            'piano': p, 'quota_a': quota_a, 'quota_b': quota_b,
            'ore_a': ore_a, 'ore_b': ore_b,
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
    return (AttivitaIst.query
            .filter(AttivitaIst.tipo.in_(_TIPI_BUCKET_AB),
                    AttivitaIst.data >= inizio_as, AttivitaIst.data <= fine_as)
            .order_by(AttivitaIst.data, AttivitaIst.ora_inizio).all())


@piano_personale_bp.route('/piano-personale/<token>')
def pubblico(token):
    p = PianoAttivitaPersonale.query.filter_by(token=token).first_or_404()
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
    if p.stato == 'bloccato':
        return redirect(url_for('piano_personale.pubblico', token=token))

    _salva_scelte(p, request.form)
    if p.stato == 'bozza':
        p.stato = 'inviato'
    p.inviato_il = datetime.utcnow()
    db.session.commit()
    flash('Piano inviato alla segreteria. Resta modificabile finché non viene confermato.', 'success')
    return redirect(url_for('piano_personale.pubblico', token=token))
