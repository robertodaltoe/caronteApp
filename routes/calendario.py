"""
Calendario degli impegni — vista giorno/settimana/mese in sola lettura
(pagina + dati JSON) ed export iCal. La logica di raccolta vive in
modules/calendario_impegni.py; qui solo parsing dei parametri e risposta.

Permessi: stessa sezione di Agenda (BLUEPRINT_SEZIONE['calendario']).
"""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, Response, abort
from models.docente import Docente
from modules.calendario_impegni import (
    FONTI, CALENDARI_ICAL, raccogli_impegni, genera_ics)

calendario_bp = Blueprint('calendario', __name__)

# Massimo intervallo servito dall'endpoint dati (la vista mese ne usa 42 giorni).
_MAX_GIORNI = 62


def _data(valore, default=None):
    try:
        return datetime.strptime(valore, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return default


def _id_docente(valore):
    try:
        return int(valore) if valore else None
    except ValueError:
        abort(400)


@calendario_bp.route('/calendario')
def index():
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome, Docente.nome).all()
    return render_template('calendario/index.html', docenti=docenti, fonti=FONTI,
                           calendari_ical=CALENDARI_ICAL,
                           id_docente=_id_docente(request.args.get('docente')),
                           oggi=date.today())


@calendario_bp.route('/calendario/dati')
def dati():
    da = _data(request.args.get('da'))
    a = _data(request.args.get('a'))
    if not da or not a or a < da or (a - da).days > _MAX_GIORNI:
        abort(400)
    id_doc = _id_docente(request.args.get('docente'))
    fonti = [f for f in request.args.get('fonti', ','.join(FONTI)).split(',') if f in FONTI]
    return jsonify(impegni=raccogli_impegni(da, a, id_docente=id_doc, fonti=fonti))


@calendario_bp.route('/calendario/ical/<cal>.ics')
def ical(cal):
    """Un calendario per tipo (piano, formazione, progetti), senza lezioni
    né assenze, sull'anno scolastico indicato (default: corrente)."""
    if cal not in CALENDARI_ICAL:
        abort(404)
    from config_anno import get_anno_corrente, intervallo_anno_scolastico
    anno = request.args.get('anno') or get_anno_corrente()
    try:
        da, a = intervallo_anno_scolastico(anno)
    except (ValueError, TypeError):
        abort(400)
    id_doc = _id_docente(request.args.get('docente'))
    nome = CALENDARI_ICAL[cal]
    if id_doc:
        doc = Docente.query.get_or_404(id_doc)
        nome += f' ({doc.cognome})'
    impegni = raccogli_impegni(da, a, id_docente=id_doc, fonti=[cal])
    testo = genera_ics(nome, impegni, datetime.utcnow())
    nome_file = f'caronte_{cal}' + (f'_{doc.cognome.lower().replace(" ", "_")}' if id_doc else '') + '.ics'
    return Response(testo, mimetype='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename="{nome_file}"'})
