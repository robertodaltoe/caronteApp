from datetime import date, datetime, timedelta

from models import db
from models.email_uscita import EmailUscita
from modules import invio_automatico as ia
from modules import notifiche_email as ne
from tests.test_notifiche_email import _setup


def _martedi_futuro():
    """(giorno della supplenza = un martedi' futuro, 'oggi' simulato = il lunedi' prima, offset in giorni)."""
    t = date.today() + timedelta(days=7)
    while t.weekday() != 1:
        t += timedelta(days=1)
    return t, t - timedelta(days=1), (t - date.today()).days


def _inviati(monkeypatch):
    lista = []
    monkeypatch.setattr('modules.gmail_invio.invia', lambda *a, **k: lista.append(a))
    return lista


def test_spento_di_default_non_invia(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    inviati = _inviati(monkeypatch)
    with app.test_request_context():
        g, oggi, off = _martedi_futuro()
        _setup(giorni=off)
        assert ia.impostazioni() == {'attivo': False, 'ora': '15:30', 'esito': None}
        assert ia.esegui(datetime.combine(oggi, datetime.min.time()).replace(hour=16)) is None
        assert inviati == []


def test_attivo_invia_all_orario_una_volta_sola(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    inviati = _inviati(monkeypatch)
    with app.test_request_context():
        g, oggi, off = _martedi_futuro()
        _setup(giorni=off)
        ia.imposta(True, '15:30')
        assert ia.impostazioni()['ora'] == '15:30'
        assert ia.esegui(datetime.combine(oggi, datetime.min.time()).replace(hour=15, minute=29)) is None
        frase = ia.esegui(datetime.combine(oggi, datetime.min.time()).replace(hour=15, minute=31))
        assert frase and '1 inviata' in frase and len(inviati) == 1
        assert ia.esegui(datetime.combine(oggi, datetime.min.time()).replace(hour=16)) is None
        assert len(inviati) == 1 and 'concluso' in ia.impostazioni()['esito']


def test_orario_modificabile_e_non_valido_ignorato(app):
    with app.test_request_context():
        ia.imposta(True, '08:05')
        assert ia.impostazioni()['ora'] == '08:05'
        ia.imposta(True, '25:99')
        assert ia.impostazioni()['ora'] == '08:05'
        ia.imposta(False, '')
        assert ia.impostazioni()['attivo'] is False


def test_modalita_spento_non_consuma_la_giornata(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'off')
    with app.test_request_context():
        g, oggi, off = _martedi_futuro()
        _setup(giorni=off)
        ia.imposta(True, '15:30')
        assert ia.esegui(datetime.combine(oggi, datetime.min.time()).replace(hour=16)) is None
        assert ia.impostazioni()['esito'] is None


def test_errori_si_riprova_massimo_tre_volte(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')

    def rotto(*a, **k):
        raise RuntimeError('gmail giu')
    monkeypatch.setattr('modules.gmail_invio.invia', rotto)
    with app.test_request_context():
        g, oggi, off = _martedi_futuro()
        _setup(giorni=off)
        base = datetime.combine(oggi, datetime.min.time()).replace(hour=15, minute=31)
        ia.imposta(True, '15:30')
        f1 = ia.esegui(base)
        assert 'riprovo' in f1
        assert ia.esegui(base + timedelta(minutes=5)) is None           # troppo presto
        assert 'riprovo' in ia.esegui(base + timedelta(minutes=11))
        f3 = ia.esegui(base + timedelta(minutes=22))
        assert 'riprovo' not in f3 and '1 errore' in f3
        assert ia.esegui(base + timedelta(minutes=40)) is None          # concluso per oggi




def test_domenica_non_invia(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    inviati = _inviati(monkeypatch)
    with app.test_request_context():
        g, oggi, off = _martedi_futuro()
        _setup(giorni=off)
        ia.imposta(True, '15:30')
        domenica = oggi - timedelta(days=1)
        assert ia.esegui(datetime.combine(domenica, datetime.min.time()).replace(hour=16)) is None
        assert inviati == []
