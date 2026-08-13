from config_anno import get_anno_corrente
from flask import Blueprint, render_template
from models.docente import Docente
from models.materia import Dipartimento, Materia
from datetime import date

impostazioni_bp = Blueprint('impostazioni', __name__)


@impostazioni_bp.route('/impostazioni')
def index():
    from models.piano_studi import ClasseSezione, CalcoloOrganico
    from models.classe_concorso import ClasseConcorso
    n_dip     = Dipartimento.query.count()
    n_materie = Materia.query.count()
    n_docenti = Docente.query.filter_by(attivo=True).count()
    n_ti      = Docente.query.filter_by(attivo=True, tipo_contratto='TI').count()
    # Anno con dati reali nel piano studi
    anni_piano = sorted({r.anno_scol for r in __import__('models.piano_studi',
        fromlist=['PianoStudi']).PianoStudi.query.all()}, reverse=True)
    anno_piano = anni_piano[0] if anni_piano else None
    n_sezioni_attive = ClasseSezione.query.filter_by(
        anno_scol=anno_piano, attiva=True).count() if anno_piano else 0
    n_cc_confermate = CalcoloOrganico.query.filter_by(
        anno_scol=anno_piano, confermato=True).count() if anno_piano else 0
    n_cc_tot = CalcoloOrganico.query.filter_by(
        anno_scol=anno_piano).filter(
        CalcoloOrganico.ore_totali_calcolate > 0).count() if anno_piano else 0
    return render_template('impostazioni/index.html',
        n_dip=n_dip, n_materie=n_materie, n_docenti=n_docenti, n_ti=n_ti,
        anno_piano=anno_piano, n_sezioni_attive=n_sezioni_attive,
        n_cc_confermate=n_cc_confermate, n_cc_tot=n_cc_tot,
        oggi=date.today(),
    )


@impostazioni_bp.route('/impostazioni/sospensioni', methods=['GET', 'POST'])
def sospensioni():
    from models.sospensione import SospensioneDidattica, TIPI_SOSPENSIONE
    from flask import request, flash, redirect, url_for

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            ini  = request.form.get('data_inizio', '').strip()
            fin  = request.form.get('data_fine', '').strip() or ini
            desc = request.form.get('descrizione', '').strip()
            tipo = request.form.get('tipo', 'festività_nazionale')
            if ini and desc:
                from models import db
                from routes.auth import log as auth_log
                db.session.add(SospensioneDidattica(
                    data_inizio = date.fromisoformat(ini),
                    data_fine   = date.fromisoformat(fin),
                    descrizione = desc,
                    tipo        = tipo,
                ))
                db.session.commit()
                auth_log('crea_sospensione', f'{desc} ({ini}–{fin})')
                flash('Sospensione aggiunta.', 'success')

        elif azione == 'elimina':
            from models import db
            from routes.auth import log as auth_log
            sid = int(request.form.get('id', 0))
            s = SospensioneDidattica.query.get_or_404(sid)
            _desc = f'{s.descrizione} ({s.data_inizio.isoformat()}–{s.data_fine.isoformat()})'
            db.session.delete(s)
            db.session.commit()
            auth_log('elimina_sospensione', _desc)
            flash('Sospensione eliminata.', 'warning')

        elif azione == 'modifica':
            from models import db
            from routes.auth import log as auth_log
            sid  = int(request.form.get('id', 0))
            s    = SospensioneDidattica.query.get_or_404(sid)
            ini  = request.form.get('data_inizio', '').strip()
            fin  = request.form.get('data_fine', '').strip() or ini
            desc = request.form.get('descrizione', '').strip()
            tipo = request.form.get('tipo', s.tipo)
            if ini and desc:
                s.data_inizio = date.fromisoformat(ini)
                s.data_fine   = date.fromisoformat(fin)
                s.descrizione = desc
                s.tipo        = tipo
                db.session.commit()
                auth_log('modifica_sospensione', f'{desc} ({ini}–{fin})')
                flash('Sospensione aggiornata.', 'success')

        return redirect(url_for('impostazioni.sospensioni'))

    sospensioni = SospensioneDidattica.query.order_by(
        SospensioneDidattica.data_inizio).all()

    # Avviso: se nessuna sospensione copre l'anno scolastico corrente,
    # probabilmente l'elenco non è ancora stato aggiornato per il nuovo
    # anno (il seed iniziale viene eseguito una sola volta e non si ripete
    # automaticamente ogni settembre).
    from config_anno import get_anno_corrente, intervallo_anno_scolastico
    anno_corrente = get_anno_corrente()
    inizio_anno, fine_anno = intervallo_anno_scolastico(anno_corrente)
    n_anno_corrente = SospensioneDidattica.query.filter(
        SospensioneDidattica.data_fine >= inizio_anno,
        SospensioneDidattica.data_inizio <= fine_anno).count()

    return render_template('impostazioni/sospensioni.html',
        sospensioni=sospensioni, tipi=TIPI_SOSPENSIONE, oggi=date.today(),
        anno_corrente=anno_corrente, n_anno_corrente=n_anno_corrente)


@impostazioni_bp.route('/impostazioni/periodi', methods=['GET', 'POST'])
def periodi():
    """
    Gestione centralizzata dei periodi usati da più moduli (corsi di
    recupero, prove di agosto, colloqui di rientro, e in futuro esami
    integrativi/passaggi e trasferimenti). Tutti condividono lo stesso
    modello RecuperoPeriodo, distinto per 'codice'.
    """
    from models.recupero import RecuperoPeriodo
    from flask import request, flash, redirect, url_for

    # Codici noti con etichetta leggibile e modulo di riferimento — quando
    # si aggiunge un nuovo modulo che usa un periodo, basta aggiungere una
    # riga qui, senza toccare il modello.
    CODICI_NOTI = {
        'corsi_giugno':      ('▥︎ Corsi di recupero (giugno-luglio)', 'Recupero'),
        'prove_agosto':      ('✎︎ Prove di recupero (agosto)', 'Recupero'),
        'colloqui_rientro':  ('⊕︎ Colloqui di rientro dall\'estero', 'Rientro'),
        'esami_integrativi': ('△︎ Esami integrativi (passaggi e trasferimenti)', 'Da definire'),
    }

    if request.method == 'POST':
        azione = request.form.get('azione')
        from models import db

        if azione == 'aggiungi':
            anno_scol = request.form.get('anno_scol', '').strip()
            codice    = request.form.get('codice', '').strip()
            label     = request.form.get('label', '').strip()
            ini       = request.form.get('data_inizio', '').strip()
            fin       = request.form.get('data_fine', '').strip()
            ora_ini   = request.form.get('ora_inizio', '08:00').strip()
            ora_fin   = request.form.get('ora_fine', '16:00').strip()

            if not (anno_scol and codice and label and ini and fin):
                flash('Anno, codice, etichetta e date sono obbligatori.', 'warning')
                return redirect(url_for('impostazioni.periodi'))

            esiste = RecuperoPeriodo.query.filter_by(
                anno_scol=anno_scol, codice=codice).first()
            if esiste:
                flash(f'Esiste già un periodo con codice "{codice}" per l\'anno {anno_scol}: '
                      'modifica quello invece di crearne un altro.', 'warning')
                return redirect(url_for('impostazioni.periodi'))

            db.session.add(RecuperoPeriodo(
                anno_scol=anno_scol, codice=codice, label=label,
                data_inizio=date.fromisoformat(ini), data_fine=date.fromisoformat(fin),
                ora_inizio=ora_ini, ora_fine=ora_fin,
            ))
            db.session.commit()
            flash('Periodo creato.', 'success')

        elif azione == 'modifica':
            pid = int(request.form.get('id', 0))
            p = RecuperoPeriodo.query.get_or_404(pid)
            p.label       = request.form.get('label', p.label).strip()
            ini = request.form.get('data_inizio', '').strip()
            fin = request.form.get('data_fine', '').strip()
            if ini: p.data_inizio = date.fromisoformat(ini)
            if fin: p.data_fine   = date.fromisoformat(fin)
            p.ora_inizio = request.form.get('ora_inizio', p.ora_inizio).strip()
            p.ora_fine   = request.form.get('ora_fine', p.ora_fine).strip()
            db.session.commit()
            flash('Periodo aggiornato.', 'success')

        elif azione == 'elimina':
            pid = int(request.form.get('id', 0))
            p = RecuperoPeriodo.query.get_or_404(pid)
            db.session.delete(p)
            db.session.commit()
            flash('Periodo eliminato.', 'warning')

        return redirect(url_for('impostazioni.periodi'))

    righe = RecuperoPeriodo.query.order_by(
        RecuperoPeriodo.anno_scol.desc(), RecuperoPeriodo.data_inizio).all()

    return render_template('impostazioni/periodi.html',
        periodi=righe, codici_noti=CODICI_NOTI, oggi=date.today(),
        anno_corrente=get_anno_corrente())


@impostazioni_bp.route('/impostazioni/anno-scolastico')
def anno_scolastico():
    from flask import redirect, url_for
    return redirect(url_for('impostazione_anno.index'))


@impostazioni_bp.route('/impostazioni/dati-istituto', methods=['GET', 'POST'])
def dati_istituto():
    from flask import request, flash, redirect, url_for
    from config_istituto import get_dati_istituto, set_dati_istituto, DEFAULTS

    if request.method == 'POST':
        nuovi = {}
        errori = []
        for chiave, default in DEFAULTS.items():
            grezzo = request.form.get(chiave, '').strip()
            if grezzo == '':
                errori.append(chiave)
                continue
            if isinstance(default, float):
                try:
                    nuovi[chiave] = float(grezzo.replace(',', '.'))
                except ValueError:
                    errori.append(chiave)
            elif isinstance(default, int):
                try:
                    nuovi[chiave] = int(grezzo)
                except ValueError:
                    errori.append(chiave)
            else:
                nuovi[chiave] = grezzo
        if errori:
            flash(f'Valori non validi per: {", ".join(errori)}. Nessuna modifica salvata.', 'danger')
        else:
            precedenti = get_dati_istituto()
            cambiati = [f'{k}: {precedenti.get(k)} →︎ {v}' for k, v in nuovi.items()
                        if precedenti.get(k) != v]
            set_dati_istituto(nuovi)
            if cambiati:
                from routes.auth import log as auth_log
                auth_log('modifica_dati_istituto', '; '.join(cambiati))
            flash('Dati istituto aggiornati.', 'success')
        return redirect(url_for('impostazioni.dati_istituto'))

    return render_template('impostazioni/dati_istituto.html',
        dati=get_dati_istituto())


@impostazioni_bp.route('/impostazioni/backup')
def backup():
    import os, io, shutil
    from flask import send_file
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')
    buf = io.BytesIO()
    with open(db_path, 'rb') as f:
        buf.write(f.read())
    buf.seek(0)
    nome = f'caronteapp_backup_{date.today().isoformat()}.db'
    return send_file(buf, as_attachment=True, download_name=nome,
                     mimetype='application/octet-stream')


@impostazioni_bp.route('/impostazioni/permessi', methods=['GET', 'POST'])
def permessi():
    """
    Matrice permessi per ruolo — riservata al DS (letteralmente: solo
    ruolo == 'ds', non tramite ha_permesso/'tutto', così nemmeno il DSGA
    può modificarla — è una scelta esplicita, non un controllo di
    permesso normale). Vedi models/permesso_ruolo.py per il perché
    'dsga' e 'display' non compaiono in questa tabella: sono gestiti a
    parte, per non rischiare che una configurazione qui blocchi l'intera
    app o l'accesso dell'unico ruolo che può correggerla.
    """
    from flask import session, redirect, url_for, request, flash
    from models import db
    from flask import current_app
    from models.permesso_ruolo import (
        SEZIONI, SEZIONI_LABEL, RUOLI_CONFIGURABILI, LIVELLI, LIVELLI_VALIDI,
        PermessoRuolo, matrice_permessi, invalida_cache, blueprint_non_mappati,
    )

    if session.get('ruolo') != 'ds':
        flash('Questa pagina è riservata al Dirigente Scolastico.', 'error')
        return redirect(url_for('impostazioni.index'))

    if request.method == 'POST':
        righe = {(p.ruolo, p.sezione): p for p in PermessoRuolo.query.all()}
        for sezione, _ in SEZIONI:
            for ruolo, _ in RUOLI_CONFIGURABILI:
                valore = request.form.get(f'liv_{sezione}_{ruolo}')
                if valore not in LIVELLI_VALIDI:
                    continue
                riga = righe.get((ruolo, sezione))
                if riga:
                    riga.livello = valore
                else:
                    db.session.add(PermessoRuolo(ruolo=ruolo, sezione=sezione, livello=valore))
        db.session.commit()
        invalida_cache()
        from routes.auth import log as auth_log
        auth_log('modifica_permessi_ruolo', 'matrice permessi aggiornata')
        flash('Permessi aggiornati.', 'success')
        return redirect(url_for('impostazioni.permessi'))

    matrice = matrice_permessi()
    return render_template('impostazioni/permessi.html',
        sezioni=SEZIONI, sezioni_label=SEZIONI_LABEL,
        ruoli=RUOLI_CONFIGURABILI, livelli=LIVELLI, matrice=matrice,
        non_mappati=blueprint_non_mappati(current_app))
