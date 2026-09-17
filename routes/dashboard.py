from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.supplenza import Supplenza
from models.assenza import Assenza
from models.docente import Docente
from models.indisponibilita import Indisponibilita
from routes.agenda import _accorpa_indisponibilita
from datetime import date, datetime, timedelta
from models.attivita_ist import AttivitaIst

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def index():
    oggi = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    try:
        data_sel = date.fromisoformat(data_str)
    except ValueError:
        data_sel = oggi

    supplenze = Supplenza.query\
        .filter_by(data=data_sel)\
        .filter(Supplenza.stato != 'annullata')\
        .order_by(Supplenza.ora)\
        .all()

    assenze = Assenza.query\
        .filter_by(data=data_sel)\
        .order_by(Assenza.id_docente, Assenza.ora_inizio)\
        .all()

    indisp_raw = Indisponibilita.query\
        .filter_by(data=data_sel)\
        .order_by(Indisponibilita.id_docente, Indisponibilita.ora)\
        .all()
    indisponibilita = _accorpa_indisponibilita(indisp_raw)

    # Esclude i docenti non in servizio alla data selezionata (non ancora
    # arrivati, già usciti, o — a luglio/agosto — con contratto già
    # scaduto) dal menu "Assegna sostituto": senza questo controllo un
    # docente compariva come possibile sostituto anche prima del suo
    # anno_scol_inizio o dopo la sua uscita — stesso controllo già usato
    # da routes/attivita_ist.py::_preset_partecipanti().
    from routes.attivita_ist import _non_in_servizio_per_data
    esclusi_servizio = _non_in_servizio_per_data(data_sel)
    docenti_attivi = [d for d in Docente.query
                      .filter_by(attivo=True)
                      .order_by(Docente.cognome).all()
                      if d.id not in esclusi_servizio]

    stats = {
        'totale':    len(supplenze),
        'assegnate': sum(1 for s in supplenze if s.stato == 'assegnata'),
        'scoperte':  sum(1 for s in supplenze if s.stato == 'scoperta'),
    }

    # Attività istituzionali del giorno selezionato
    try:
        eventi_ist = AttivitaIst.query.filter_by(data=data_sel)            .order_by(AttivitaIst.ora_inizio).all()
    except Exception:
        eventi_ist = []

    # Fase di orari provvisori settimanali: se l'orario in vigore ha
    # una validità impostata e la data selezionata cade fuori, nessuna
    # supplenza automatica può esistere per quel giorno -- avvisa,
    # altrimenti l'assenza di supplenze sembra un bug.
    from models.orario_docente import validita_orario_corrente
    v_ini, v_fine = validita_orario_corrente()
    orario_non_in_vigore = bool(
        (v_ini or v_fine) and ((v_ini and data_sel < v_ini) or (v_fine and data_sel > v_fine))
    )

    return render_template('dashboard.html',
        supplenze=supplenze,
        assenze=assenze,
        indisponibilita=indisponibilita,
        docenti=docenti_attivi,
        data_sel=data_sel,
        oggi=oggi,
        domani=oggi + timedelta(days=1),
        dopodomani=oggi + timedelta(days=2),
        stats=stats,
        timedelta=timedelta,
        eventi_ist=eventi_ist,
        orario_non_in_vigore=orario_non_in_vigore,
    )
