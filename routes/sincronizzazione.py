from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db
from models.sync_orario import AliasDocente, LogImportazione
from models.docente import Docente
from models.orario_docente import OrarioDocente
from werkzeug.utils import secure_filename
import os, json

sync_bp = Blueprint('sync', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
ALLOWED_EXT   = {'xlsx', 'xlsm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


# ── PAGINA PRINCIPALE ────────────────────────────────────────

@sync_bp.route('/orario/globale')
def orario_globale():
    from models.orario_docente import OrarioDocente
    from models.docente import Docente
    from models.orario_sostegno import OrarioSostegno
    from collections import defaultdict

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
    giorno_sel = request.args.get('giorno', 0, type=int)

    slots_giorno = OrarioDocente.query.filter_by(giorno=giorno_sel).all()
    sostegno_giorno = OrarioSostegno.query.filter_by(giorno=giorno_sel).all()

    classi = sorted(set(
        s.classe for s in slots_giorno
        if s.classe and s.classe not in ('---','-x-','','POTENZIAMENTO')
        and s.classe[0].isdigit()
    ))
    ore_list = sorted(set(s.ora for s in slots_giorno if s.classe in classi))

    # griglia[classe][ora] = lista di slot (supporta compresenze/ITP)
    griglia = defaultdict(lambda: defaultdict(list))
    for s in slots_giorno:
        if s.classe in classi:
            griglia[s.classe][s.ora].append(s)

    # griglia_sostegno[classe][ora] = lista di slot OrarioSostegno,
    # tenuta separata (colore diverso in template, tabella diversa) —
    # il docente di sostegno non compare nel file orario importato.
    griglia_sostegno = defaultdict(lambda: defaultdict(list))
    for s in sostegno_giorno:
        if s.classe in classi:
            griglia_sostegno[s.classe][s.ora].append(s)

    doc_ids = {s.id_docente for s in slots_giorno} | {s.id_docente for s in sostegno_giorno}
    docenti_map = {d.id: d for d in Docente.query.filter(
        Docente.id.in_(doc_ids)).all()}

    giorni_con_orario = sorted(set(
        r[0] for r in OrarioDocente.query
        .with_entities(OrarioDocente.giorno).distinct().all()
        if r[0] is not None
    ))

    return render_template('orario_globale.html',
        classi=classi,
        ore_list=ore_list,
        griglia=griglia,
        griglia_sostegno=griglia_sostegno,
        docenti_map=docenti_map,
        giorno_sel=giorno_sel,
        giorni_con_orario=giorni_con_orario,
        giorni_nomi=GIORNI,
    )

@sync_bp.route('/sincronizzazione')
def index():
    logs  = LogImportazione.query.order_by(LogImportazione.data_ora.desc()).limit(10).all()
    alias = AliasDocente.query.order_by(AliasDocente.nome_file).all()
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    # File orario attuale in data/
    file_corrente = None
    for f in os.listdir(UPLOAD_FOLDER):
        if f.endswith(('.xlsx', '.xlsm')) and 'ORARIO' in f.upper():
            file_corrente = f
            break

    # Statistiche orario attuale
    slot_count = OrarioDocente.query.count()
    doc_con_orario = db.session.query(
        OrarioDocente.id_docente
    ).distinct().count()

    return render_template('sincronizzazione.html',
        logs=logs, alias=alias, docenti=docenti,
        file_corrente=file_corrente,
        slot_count=slot_count,
        doc_con_orario=doc_con_orario,
    )


# ── UPLOAD + IMPORTA ─────────────────────────────────────────
@sync_bp.route('/sincronizzazione/importa', methods=['POST'])
def importa():
    from modules.parser_orario import applica_importazione

    # Usa file caricato o quello già presente
    file_path = None

    if 'file_orario' in request.files:
        f = request.files['file_orario']
        if f and f.filename and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            f.save(file_path)

    if not file_path:
        # Cerca file già presente
        for fn in os.listdir(UPLOAD_FOLDER):
            if fn.endswith(('.xlsx', '.xlsm')) and 'ORARIO' in fn.upper():
                file_path = os.path.join(UPLOAD_FOLDER, fn)
                break

    if not file_path or not os.path.exists(file_path):
        flash('Nessun file orario trovato. Carica un file .xlsx/.xlsm.', 'error')
        return redirect(url_for('sync.index'))

    try:
        stats = applica_importazione(file_path, db.session)
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'importazione: {e}', 'error')
        return redirect(url_for('sync.index'))

    msg = (f'Orario aggiornato: {stats["slot_totali"]} slot, '
           f'{stats["docenti_nuovi"]} docenti nuovi.')

    if stats['non_riconosciuti']:
        nr = ', '.join(stats['non_riconosciuti'])
        flash(msg, 'warning')
        flash(f'⚠︎ Docenti non riconosciuti (aggiungi alias): {nr}', 'warning')
    else:
        flash(msg, 'success')

    # Le riunioni pomeridiane (Consigli di classe/scrutini) vengono
    # programmate dalle Assegnazioni, ben prima che l'orario reale sia
    # disponibile — appena l'orario arriva potrebbe smentirne qualcuna
    # (un docente coinvolto ha in realtà lezione in quell'ora). Segnala
    # subito qui, invece di scoprirlo solo per caso — richiesto da
    # Roberto. Solo le riunioni da oggi in poi: quelle passate sono
    # ormai storia, non serve segnalarle.
    from datetime import date
    from modules.verifica_orario_riunioni import trova_conflitti_orario_riunioni
    conflitti = trova_conflitti_orario_riunioni(data_da=date.today())
    if conflitti:
        flash(f'⚠︎ {len(conflitti)} conflitt{"o" if len(conflitti) == 1 else "i"} tra '
              f'l\'orario appena importato e riunioni già programmate — vedi '
              f'"Genera piano delle attività" → "Verifica conflitti orario".',
              'warning')

    return redirect(url_for('sync.index'))


# ── GESTIONE ALIAS ───────────────────────────────────────────
@sync_bp.route('/sincronizzazione/alias/nuovo', methods=['POST'])
def nuovo_alias():
    nome_file  = request.form.get('nome_file', '').strip().upper()
    id_docente = request.form.get('id_docente', type=int)

    if not nome_file or not id_docente:
        flash('Compila entrambi i campi.', 'warning')
        return redirect(url_for('sync.index'))

    esistente = AliasDocente.query.filter_by(nome_file=nome_file).first()
    if esistente:
        esistente.id_docente = id_docente
        flash(f'Alias "{nome_file}" aggiornato.', 'success')
    else:
        a = AliasDocente(nome_file=nome_file, id_docente=id_docente)
        db.session.add(a)
        flash(f'Alias "{nome_file}" creato.', 'success')

    db.session.commit()
    return redirect(url_for('sync.index'))


@sync_bp.route('/sincronizzazione/alias/<int:id>/elimina', methods=['POST'])
def elimina_alias(id):
    a = AliasDocente.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    flash(f'Alias "{a.nome_file}" eliminato.', 'warning')
    return redirect(url_for('sync.index'))
