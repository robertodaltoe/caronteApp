"""
Audit privacy (Sessione 66 addendum 124): il link pubblico del piano
attività personale usava un token robusto (secrets.token_urlsafe(32))
ma senza nessuna scadenza automatica — un link inviato per email restava
valido a tempo indeterminato finché nessuno lo rigenerava esplicitamente.

link_scaduto (models/piano_attivita_personale.py) fa scadere il link da
solo il 1° settembre successivo al 31 agosto dell'anno_scol del piano —
stesso confine già usato ovunque nel progetto per l'anno scolastico.
Comportamento analogo a link_disabilitato: pagina dedicata invece del
piano, salvataggio/invio rifiutati anche forzando il POST.
"""
from datetime import date
from models import db
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.materia import Dipartimento, Materia, DocenteMateria  # noqa
        from models.piano_attivita_personale import PianoAttivitaPersonale, PianoAttivitaPersonaleVoce  # noqa
        from models.config_app import ConfigApp  # noqa
        db.create_all()


def _registra_blueprint(app, monkeypatch=None):
    from routes.piano_personale import piano_personale_bp
    if 'piano_personale' not in app.blueprints:
        app.register_blueprint(piano_personale_bp)
    if monkeypatch is not None:
        import routes.piano_personale as pp_mod
        monkeypatch.setattr(pp_mod, 'render_template', lambda *a, **k: '<html></html>')
    return app


def _crea_piano(anno_scol):
    d = crea_docente('Scaduti')
    d.ore_contratto = 9
    d.part_time = True
    d.ore_contratto_pt = 9
    from models.piano_attivita_personale import PianoAttivitaPersonale, genera_token
    p = PianoAttivitaPersonale(id_docente=d.id, anno_scol=anno_scol, token=genera_token())
    db.session.add(p)
    db.session.commit()
    return d, p


def test_piano_di_un_anno_scolastico_concluso_e_scaduto(app, db_session):
    _, p = _crea_piano('2015-2016')  # ampiamente concluso, qualunque sia "oggi"
    assert p.link_scaduto is True


def test_piano_dell_anno_scolastico_in_corso_o_futuro_non_e_scaduto(app, db_session):
    _, p = _crea_piano('2099-2100')  # ampiamente futuro
    assert p.link_scaduto is False


def test_link_scaduto_mostra_pagina_dedicata_invece_del_piano(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app)
    with app.app_context():
        _, p = _crea_piano('2015-2016')
        token = p.token

    catturato = {}
    import routes.piano_personale as pp_mod
    def _finto_render(nome, **ctx):
        catturato['nome'] = nome
        catturato['ctx'] = ctx
        return '<html></html>'
    monkeypatch.setattr(pp_mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/piano-personale/{token}')
        assert r.status_code == 200
        assert catturato['nome'] == 'piano_personale_disabilitato.html'
        assert catturato['ctx']['scaduto'] is True


def test_link_scaduto_rifiuta_salvataggio_anche_forzato(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    with app.app_context():
        d, p = _crea_piano('2015-2016')
        from models.attivita_ist import AttivitaIst
        ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 10, 10), origine='manuale')
        db.session.add(ev)
        db.session.commit()
        token, ev_id, pid = p.token, ev.id, p.id

    with app.test_client() as c:
        c.post(f'/piano-personale/{token}/salva', data={'evento': str(ev_id)})
        c.post(f'/piano-personale/{token}/invia', data={'evento': str(ev_id)})

    with app.app_context():
        from models.piano_attivita_personale import PianoAttivitaPersonale
        p = PianoAttivitaPersonale.query.get(pid)
        assert p.voci == []
        assert p.stato == 'bozza'
