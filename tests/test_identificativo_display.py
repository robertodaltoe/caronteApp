"""
Test per modules/identificativo_display.py (Sessione 69 addendum 6):
iniziali uniche da mostrare sul monitor /display al posto di nomi/
cognomi interi, con la regola del DS -- estendere il cognome lettera
per lettera solo per chi condivide la sigla, finche' non sono di nuovo
distinguibili tra loro.
"""
from modules.identificativo_display import calcola_iniziali_uniche, identificativi_display
from tests.conftest import crea_docente


def test_iniziali_senza_collisioni(app, db_session):
    with app.app_context():
        a = crea_docente('Santagata', nome='Mario')
        b = crea_docente('Verdi', nome='Anna')
        mappa = calcola_iniziali_uniche([a, b])
        assert mappa[a.id] == 'S.M.'
        assert mappa[b.id] == 'V.A.'


def test_iniziali_con_collisione_estende_il_cognome(app, db_session):
    with app.app_context():
        a = crea_docente('Santagata', nome='Mario')
        # "Sartori" condivide anche "SA" con "Santagata" (SAN vs SAR):
        # la sigla si allunga finche' non divergono, non basta 1 lettera in piu'.
        b = crea_docente('Sartori', nome='Mario')
        mappa = calcola_iniziali_uniche([a, b])
        assert mappa[a.id] == 'SAN.M.'
        assert mappa[b.id] == 'SAR.M.'
        assert len({mappa[a.id], mappa[b.id]}) == 2


def test_iniziali_con_tripla_collisione(app, db_session):
    with app.app_context():
        a = crea_docente('Santagata', nome='Mario')
        b = crea_docente('Sartori', nome='Mario')
        c = crea_docente('Salvi', nome='Mario')
        mappa = calcola_iniziali_uniche([a, b, c])
        assert len({mappa[a.id], mappa[b.id], mappa[c.id]}) == 3


def test_omonimia_vera_non_va_in_loop_infinito(app, db_session):
    """Due docenti con cognome IDENTICO (fino in fondo) e stesso nome:
    restano con la stessa sigla (caso raro, serve un codice manuale),
    ma la funzione deve terminare, non entrare in un ciclo infinito."""
    with app.app_context():
        a = crea_docente('Rossi', nome='Mario')
        b = crea_docente('Rossi', nome='Mario')
        mappa = calcola_iniziali_uniche([a, b])
        assert mappa[a.id] == mappa[b.id] == 'ROSSI.M.'


def test_codice_display_ha_precedenza_sulle_iniziali(app, db_session):
    with app.app_context():
        a = crea_docente('Santagata', nome='Mario')
        a.codice_display = 'BADGE042'
        b = crea_docente('Sartori', nome='Mario')
        from models import db
        db.session.commit()

        mappa = identificativi_display([a, b])
        assert mappa[a.id] == 'BADGE042'
        # b non collide più con nessuno (a ha un codice suo): resta alla sigla base
        assert mappa[b.id] == 'S.M.'
