"""
Fase 2 del Piano Annuale delle Attività: vista mensile
(routes/attivita_ist.py::piano_annuale) e riepilogo ore per classe/
docente (routes/attivita_ist.py::riepilogo_ore).

Il fixture 'app' leggero non ha il template_folder del progetto né i
context processor dell'app reale (vedi test_piano_attivita_personale.py
per lo stesso problema) — monkeypatch di render_template per catturare
i dati calcolati dalla route invece di renderizzare l'HTML reale.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _registra_blueprint_con_cattura(app, monkeypatch):
    from routes.attivita_ist import attivita_ist_bp
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(attivita_ist_bp)

    catturato = {}
    import routes.attivita_ist as mod

    def _finto_render(template_name, **kwargs):
        catturato['template'] = template_name
        catturato['kwargs'] = kwargs
        return '<html></html>'

    monkeypatch.setattr(mod, 'render_template', _finto_render)
    return catturato


def test_piano_annuale_raggruppa_per_mese_e_giorno(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    db.session.add_all([
        AttivitaIst(tipo='collegio', titolo='Collegio apertura',
                    data=date(2026, 9, 2), origine='manuale'),
        AttivitaIst(tipo='collegio', titolo='Collegio secondo evento stesso giorno',
                    data=date(2026, 9, 2), origine='manuale'),
        AttivitaIst(tipo='scrutinio', titolo='Scrutinio giugno',
                    data=date(2027, 6, 10), classe='5A LLI', origine='manuale'),
    ])
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/piano-annuale?anno={ANNO}')
        assert r.status_code == 200

    mesi = catturato['kwargs']['mesi']
    etichette = [e for e, _ in mesi]
    # Ordine cronologico dell'anno scolastico: settembre prima di giugno
    assert etichette.index('settembre 2026') < etichette.index('giugno 2027')

    giorni_settembre = mesi[etichette.index('settembre 2026')][1]
    eventi_2_settembre = giorni_settembre[date(2026, 9, 2)]
    assert len(eventi_2_settembre) == 2  # i due eventi dello stesso giorno raggruppati


def test_piano_annuale_anno_vuoto(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    with app.test_client() as c:
        r = c.get(f'/attivita-ist/piano-annuale?anno={ANNO}')
        assert r.status_code == 200
    assert catturato['kwargs']['mesi'] == []
    assert catturato['kwargs']['n_eventi'] == 0


def test_riepilogo_ore_per_classe_somma_consigli_e_scrutini(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    db.session.add_all([
        AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LLI', data=date(2026, 10, 1),
                    classe='3A LLI', durata_min=60, origine='manuale'),
        AttivitaIst(tipo='scrutinio', titolo='Scrutinio 3A LLI', data=date(2027, 6, 10),
                    classe='3A LLI', durata_min=90, origine='manuale'),
        AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A CAT', data=date(2026, 10, 2),
                    classe='1A CAT', durata_min=45, origine='manuale'),
    ])
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    ore_per_classe = dict(catturato['kwargs']['ore_per_classe'])
    assert ore_per_classe['3A LLI'] == 2.5   # 60+90 min
    assert ore_per_classe['1A CAT'] == 0.75  # 45 min


def test_riepilogo_ore_per_docente_confronta_col_bucket(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    d = crea_docente('Rossi', tipo_contratto='TI')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 2),
                      durata_min=120, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    righe = catturato['kwargs']['riepilogo_docenti']
    assert len(righe) == 1
    assert righe[0]['docente'].cognome == 'Rossi'
    assert righe[0]['ore_a'] == 2.0
    assert righe[0]['ore_b'] == 0.0
    assert righe[0]['eccede_a'] is False


def test_riepilogo_ore_docente_senza_eventi_non_compare(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    crea_docente('Bianchi')
    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200
    assert catturato['kwargs']['riepilogo_docenti'] == []


def test_riepilogo_ore_eccedenza_segnalata(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    d = crea_docente('Verdi', tipo_contratto='TI')
    for i in range(5):
        ev = AttivitaIst(tipo='collegio', titolo=f'Collegio {i}', data=date(2026, 9, 2 + i),
                          durata_min=600, origine='manuale')  # 10h l'uno, 50h totali > 40h
        db.session.add(ev)
        db.session.flush()
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    riga = catturato['kwargs']['riepilogo_docenti'][0]
    assert riga['ore_a'] == 50.0
    assert riga['eccede_a'] is True
