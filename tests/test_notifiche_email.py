from datetime import date, timedelta

import pytest

from models import db
from models.docente import Docente
from models.supplenza import Supplenza
from models.email_uscita import EmailUscita
from modules.notifiche_email import notifica_supplenza_assegnata


def _crea(email='mario.rossi@davincichiavenna.edu.it', giorni=3):
    sost = Docente(cognome='Rossi', nome='Mario', email=email, attivo=True)
    ass = Docente(cognome='Bianchi', nome='Anna', attivo=True)
    db.session.add_all([sost, ass])
    db.session.flush()
    s = Supplenza(data=date.today() + timedelta(days=giorni), ora=3, classe='3A',
                  id_assente=ass.id, id_sostituto=sost.id, stato='assegnata')
    db.session.add(s)
    db.session.commit()
    return s


def test_off_di_default_non_scrive(app, monkeypatch):
    monkeypatch.delenv('CARONTE_EMAIL_MODE', raising=False)
    with app.app_context():
        assert notifica_supplenza_assegnata(_crea()) is None
        assert EmailUscita.query.count() == 0


def test_simulato_registra_senza_inviare(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.app_context():
        s = _crea()
        assert notifica_supplenza_assegnata(s) == 'simulata'
        e = EmailUscita.query.one()
        assert e.destinatario == 'mario.rossi@davincichiavenna.edu.it'
        assert '3A' in e.corpo and 'Bianchi' in e.corpo


def test_nessun_doppio_invio(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.app_context():
        s = _crea()
        notifica_supplenza_assegnata(s)
        assert notifica_supplenza_assegnata(s) is None
        assert EmailUscita.query.count() == 1


@pytest.mark.parametrize('email,giorni,motivo', [
    (None, 3, 'email mancante'),
    ('mario@gmail.com', 3, 'fuori dominio'),
    ('mario.rossi@davincichiavenna.edu.it', -1, 'data passata'),
])
def test_casi_saltati(app, monkeypatch, email, giorni, motivo):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.app_context():
        assert notifica_supplenza_assegnata(_crea(email, giorni)) == 'saltata'
        assert motivo in EmailUscita.query.one().dettaglio


def test_reale_non_collegato_registra_errore(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    with app.app_context():
        assert notifica_supplenza_assegnata(_crea()) == 'errore'
