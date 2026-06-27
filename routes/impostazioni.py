from flask import Blueprint, render_template
from models.docente import Docente
from models.materia import Dipartimento, Materia
from datetime import date

impostazioni_bp = Blueprint('impostazioni', __name__)


@impostazioni_bp.route('/impostazioni')
def index():
    # Statistiche rapide per ogni sezione
    n_dip     = Dipartimento.query.count()
    n_materie = Materia.query.count()
    n_docenti = Docente.query.filter_by(attivo=True).count()
    return render_template('impostazioni/index.html',
        n_dip=n_dip, n_materie=n_materie, n_docenti=n_docenti,
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
                db.session.add(SospensioneDidattica(
                    data_inizio = date.fromisoformat(ini),
                    data_fine   = date.fromisoformat(fin),
                    descrizione = desc,
                    tipo        = tipo,
                ))
                db.session.commit()
                flash('Sospensione aggiunta.', 'success')

        elif azione == 'elimina':
            from models import db
            sid = int(request.form.get('id', 0))
            s = SospensioneDidattica.query.get_or_404(sid)
            db.session.delete(s)
            db.session.commit()
            flash('Sospensione eliminata.', 'warning')

        elif azione == 'modifica':
            from models import db
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
                flash('Sospensione aggiornata.', 'success')

        return redirect(url_for('impostazioni.sospensioni'))

    sospensioni = SospensioneDidattica.query.order_by(
        SospensioneDidattica.data_inizio).all()
    return render_template('impostazioni/sospensioni.html',
        sospensioni=sospensioni, tipi=TIPI_SOSPENSIONE, oggi=date.today())


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
        'corsi_giugno':      ('📚 Corsi di recupero (giugno-luglio)', 'Recupero'),
        'prove_agosto':      ('📝 Prove di recupero (agosto)', 'Recupero'),
        'colloqui_rientro':  ('🌍 Colloqui di rientro dall\'estero', 'Rientro'),
        'esami_integrativi': ('🎓 Esami integrativi (passaggi e trasferimenti)', 'Da definire'),
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
        periodi=righe, codici_noti=CODICI_NOTI, oggi=date.today())


@impostazioni_bp.route('/impostazioni/anno-scolastico')
def anno_scolastico():
    from flask import redirect, url_for
    return redirect(url_for('impostazione_anno.index'))


@impostazioni_bp.route('/impostazioni/dati-istituto')
def dati_istituto():
    return render_template('impostazioni/stub.html',
        titolo='Dati istituto', emoji='🏫',
        desc='Dati istituto e costo ora supplenza — prossimamente.')


@impostazioni_bp.route('/impostazioni/cambio-anno')
def cambio_anno():
    return render_template('impostazioni/stub.html',
        titolo='Cambio anno scolastico', emoji='🔄',
        desc='Wizard di fine/inizio anno scolastico — prossimamente.')


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
