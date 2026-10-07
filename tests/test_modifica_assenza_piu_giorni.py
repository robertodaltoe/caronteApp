"""
Regressione: modificando un'assenza e impostandola su "Più giorni" il form
non invia 'data' (campo disabilitato) ma data_range_ini/data_range_fin;
prima modifica_assenza leggeva form["data"] → BadRequestKeyError (pagina
"Bad Request"). Ora la riga prende la prima data e le altre vengono create.
"""
from datetime import date
from flask import g
from werkzeug.datastructures import MultiDict

from models import db
from models.assenza import Assenza
from modules.assenze_registrazione import modifica_assenza
from tests.conftest import crea_docente


class _Utente:
    ruolo = 'ds'
    username = 'test'


def _setup(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()


def test_modifica_assenza_su_piu_giorni(app, db_session):
    _setup(app)
    with app.app_context():
        d = crea_docente('Rossi')
        lun = date(2027, 3, 15)  # lunedì
        a = Assenza(id_docente=d.id, data=lun, ora_inizio=1, ora_fine=2, motivo='ferie')
        db.session.add(a)
        db.session.commit()
        form = MultiDict({
            'id_docente': str(d.id),
            'data_range_ini': '2027-03-15', 'data_range_fin': '2027-03-17',
            'ora_inizio': '1', 'ora_fine': '2', 'motivo': 'ferie',
            'note_interne': 'x',
        })
        with app.test_request_context():
            g.utente = _Utente()
            r = modifica_assenza(a, form)
        db.session.commit()
        date_ass = sorted(x.data for x in Assenza.query.filter_by(id_docente=d.id))
        assert date_ass == [date(2027, 3, 15), date(2027, 3, 16), date(2027, 3, 17)]
        assert r['n_extra'] == 2


def test_modifica_assenza_singolo_giorno_invariato(app, db_session):
    _setup(app)
    with app.app_context():
        d = crea_docente('Bianchi')
        a = Assenza(id_docente=d.id, data=date(2027, 3, 15), ora_inizio=1, ora_fine=2, motivo='ferie')
        db.session.add(a)
        db.session.commit()
        form = MultiDict({'id_docente': str(d.id), 'data': '2027-03-16',
                          'ora_inizio': '1', 'ora_fine': '2', 'motivo': 'ferie'})
        with app.test_request_context():
            g.utente = _Utente()
            r = modifica_assenza(a, form)
        db.session.commit()
        assert [x.data for x in Assenza.query.filter_by(id_docente=d.id)] == [date(2027, 3, 16)]
        assert r['n_extra'] == 0
