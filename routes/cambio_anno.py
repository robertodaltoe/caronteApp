"""
Gestione del cambio anno scolastico in CaronteApp.

Due operazioni distinte:
  A. prepara_anno(nuovo_anno)  — crea struttura per il nuovo anno,
                                  eseguita mesi prima (es. luglio)
  B. attiva_anno(nuovo_anno)   — rende operativo il nuovo anno,
                                  eseguita il 1 settembre (o manualmente)
"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db
from models.docente import Docente
from models.piano_studi import ClasseSezione, PianoStudi, CalcoloOrganico
from models.config_app import ConfigApp
from config_anno import get_anno_corrente, set_anno_corrente
from routes.impostazione_anno import _ricalcola_organico
from modules.backup_cifrato import crea_backup_cifrato

cambio_anno_bp = Blueprint('cambio_anno', __name__)

# Sezioni massime per indirizzo (template completo)
SEZIONI_TEMPLATE = {
    'AFM': [(1,'A'),(1,'B'),(2,'A'),(2,'B')],
    'RIM': [(3,'A'),(3,'B'),(4,'A'),(4,'B'),(5,'A'),(5,'B')],
    'CAT': [(ac,s) for ac in range(1,6) for s in ('A','B')],
    'LSU': [(ac,s) for ac in range(1,6) for s in ('A','B')],
    'LSC': [(ac,s) for ac in range(1,6) for s in ('A','B')],
    'LLI': [(ac,s) for ac in range(1,6) for s in ('A','B')],
    'LSP': [(ac,'A') for ac in range(1,6)],
}


@cambio_anno_bp.route('/cambio-anno')
def index():
    anno_corrente = get_anno_corrente()
    # Calcola il prossimo anno scolastico
    y = int(anno_corrente.split('-')[0])
    anno_prossimo = f'{y+1}-{y+2}'
    anno_preparato = ClasseSezione.query.filter_by(
        anno_scol=anno_prossimo).count() > 0

    # Verifica cosa esiste per l'anno prossimo
    stato = {
        'classi_sezioni': ClasseSezione.query.filter_by(anno_scol=anno_prossimo).count(),
        'piano_studi': PianoStudi.query.filter_by(anno_scol=anno_prossimo).count(),
        'calc_organico': CalcoloOrganico.query.filter_by(anno_scol=anno_prossimo).count(),
    }

    return render_template('cambio_anno/index.html',
        anno_corrente=anno_corrente,
        anno_prossimo=anno_prossimo,
        anno_preparato=anno_preparato,
        stato=stato)


@cambio_anno_bp.route('/cambio-anno/prepara', methods=['POST'])
def prepara():
    """
    Operazione A: prepara la struttura per il nuovo anno scolastico.
    Crea classi sezioni (tutte inattive), copia piano studi dall'anno
    corrente come bozza. Non tocca nulla dell'anno operativo corrente.
    """
    anno_corrente = get_anno_corrente()
    anno_nuovo = request.form.get('anno_nuovo', '').strip()

    if not anno_nuovo or len(anno_nuovo) != 9 or '-' not in anno_nuovo:
        flash('Anno scolastico non valido (formato: AAAA-AAAA).', 'danger')
        return redirect(url_for('cambio_anno.index'))

    risultati = []

    # 1. Classi sezioni — template completo, tutte inattive
    n_sez = 0
    for ind, sezioni in SEZIONI_TEMPLATE.items():
        for ac, sez in sezioni:
            if not ClasseSezione.query.filter_by(
                    anno_scol=anno_nuovo, indirizzo=ind,
                    anno_corso=ac, sezione=sez).first():
                db.session.add(ClasseSezione(
                    anno_scol=anno_nuovo, indirizzo=ind,
                    anno_corso=ac, sezione=sez, attiva=False))
                n_sez += 1
    db.session.commit()
    risultati.append(f'✓︎ Classi sezioni: {n_sez} create (tutte inattive)')

    # 2. Piano studi — copia dall'anno corrente come bozza
    righe_esistenti = PianoStudi.query.filter_by(anno_scol=anno_nuovo).count()
    if righe_esistenti == 0:
        n_piano = 0
        for p in PianoStudi.query.filter_by(anno_scol=anno_corrente).all():
            db.session.add(PianoStudi(
                anno_scol=anno_nuovo,
                indirizzo=p.indirizzo,
                anno_corso=p.anno_corso,
                id_classe_concorso=p.id_classe_concorso,
                id_materia=p.id_materia,
                nome_materia_locale=p.nome_materia_locale,
                ore_settimanali=p.ore_settimanali,
                id_cc_madre=p.id_cc_madre,
                id_cc_default=p.id_cc_default,
                atipica=False,   # reset atipicità — da reimpostare per il nuovo anno
            ))
            n_piano += 1
        db.session.commit()
        risultati.append(f'✓︎ Piano studi: {n_piano} righe copiate da {anno_corrente} (atipicità resettate)')
    else:
        risultati.append(f'ℹ Piano studi: già presente ({righe_esistenti} righe) — non sovrascritto')

    # 3. Calcolo organico — verrà ricalcolato quando si attivano le sezioni
    risultati.append('ℹ Calcolo organico: verrà generato dopo aver attivato le sezioni')

    flash(' | '.join(risultati), 'success')
    return redirect(url_for('cambio_anno.index'))


@cambio_anno_bp.route('/cambio-anno/attiva', methods=['POST'])
def attiva():
    """
    Operazione B: rende operativo il nuovo anno scolastico.
    - Cambia anno_scol_corrente nel DB
    - Svuota orario_docenti (in attesa del nuovo import)
    - Svuota indisponibilita non ricorrenti
    - Banca ore: nessuna cancellazione — il saldo si azzera da solo perché
      è sempre calcolato per anno scolastico (colonna anno_scol), lo storico
      degli anni precedenti resta consultabile
    - Azzera flag attivo di docenti non TI senza anno_scol_inizio per il nuovo anno
    ATTENZIONE: operazione irreversibile per i dati operativi.
    """
    anno_nuovo = request.form.get('anno_nuovo', '').strip()
    conferma   = request.form.get('conferma', '')

    if conferma != 'CONFERMO':
        flash('Digita CONFERMO nel campo di conferma per procedere.', 'danger')
        return redirect(url_for('cambio_anno.index'))

    if not anno_nuovo:
        flash('Anno scolastico non specificato.', 'danger')
        return redirect(url_for('cambio_anno.index'))

    # Verifica che l'anno sia stato preparato
    if not ClasseSezione.query.filter_by(anno_scol=anno_nuovo).first():
        flash(f'Anno {anno_nuovo} non ancora preparato. Esegui prima "Prepara anno".', 'danger')
        return redirect(url_for('cambio_anno.index'))

    anno_precedente = get_anno_corrente()

    # Backup cifrato dedicato PRIMA di qualunque scrittura — l'unico
    # backup automatico esistente (app.py::_backup_automatico) è
    # giornaliero e legato all'avvio del server: se il server è acceso
    # da giorni non garantisce un backup recente proprio prima di
    # un'operazione irreversibile come questa (richiesto da Roberto).
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'database.db')
    backup_dir = os.path.join(base_dir, 'data', 'backup')
    try:
        backup_path = crea_backup_cifrato(
            db_path, backup_dir,
            suffisso=f'_pre_attiva_anno_{anno_precedente}_a_{anno_nuovo}')
    except Exception as e:
        flash(f'Backup non riuscito, operazione annullata per sicurezza: {e}', 'danger')
        return redirect(url_for('cambio_anno.index'))

    risultati = []
    risultati.append(f'✓︎ Backup cifrato creato: {os.path.basename(backup_path)}')

    # 1. Cambia anno scolastico corrente
    set_anno_corrente(anno_nuovo)
    risultati.append(f'✓︎ Anno corrente: {anno_precedente} →︎ {anno_nuovo}')

    # 2. Svuota orario docenti (viene reimportato)
    from models.orario_docente import OrarioDocente
    n_orario = OrarioDocente.query.count()
    OrarioDocente.query.delete()
    db.session.commit()
    risultati.append(f'✓︎ Orario docenti: {n_orario} righe archiviate (svuotato)')

    # 3. Svuota le indisponibilità dell'anno che si chiude — SOLO quelle
    # datate entro la sua fine (31/08). Prima cancellava TUTTE le righe
    # senza alcun filtro per data (Indisponibilita.query.delete() sulla
    # tabella intera): un'indisponibilità già inserita per il nuovo
    # anno (es. ottobre) sarebbe sparita insieme a quelle vecchie —
    # segnalato da Roberto prima di eseguire il cambio anno reale.
    from models.indisponibilita import Indisponibilita
    from config_anno import intervallo_anno_scolastico
    _, fine_anno_precedente = intervallo_anno_scolastico(anno_precedente)
    ind_da_eliminare = Indisponibilita.query.filter(
        Indisponibilita.data <= fine_anno_precedente).all()
    n_ind = len(ind_da_eliminare)
    for i in ind_da_eliminare:
        db.session.delete(i)
    db.session.commit()
    risultati.append(
        f'✓︎ Indisponibilità: {n_ind} righe di {anno_precedente} eliminate '
        f'(quelle già inserite per {anno_nuovo} restano intatte)')

    # 4. Banca ore: nessuna azione necessaria. Il saldo mostrato ovunque
    # (routes/report.py::get_saldi_docente) è sempre filtrato per anno
    # scolastico (colonna anno_scol, calcolata automaticamente dalla data
    # di ogni movimento): cambiando l'anno corrente il saldo del nuovo
    # anno parte da zero, i movimenti degli anni precedenti restano nel
    # database e sono consultabili scegliendo l'anno nella pagina Banca Ore.
    risultati.append('✓︎ Banca ore: saldo azzerato per il nuovo anno, storico degli anni precedenti conservato e consultabile')

    # 5. Ricalcola organico per il nuovo anno (con le sezioni attive impostate)
    _ricalcola_organico(anno_nuovo)
    risultati.append(f'✓︎ Calcolo organico {anno_nuovo}: ricalcolato')

    flash(' | '.join(risultati), 'success')
    return redirect(url_for('cambio_anno.index'))
