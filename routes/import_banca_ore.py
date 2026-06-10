"""routes/import_banca_ore.py"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.docente import Docente
from models.movimento_banca_ore import MovimentoBancaOre
from modules.import_banca_ore import leggi_movimenti_file

import_bp = Blueprint('import_banca', __name__)

FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'Banca_Ore_Docenti_v3.xlsm'
)


@import_bp.route('/import/banca-ore', methods=['GET', 'POST'])
def index():
    if not os.path.exists(FILE_PATH):
        flash('File Banca_Ore_Docenti_v3.xlsm non trovato in data/.', 'error')
        return redirect(url_for('report.index'))

    # Leggi tutti i movimenti dal file
    movimenti_file = leggi_movimenti_file(FILE_PATH)

    # Costruisce mappa cognome -> id_docente
    docenti = Docente.query.filter_by(attivo=True).all()
    doc_map = {}
    for d in docenti:
        key = d.cognome.strip().upper().replace("'", "'").replace("'", "'")
        doc_map[key] = d

    # Movimenti già nel DB per rilevare doppioni
    # Chiave: (id_docente, descrizione) — univoca per settimana
    esistenti = set()
    for m in MovimentoBancaOre.query.all():
        if m.descrizione:
            esistenti.add((m.id_docente, m.descrizione))

    # Classifica ogni movimento
    da_importare = []
    non_trovati  = set()
    doppioni     = []

    for mov in movimenti_file:
        cognome_key = mov['cognome'].upper().replace("'", "'").replace("'", "'")
        doc = doc_map.get(cognome_key)

        if not doc:
            non_trovati.add(mov['cognome'])
            continue

        chiave = (doc.id, mov['descrizione'])
        if chiave in esistenti:
            doppioni.append({**mov, 'cognome': doc.cognome})
            continue

        da_importare.append({**mov, 'id_docente': doc.id, 'cognome': doc.cognome})

    if request.method == 'POST':
        sett_sel   = request.form.getlist('sett_sel')
        tipo_sel   = request.form.getlist('tipo_sel')
        sovrascrivi = request.form.get('sovrascrivi') == '1'

        eliminati = 0
        inseriti  = 0

        # Tutti i movimenti del file (inclusi doppioni) se sovrascrivi
        sorgente = (da_importare + doppioni) if sovrascrivi else da_importare

        for mov in sorgente:
            if sett_sel and str(mov['sett_n']) not in sett_sel:
                continue
            if tipo_sel and mov['tipo'] not in tipo_sel:
                continue
            if 'id_docente' not in mov:
                # Risolvi id_docente per i doppioni (già trovati sopra)
                cognome_key = mov['cognome'].upper().replace("'","'").replace("'","'")
                doc = doc_map.get(cognome_key)
                if not doc:
                    continue
                mov['id_docente'] = doc.id

            if sovrascrivi:
                # Elimina vecchio movimento con stessa descrizione
                old_mov = MovimentoBancaOre.query.filter_by(
                    id_docente  = mov['id_docente'],
                    descrizione = mov['descrizione']
                ).first()
                if old_mov:
                    db.session.delete(old_mov)
                    eliminati += 1

            # Salta se ore = 0 (dati modificati a zero nel file)
            if mov['ore'] <= 0:
                continue

            # pagamento, permessi e civica sono negativi (sottraggono dal saldo)
            TIPI_NEGATIVI = ('permesso_orario', 'civica', 'supplenza_pagamento')
            segno = -1 if mov['tipo'] in TIPI_NEGATIVI else 1
            db.session.add(MovimentoBancaOre(
                id_docente  = mov['id_docente'],
                data        = mov['data'],
                minuti      = mov['ore'] * 60 * segno,
                tipo        = mov['tipo'],
                descrizione = mov['descrizione'],
            ))
            inseriti += 1

        db.session.commit()
        if sovrascrivi:
            flash(f'Reimportati {inseriti} movimenti ({eliminati} sostituiti).', 'success')
        else:
            flash(f'Importati {inseriti} movimenti dalla banca ore.', 'success')
        return redirect(url_for('import_banca.index'))

    # Raggruppa per settimana per l'anteprima
    per_sett = {}
    for mov in da_importare:
        sn = mov['sett_n']
        per_sett.setdefault(sn, []).append(mov)

    return render_template('import_banca_ore.html',
        per_sett=dict(sorted(per_sett.items())),
        da_importare=da_importare,
        doppioni=doppioni,
        non_trovati=sorted(non_trovati),
        tipi=[
            ('supplenza_recupero', '♻ Supplenze svolte'),
            ('permesso_orario',    '📋 Permessi orari'),
            ('civica',             '📚 Ed. Civica libero'),
        ],
    )
