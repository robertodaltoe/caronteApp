from datetime import date, timedelta

import pytest

from models import db
from models.docente import Docente
from models.supplenza import Supplenza
from models.email_uscita import EmailUscita
from modules import notifiche_email as ne

MAIL = 'mario.rossi@davincichiavenna.edu.it'


def _doc(cognome='Rossi', email=MAIL):
    d = Docente(cognome=cognome, nome='Mario', email=email, attivo=True)
    db.session.add(d)
    db.session.flush()
    return d


def _supp(giorno, sost, ass, ora=3, classe='3A', stato='assegnata'):
    s = Supplenza(data=giorno, ora=ora, classe=classe, id_assente=ass.id,
                  id_sostituto=sost.id if sost else None, stato=stato)
    db.session.add(s)
    db.session.commit()
    return s


def _setup(giorni=3):
    g = date.today() + timedelta(days=giorni)
    sost, ass = _doc(), _doc('Bianchi', 'a.b@davincichiavenna.edu.it')
    _supp(g, sost, ass, ora=3)
    _supp(g, sost, ass, ora=5, classe='4B')
    return g, sost, ass


def test_giorno_default_si_lavora_il_sabato():
    assert ne.giorno_default(date(2026, 10, 23)) == date(2026, 10, 24)  # ven -> sab
    assert ne.giorno_default(date(2026, 10, 24)) == date(2026, 10, 26)  # sab -> lun
    assert ne.giorno_default(date(2026, 10, 25)) == date(2026, 10, 26)  # dom -> lun
    assert ne.giorno_default(date(2026, 10, 26)) == date(2026, 10, 27)


def test_un_messaggio_per_docente_con_tutte_le_supplenze(app):
    with app.test_request_context():
        g, sost, _ = _setup()
        p = ne.proposte_supplenze(g)
        assert len(p) == 1 and p[0]['variante'] == 'nuova'
        assert '3A' in p[0]['corpo'] and '4B' in p[0]['corpo'] and 'Bianchi' in p[0]['corpo']


def test_off_non_registra(app, monkeypatch):
    monkeypatch.delenv('CARONTE_EMAIL_MODE', raising=False)
    with app.test_request_context():
        g, sost, _ = _setup()
        ne.invia_supplenze(g, [sost.id])
        assert EmailUscita.query.count() == 0


def test_simulato_poi_gia_inviata_poi_variazione_poi_annullamento(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.test_request_context():
        g, sost, ass = _setup()
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'simulata'
        assert ne.proposte_supplenze(g)[0]['variante'] == 'gia_inviata'
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'saltata'
        # nuova supplenza -> variazione
        _supp(g, sost, ass, ora=6)
        p = ne.proposte_supplenze(g)[0]
        assert p['variante'] == 'variazione' and p['oggetto'].startswith('VARIAZIONE')
        ne.invia_supplenze(g, [sost.id])
        # tutte annullate -> annullamento
        for s in Supplenza.query.all():
            s.stato = 'annullata'
        db.session.commit()
        p = ne.proposte_supplenze(g)[0]
        assert p['variante'] == 'annullamento' and p['righe'] == []


@pytest.mark.parametrize('email,motivo', [
    (None, 'email mancante'), ('x@gmail.com', 'fuori dominio')])
def test_indirizzi_non_inviabili(app, monkeypatch, email, motivo):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.test_request_context():
        g = date.today() + timedelta(days=2)
        sost, ass = _doc(email=email), _doc('Bianchi')
        _supp(g, sost, ass)
        r = ne.invia_supplenze(g, [sost.id])
        assert r[0][1] == 'saltata' and motivo in r[0][2]


def test_reale_rispetta_lista_di_prova_e_registra_errori(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    monkeypatch.setenv('CARONTE_EMAIL_SOLO_A', 'altro@davincichiavenna.edu.it')
    inviati = []
    monkeypatch.setattr('modules.gmail_invio.invia', lambda *a, **k: inviati.append(a))
    with app.test_request_context():
        g, sost, _ = _setup()
        assert ne.invia_supplenze(g, [sost.id])[0] == ('Rossi', 'saltata', 'fuori lista di prova')
        assert inviati == []
        monkeypatch.setenv('CARONTE_EMAIL_SOLO_A', MAIL)
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'inviata'
        assert inviati and inviati[0][0] == MAIL


def test_reale_errore_gmail_non_segna_come_inviata(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    def boom(*a, **k):
        raise RuntimeError('manca gmail_token.json')
    monkeypatch.setattr('modules.gmail_invio.invia', boom)
    with app.test_request_context():
        g, sost, _ = _setup()
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'errore'
        assert ne.proposte_supplenze(g)[0]['variante'] == 'nuova'  # reinviabile


def test_non_si_invia_per_giorni_passati(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.test_request_context():
        g, sost, _ = _setup(giorni=-1)
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'errore'


def test_messaggio_gmail_senza_from_e_con_destinatario():
    from modules.gmail_invio import costruisci
    m = costruisci(MAIL, 'Oggetto', 'Corpo')
    assert m['To'] == MAIL and m['From'] is None
