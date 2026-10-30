"""
Revisione dei conflitti rilevati dal sync automatico additivo
(modules/auto_sync.py). Vedi anche il banner in templates/base.html.
"""
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
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
    'docenti':               'Anagrafica docente',
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
    'email':               'Email',
    'colloqui_giorno':     'Ricevimento: giorno (0 = lunedì)',
    'colloqui_ora_inizio': 'Ricevimento: ora di inizio',
    'colloqui_ora_fine':   'Ricevimento: ora di fine',
}


@sync_conflitti_bp.route('/sync/conflitti')
def index():
    from modules.sync_conflitti_vista import prepara_conflitti
    conflitti = (SyncConflitto.query
                 .filter_by(risolto=False)
                 .order_by(SyncConflitto.rilevato_il.desc())
                 .all())
    vista = prepara_conflitti(conflitti, CAMPO_LABEL, TABELLA_LABEL)

    risolti = (SyncConflitto.query
               .filter_by(risolto=True)
               .order_by(SyncConflitto.risolto_il.desc())
               .limit(15).all())
    risolti_recenti = [
        {'titolo': v['titolo'], 'scelta': c.scelta, 'risolto_da': c.risolto_da,
         'risolto_il': c.risolto_il}
        for c, v in zip(risolti, prepara_conflitti(risolti, CAMPO_LABEL, TABELLA_LABEL))]

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
    # postazione (o la stessa, se la copia Drive era solo rimasta
    # indietro rispetto a una modifica fatta qui — vedi
    # modules/auto_sync.py::pubblica_su_drive_se_possibile) resterebbe
    # con la sua versione divergente e lo stesso conflitto
    # ricomparirebbe ad ogni giro del sync automatico.
    from modules.auto_sync import pubblica_su_drive_se_possibile
    pubblica_su_drive_se_possibile()

    flash('Conflitto risolto: ' +
          ('tenuta la versione da Drive.' if scelta == 'remoto'
           else 'tenuta la versione locale.'), 'success')
    return redirect(url_for('sync_conflitti.index'))
