from models.attivita_ist import AttivitaIst, BUCKET_A, BUCKET_B, BUCKET_NO


def _b(tipo, scelta=None):
    return AttivitaIst(tipo=tipo, bucket_altro=scelta).bucket


import pytest


@pytest.fixture(autouse=True)
def _mappers(app):
    yield


def test_articolazioni_del_collegio_sono_bucket_a():
    for t in ('collegio', 'dipartimento', 'riunione_materia', 'riunione_referenti',
              'incontro_famiglie', 'formazione'):
        assert _b(t) == BUCKET_A


def test_cdc_e_glo_bucket_b_scrutini_fuori():
    assert _b('consiglio_classe') == BUCKET_B and _b('glo') == BUCKET_B
    assert _b('scrutinio') is BUCKET_NO


def test_altro_segue_la_scelta_per_evento():
    assert _b('altro', 'A') == BUCKET_A
    assert _b('altro', 'B') == BUCKET_B
    assert _b('altro', 'N') is None
    assert _b('altro') == BUCKET_A  # eventi precedenti alla scelta
