"""
routes/sostituzioni.py -- pagine per avviare/concludere una sostituzione
docente (temporanea o definitiva), vedi modules/sostituzione_docente.py
per la logica.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import date as _date

from models.docente import Docente
from models.sostituzione_docente import SostituzioneDocente
from models.assenza import LABEL_INTERNE as MOTIVI_LABEL
from modules.sostituzione_docente import (
    avvia_sostituzione, termina_sostituzione, SostituzioneDocenteErrore,
)

sostituzioni_bp = Blueprint('sostituzioni', __name__)

# Solo i motivi che nella pratica corrispondono a un'assenza vera di
# lungo periodo con sostituto noto -- non ha senso qui offrire, es.,
# 'classe_libera' o 'ferie' (niente supplenza automatica, vedi
# models/assenza.py::CATEGORIE).
_MOTIVI_SOSTITUZIONE = ['malattia', 'permesso_personale', 'non_recuperabile']


def _docenti_selezionabili(data_riferimento):
    # Docenti attivi E in servizio a una data (esclude chi e' gia' uscito,
    # non ancora arrivato, in aspettativa/AP uscente...) -- stesso
    # controllo usato in tutta l'app per popolare un menu di scelta
    # docente (routes/supplenze.py::nuova, routes/dashboard.py, ecc.),
    # vedi routes/attivita_ist.py::_non_in_servizio_per_data. Prima qui si
    # usava solo Docente.attivo, che non basta: un docente 'attivo' in
    # anagrafica ma uscito a fine di un anno precedente (anno_scol_uscita)
    # compariva comunque in elenco (segnalato da Roberto, caso Alaimo).
    from routes.attivita_ist import _non_in_servizio_per_data
    esclusi = _non_in_servizio_per_data(data_riferimento)
    return [d for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
            if d.id not in esclusi]


@sostituzioni_bp.route('/sostituzioni')
def index():
    attive = (SostituzioneDocente.query.filter_by(stato='attiva')
              .order_by(SostituzioneDocente.data_inizio.desc()).all())
    concluse = (SostituzioneDocente.query.filter_by(stato='conclusa')
                .order_by(SostituzioneDocente.data_inizio.desc()).limit(30).all())
    docenti = _docenti_selezionabili(_date.today())
    return render_template('sostituzioni/index.html',
                            attive=attive, concluse=concluse, docenti=docenti)


@sostituzioni_bp.route('/sostituzioni/nuova', methods=['GET'])
def nuova():
    from models.orario_docente import OrarioDocente

    id_titolare = request.args.get('id_titolare', type=int)
    titolare = Docente.query.get(id_titolare) if id_titolare else None
    classi_titolare = []
    if titolare:
        righe = (OrarioDocente.query.filter_by(id_docente=titolare.id)
                 .filter(OrarioDocente.classe.isnot(None))
                 .filter(OrarioDocente.tipo_ora.in_(['lezione', 'compresenza']))
                 .all())
        classi_titolare = sorted({r.classe for r in righe if r.classe not in ('---', '-x-', '')})

    docenti = _docenti_selezionabili(_date.today())
    return render_template('sostituzioni/nuova.html',
                            titolare=titolare, classi_titolare=classi_titolare,
                            docenti=docenti, motivi=_MOTIVI_SOSTITUZIONE,
                            motivi_label=MOTIVI_LABEL, oggi=_date.today())


@sostituzioni_bp.route('/sostituzioni/avvia', methods=['POST'])
def avvia():
    id_titolare  = request.form.get('id_titolare', type=int)
    id_sostituto = request.form.get('id_sostituto', type=int)
    tipo         = request.form.get('tipo', '')
    data_inizio_s = request.form.get('data_inizio', '')
    data_fine_s   = request.form.get('data_fine', '')
    motivo       = request.form.get('motivo', 'malattia')
    note         = request.form.get('note', '').strip()
    classi       = request.form.getlist('classi')

    if not (id_titolare and id_sostituto and tipo and data_inizio_s):
        flash('Compila titolare, sostituto, tipo e data di inizio.', 'warning')
        return redirect(url_for('sostituzioni.index'))

    from flask import g
    creato_da = g.utente.username if getattr(g, 'utente', None) else None

    try:
        data_inizio = _date.fromisoformat(data_inizio_s)
        data_fine = _date.fromisoformat(data_fine_s) if data_fine_s else None
        risultato = avvia_sostituzione(
            id_titolare=id_titolare, id_sostituto=id_sostituto, tipo=tipo,
            data_inizio=data_inizio, data_fine=data_fine,
            classi=classi or None, motivo=motivo, note=note, creato_da=creato_da,
        )
    except SostituzioneDocenteErrore as e:
        flash(f'⚠︎ {e}', 'danger')
        return redirect(url_for('sostituzioni.index'))

    msg = (f'Sostituzione avviata: {risultato["n_slot_orario"]} ore di orario spostate')
    if risultato['n_assenze']:
        msg += (f', {risultato["n_assenze"]} giorni di assenza registrati, '
                f'{risultato["n_supplenze"]} supplenze già assegnate')
    if risultato['n_eventi_ist']:
        msg += f', {risultato["n_eventi_ist"]} riunioni istituzionali aggiornate'
    if risultato['n_cattedre_trasferite']:
        msg += f', {risultato["n_cattedre_trasferite"]} cattedre trasferite'
    msg += '.'
    flash(msg, 'success')
    return redirect(url_for('sostituzioni.index'))


@sostituzioni_bp.route('/sostituzioni/<int:id>/termina', methods=['POST'])
def termina(id):
    from flask import g
    creato_da = g.utente.username if getattr(g, 'utente', None) else None
    try:
        risultato = termina_sostituzione(id, creato_da=creato_da)
    except SostituzioneDocenteErrore as e:
        flash(f'⚠︎ {e}', 'danger')
        return redirect(url_for('sostituzioni.index'))
    flash(f'Sostituzione conclusa: {risultato["n_orario_ripristinato"]} ore di orario '
          f'ripristinate sul titolare.', 'success')
    return redirect(url_for('sostituzioni.index'))
