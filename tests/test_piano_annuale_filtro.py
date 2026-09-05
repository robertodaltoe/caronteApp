"""
Roberto: "aggiungi filtro anche in piano delle attività" — Elenco/
gestione eventi aveva già i filtri tipo/mese (routes/attivita_ist.py::
lista()), Piano Annuale no. Stesso filtro riusato in
_righe_piano_annuale(anno, tipo_f, mese_f), passato solo dalla vista a
schermo — gli export PDF/xlsx restano sempre il piano ufficiale
completo, non filtrato.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst


def _crea(tipo, titolo, data):
    ev = AttivitaIst(tipo=tipo, titolo=titolo, data=data, origine='manuale')
    db.session.add(ev)
    return ev


def test_filtro_tipo(app, db_session):
    from routes.attivita_ist import _righe_piano_annuale
    _crea('scrutinio', 'Scrutinio 1A', date(2027, 1, 10))
    _crea('collegio', 'Collegio', date(2027, 1, 12))
    db.session.commit()

    mesi, _anni, n_eventi = _righe_piano_annuale('2026-2027', tipo_f='scrutinio')
    assert n_eventi == 1

    titoli = set()
    for _et, righe in mesi:
        for _data, tipo_r, contenuto in righe:
            if tipo_r == 'eventi':
                titoli |= {e.titolo for e in contenuto}
    assert titoli == {'Scrutinio 1A'}


def test_filtro_mese(app, db_session):
    from routes.attivita_ist import _righe_piano_annuale
    _crea('scrutinio', 'Scrutinio Gennaio', date(2027, 1, 10))
    _crea('scrutinio', 'Scrutinio Giugno', date(2027, 6, 10))
    db.session.commit()

    mesi, _anni, n_eventi = _righe_piano_annuale('2026-2027', mese_f='1')
    assert n_eventi == 1
    assert len(mesi) == 1
    titoli = set()
    for _et, righe in mesi:
        for _data, tipo_r, contenuto in righe:
            if tipo_r == 'eventi':
                titoli |= {e.titolo for e in contenuto}
    assert titoli == {'Scrutinio Gennaio'}


def test_senza_filtro_mostra_tutto_come_prima(app, db_session):
    from routes.attivita_ist import _righe_piano_annuale
    _crea('scrutinio', 'Scrutinio', date(2027, 1, 10))
    _crea('collegio', 'Collegio', date(2027, 6, 10))
    db.session.commit()

    mesi, _anni, n_eventi = _righe_piano_annuale('2026-2027')
    assert n_eventi == 2


def test_route_legge_filtri_dalla_query_string(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    _crea('scrutinio', 'Scrutinio Gennaio', date(2027, 1, 10))
    _crea('collegio', 'Collegio', date(2027, 1, 12))
    db.session.commit()

    catturato = {}
    def _fake_render(nome, **ctx):
        catturato['ctx'] = ctx
        return ''
    monkeypatch.setattr(mod, 'render_template', _fake_render)

    with app.test_client() as c:
        c.get('/attivita-ist/piano-annuale?anno=2026-2027&tipo=scrutinio&mese=1')

    assert catturato['ctx']['tipo_f'] == 'scrutinio'
    assert catturato['ctx']['mese_f'] == '1'
    assert catturato['ctx']['n_eventi'] == 1
