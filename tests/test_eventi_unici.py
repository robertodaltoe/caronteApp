"""
routes/generatore_cdc.py::eventi_unici() — Collegio, Incontro
scuola-famiglia, e il nuovo tipo "riunione_extra" (Commissione, Staff
o altro gruppo ad hoc, richiesto da Roberto: non rientra in nessun
bucket normativo, partecipanti scelti a mano invece che "tutti" o
"coordinatori").

Verifica anche che, dopo la creazione, si torni sulla stessa pagina
(non più al Piano Annuale) — stesso motivo già applicato al generatore
CdC/scrutini e a quello dipartimenti (addendum 69): Roberto crea più
eventi di seguito e vuole restare dove stava lavorando.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, TIPI_ATTIVITA, BUCKET_NO
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _registra_blueprint(app):
    import routes.generatore_cdc as mod
    if 'generatore_cdc' not in app.blueprints:
        app.register_blueprint(mod.generatore_cdc_bp)


def test_riunione_extra_e_fuori_conteggio():
    assert TIPI_ATTIVITA['riunione_extra']['bucket'] == BUCKET_NO


def test_riunione_extra_usa_solo_i_docenti_scelti_a_mano(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    d3 = crea_docente('Verdi')  # non selezionato, non deve comparire

    with app.test_client() as c:
        r = c.post('/generatore-cdc/eventi-unici', data={
            'anno_scol': ANNO, 'tipo': 'riunione_extra',
            'titolo': 'Commissione elettorale',
            'data': '2026-10-05', 'ora_inizio': '15:00', 'durata_min': '60',
            'docenti_manuali': [str(d1.id), str(d2.id)],
        })
        assert r.status_code == 302

    ev = AttivitaIst.query.filter_by(tipo='riunione_extra').first()
    assert ev is not None
    assert ev.titolo == 'Commissione elettorale'
    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert ids == {d1.id, d2.id}
    assert d3.id not in ids


def test_riunione_extra_torna_alla_stessa_pagina_non_al_piano_annuale(app, db_session):
    _registra_blueprint(app)
    with app.test_client() as c:
        r = c.post('/generatore-cdc/eventi-unici', data={
            'anno_scol': ANNO, 'tipo': 'riunione_extra',
            'titolo': 'Staff di dirigenza',
            'data': '2026-10-05', 'ora_inizio': '15:00', 'durata_min': '60',
            'docenti_manuali': [],
        })
        assert r.status_code == 302
        assert r.headers['Location'] == f'/generatore-cdc/eventi-unici?anno={ANNO}'


def test_collegio_torna_alla_stessa_pagina_non_al_piano_annuale(app, db_session):
    """Stesso comportamento anche per i tipi preesistenti (Collegio,
    Incontro scuola-famiglia), non solo per il nuovo riunione_extra."""
    _registra_blueprint(app)
    with app.test_client() as c:
        r = c.post('/generatore-cdc/eventi-unici', data={
            'anno_scol': ANNO, 'tipo': 'collegio',
            'data': '2026-10-05', 'ora_inizio': '15:00', 'durata_min': '60',
        })
        assert r.status_code == 302
        assert r.headers['Location'] == f'/generatore-cdc/eventi-unici?anno={ANNO}'
