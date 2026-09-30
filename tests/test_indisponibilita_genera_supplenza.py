"""Indisponibilità che genera anche la supplenza per la classe (motivi come
gara/uscita/formazione, dove il docente non è fisicamente in aula) — vedi
routes/indisponibilita.py::nuova e la spunta "Genera supplenza" nel form."""
from datetime import date

from models import db
from models.docente import Docente
from models.orario_docente import OrarioDocente
from models.indisponibilita import Indisponibilita
from models.supplenza import Supplenza
from routes.indisponibilita import indisp_bp
from routes.dashboard import dashboard_bp


def crea_docente(cognome='ROSSI', **kw):
    d = Docente(cognome=cognome, nome='Mario', nome_display=cognome, **kw)
    db.session.add(d)
    db.session.flush()
    return d


def test_genera_supplenza_su_ore_singole(app, db_session):
    with app.app_context():
        d = crea_docente()
        db.session.add(OrarioDocente(id_docente=d.id, giorno=3, ora=1, classe='1ALSU', materia='X'))
        db.session.add(OrarioDocente(id_docente=d.id, giorno=3, ora=2, classe='1ALSU', materia='X'))
        db.session.commit()

        if 'indisponibilita' not in app.blueprints:
            app.register_blueprint(indisp_bp)
        if 'dashboard' not in app.blueprints:
            app.register_blueprint(dashboard_bp)
        c = app.test_client()
        data = '2026-10-01'  # giovedì -> giorno=3
        r = c.post('/indisponibilita/nuova', data={
            'n_righe': '1', 'id_docente[0]': str(d.id), 'tipo[0]': 'singola',
            'motivo[0]': 'gara', 'data[0]': data,
            'ore[0][]': ['1', '2'], 'genera_supplenza[0]': '1',
        })
        assert r.status_code == 302

        indisp = Indisponibilita.query.filter_by(id_docente=d.id).all()
        assert len(indisp) == 2
        assert all(i.genera_supplenza for i in indisp)

        sup = Supplenza.query.filter_by(id_assente=d.id).order_by(Supplenza.ora).all()
        assert [s.ora for s in sup] == [1, 2]
        assert all(s.classe == '1ALSU' and s.stato == 'scoperta' for s in sup)


def test_senza_spunta_non_genera_supplenza(app, db_session):
    with app.app_context():
        d = crea_docente()
        db.session.add(OrarioDocente(id_docente=d.id, giorno=3, ora=1, classe='1ALSU', materia='X'))
        db.session.commit()

        if 'indisponibilita' not in app.blueprints:
            app.register_blueprint(indisp_bp)
        if 'dashboard' not in app.blueprints:
            app.register_blueprint(dashboard_bp)
        c = app.test_client()
        r = c.post('/indisponibilita/nuova', data={
            'n_righe': '1', 'id_docente[0]': str(d.id), 'tipo[0]': 'singola',
            'motivo[0]': 'colloqui', 'data[0]': '2026-10-01',
            'ore[0][]': ['1'],
        })
        assert r.status_code == 302
        assert Indisponibilita.query.filter_by(id_docente=d.id).count() == 1
        assert Supplenza.query.filter_by(id_assente=d.id).count() == 0


def test_genera_supplenza_giornata_intera(app, db_session):
    with app.app_context():
        d = crea_docente()
        db.session.add(OrarioDocente(id_docente=d.id, giorno=3, ora=1, classe='1ALSU', materia='X'))
        db.session.add(OrarioDocente(id_docente=d.id, giorno=3, ora=5, classe='2BCAT', materia='Y'))
        db.session.commit()

        if 'indisponibilita' not in app.blueprints:
            app.register_blueprint(indisp_bp)
        if 'dashboard' not in app.blueprints:
            app.register_blueprint(dashboard_bp)
        c = app.test_client()
        r = c.post('/indisponibilita/nuova', data={
            'n_righe': '1', 'id_docente[0]': str(d.id), 'tipo[0]': 'singola',
            'motivo[0]': 'formazione', 'data[0]': '2026-10-01',
            'genera_supplenza[0]': '1',
        })
        assert r.status_code == 302
        assert Indisponibilita.query.filter_by(id_docente=d.id, ora=None).count() == 1
        sup = Supplenza.query.filter_by(id_assente=d.id).all()
        assert {s.classe for s in sup} == {'1ALSU', '2BCAT'}
