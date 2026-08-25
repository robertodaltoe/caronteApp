"""
Revisione dei conflitti rilevati dal sync automatico additivo
(modules/auto_sync.py). Vedi anche il banner in templates/base.html.
"""
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, g, current_app
from sqlalchemy import text
from datetime import datetime
from models import db
from models.sync_conflitto import SyncConflitto

sync_conflitti_bp = Blueprint('sync_conflitti', __name__)

TABELLA_LABEL = {
    'assenze':               'Assenza docente',
    'supplenze':             'Supplenza',
    'indisponibilita':       'Indisponibilità docente',
    'sostituzioni_scrutinio': 'Sostituzione scrutinio',
}

# Etichette leggibili per i nomi di colonna, usate nel confronto campo per campo
CAMPO_LABEL = {
    'motivo':         'Motivo',
    'classe_libera':  'Classe libera (nessun sostituto)',
    'note_interne':   'Note interne',
    'ora_ist_inizio': 'Inizio permesso orario',
    'ora_ist_fine':   'Fine permesso orario',
    'id_sostituto':   'Docente sostituto',
    'tipo':           'Tipo copertura',
    'stato':          'Stato',
    'origine':        'Origine',
    'note_display':   'Note (visibili nel display)',
    'n_protocollo':   'N. protocollo',
    'data_nomina':    'Data nomina',
    'note':           'Note interne',
}


def _riga_leggibile(dati_json, chiave_json):
    """Unisce chiave logica + campi salvati in un unico dict per la vista."""
    d = json.loads(dati_json) if dati_json else {}
    k = json.loads(chiave_json) if chiave_json else {}
    merged = dict(k)
    merged.update(d)
    return merged


@sync_conflitti_bp.route('/sync/conflitti')
def index():
    conflitti = (SyncConflitto.query
                 .filter_by(risolto=False)
                 .order_by(SyncConflitto.rilevato_il.desc())
                 .all())

    vista = []
    for c in conflitti:
        campi_diversi = json.loads(c.campi_diversi) if c.campi_diversi else []
        locale = _riga_leggibile(c.dati_locali, c.chiave_logica)
        remoto = _riga_leggibile(c.dati_remoti, c.chiave_logica)
        confronto = [{
            'campo': campo,
            'label': CAMPO_LABEL.get(campo, campo),
            'locale': locale.get(campo),
            'remoto': remoto.get(campo),
        } for campo in campi_diversi]
        vista.append({
            'id': c.id,
            'tabella_label': TABELLA_LABEL.get(c.tabella, c.tabella),
            'descrizione': c.descrizione,
            'rilevato_il': c.rilevato_il,
            'aggiornato_il': c.aggiornato_il,
            'confronto': confronto,
            'creato_da_locale': locale.get('creato_da'),
            'creato_da_remoto': remoto.get('creato_da'),
        })

    risolti_recenti = (SyncConflitto.query
                        .filter_by(risolto=True)
                        .order_by(SyncConflitto.risolto_il.desc())
                        .limit(15).all())

    return render_template('sync_conflitti.html',
                            conflitti=vista, risolti_recenti=risolti_recenti,
                            tabella_label=TABELLA_LABEL, campo_label=CAMPO_LABEL)


@sync_conflitti_bp.route('/sync/conflitti/<int:id>/risolvi', methods=['POST'])
def risolvi(id):
    c = SyncConflitto.query.get_or_404(id)
    scelta = request.form.get('scelta')

    if scelta not in ('locale', 'remoto'):
        flash('Scelta non valida.', 'error')
        return redirect(url_for('sync_conflitti.index'))

    if scelta == 'remoto':
        # Applica alla riga locale i valori visti su Drive per i soli
        # campi che risultavano diversi — non tocca il resto della riga.
        chiave = json.loads(c.chiave_logica)
        remoto = json.loads(c.dati_remoti)
        campi_diversi = json.loads(c.campi_diversi)

        set_clause = ', '.join(f"{campo} = :v_{campo}" for campo in campi_diversi)
        where_clause = ' AND '.join(f"{col} = :k_{col}" for col in chiave)
        valori = {f"v_{campo}": remoto.get(campo) for campo in campi_diversi}
        valori.update({f"k_{col}": val for col, val in chiave.items()})

        db.session.execute(
            text(f"UPDATE {c.tabella} SET {set_clause} WHERE {where_clause}"),
            valori)

    c.risolto = True
    c.risolto_il = datetime.utcnow()
    c.risolto_da = g.utente.username if getattr(g, 'utente', None) else None
    c.scelta = scelta
    db.session.commit()

    # Ripubblica subito su Drive la decisione presa, altrimenti l'altra
    # postazione resterebbe con la sua versione divergente e lo stesso
    # conflitto ricomparirebbe ad ogni giro del sync automatico.
    try:
        from sync_db import carica
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        carica(db_path)
    except Exception as e:
        current_app.logger.warning(f"[sync_conflitti] pubblicazione su Drive fallita: {e}")

    flash('Conflitto risolto: ' +
          ('tenuta la versione da Drive.' if scelta == 'remoto'
           else 'tenuta la versione locale.'), 'success')
    return redirect(url_for('sync_conflitti.index'))
