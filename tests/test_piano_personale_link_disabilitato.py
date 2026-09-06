"""
Roberto: "fai in modo che possa disabilitare un link generato per la
compilazione del piano individuale delle attività".

Diverso da 'blocca' (stato='bloccato'): quello impedisce solo
ulteriori modifiche, ma il link resta apribile e visibile dal docente.
link_disabilitato disattiva il link stesso — nessun accesso possibile,
né in lettura (pubblico()) né in scrittura (salva()/invia()) — mostra
una pagina dedicata invece del piano. Riabilitabile senza perdere le
scelte già fatte (le voci del piano non vengono toccate).
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


def _crea_piano(anno_scol='2026-2027', disabilitato=False):
    d = crea_docente('Ferri')
    d.ore_contratto = 9
    d.part_time = True
    d.ore_contratto_pt = 9
    from models.piano_attivita_personale import PianoAttivitaPersonale, genera_token
    p = PianoAttivitaPersonale(id_docente=d.id, anno_scol=anno_scol,
                                token=genera_token(), link_disabilitato=disabilitato)
    db.session.add(p)
    db.session.commit()
    return d, p


def test_link_disabilitato_mostra_pagina_dedicata_invece_del_piano(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app)  # niente monkeypatch: serve il render reale per distinguere i template
    with app.app_context():
        _, p = _crea_piano(disabilitato=True)
        token = p.token

    catturato = {}
    import routes.piano_personale as pp_mod
    def _finto_render(nome, **ctx):
        catturato['nome'] = nome
        return '<html></html>'
    monkeypatch.setattr(pp_mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/piano-personale/{token}')
        assert r.status_code == 200
        assert catturato['nome'] == 'piano_personale_disabilitato.html'


def test_link_attivo_mostra_il_piano_normale(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app)
    with app.app_context():
        _, p = _crea_piano(disabilitato=False)
        token = p.token

    catturato = {}
    import routes.piano_personale as pp_mod
    def _finto_render(nome, **ctx):
        catturato['nome'] = nome
        return '<html></html>'
    monkeypatch.setattr(pp_mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/piano-personale/{token}')
        assert r.status_code == 200
        assert catturato['nome'] == 'piano_personale_pubblico.html'


def test_link_disabilitato_rifiuta_salvataggio_anche_forzato(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    with app.app_context():
        d, p = _crea_piano(disabilitato=True)
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
        assert p.stato == 'bozza'  # invio forzato non ha avuto effetto


def test_disabilita_e_riabilita_dallo_staff(app, db_session):
    _crea_tabelle(app)
    _registra_blueprint(app)
    with app.app_context():
        _, p = _crea_piano(disabilitato=False)
        pid = p.id

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/piano-personale/{pid}/disabilita-link')
        assert r.status_code == 302

    with app.app_context():
        from models.piano_attivita_personale import PianoAttivitaPersonale
        p = PianoAttivitaPersonale.query.get(pid)
        assert p.link_disabilitato is True

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/piano-personale/{pid}/riabilita-link')
        assert r.status_code == 302

    with app.app_context():
        from models.piano_attivita_personale import PianoAttivitaPersonale
        p = PianoAttivitaPersonale.query.get(pid)
        assert p.link_disabilitato is False


def test_riabilitare_non_perde_le_scelte_gia_fatte(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    with app.app_context():
        d, p = _crea_piano(disabilitato=False)
        from models.attivita_ist import AttivitaIst
        ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 10, 10), origine='manuale')
        db.session.add(ev)
        db.session.commit()
        token, ev_id, pid = p.token, ev.id, p.id

    with app.test_client() as c:
        c.post(f'/piano-personale/{token}/salva', data={'evento': str(ev_id)})

    with app.test_client() as c:
        c.post(f'/attivita-ist/piano-personale/{pid}/disabilita-link')
        c.post(f'/attivita-ist/piano-personale/{pid}/riabilita-link')

    with app.app_context():
        from models.piano_attivita_personale import PianoAttivitaPersonale
        p = PianoAttivitaPersonale.query.get(pid)
        assert p.ids_attivita_scelte == {ev_id}
