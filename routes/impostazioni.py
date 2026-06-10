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


@impostazioni_bp.route('/impostazioni/anno-scolastico')
def anno_scolastico():
    return render_template('impostazioni/stub.html',
        titolo='Anno scolastico', emoji='🗓',
        desc='Configurazione dell\'anno scolastico corrente — prossimamente.')


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
