"""Test 'fumo': verifica che le fixture base funzionino prima di costruire
test più complessi sopra."""
from tests.conftest import crea_docente, crea_periodo


def test_app_si_avvia(app):
    assert app is not None


def test_crea_docente(app, db_session):
    d = crea_docente('ROSSI', 'Mario', tipo_contratto='TI')
    assert d.id is not None
    assert d.cognome == 'ROSSI'


def test_crea_periodo(app, db_session):
    p = crea_periodo('prove_agosto')
    assert p.codice == 'prove_agosto'
    assert p.data_inizio.month == 8
