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

    docenti_attivi = Docente.query\
        .filter_by(attivo=True)\
        .order_by(Docente.cognome)\
        .all()

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
    )
