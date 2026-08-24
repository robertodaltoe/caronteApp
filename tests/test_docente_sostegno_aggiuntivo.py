"""
Caso reale segnalato da Roberto: nel 2025-2026 Luzzi era sia ITP di
Informatica (9h) sia docente di Sostegno (9h) — l'anagrafica non
riusciva a rappresentarlo, perché "ruolo" è un solo valore
(titolare/itp/sostegno). Soluzione mirata (non un redesign a incarichi
multipli): un flag Docente.sostegno_aggiuntivo + ore dedicate, che
convive col ruolo principale invece di sostituirlo.
"""
from models import db
from tests.conftest import crea_docente


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


def test_modifica_docente_salva_sostegno_aggiuntivo(app, db_session):
    import routes.docenti as mod
    from concorrenza import versione_str
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    d = crea_docente('Luzzi', ruolo='itp')
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/docenti/{d.id}/modifica', data={
            'cognome': d.cognome, 'nome': d.nome,
            'ore_contratto': '18', 'tipo_contratto': 'TI', 'ruolo': 'itp',
            'tipo_servizio': 'full',
            'sostegno_aggiuntivo': '1', 'ore_sostegno_aggiuntivo': '9',
            'versione': versione_str(d.modificato_il),
        })
        assert r.status_code == 302

    db.session.refresh(d)
    assert d.ruolo == 'itp'  # ruolo principale invariato
    assert d.sostegno_aggiuntivo is True
    assert d.ore_sostegno_aggiuntivo == 9


def test_deselezionare_la_casella_azzera_le_ore(app, db_session):
    import routes.docenti as mod
    from concorrenza import versione_str
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    d = crea_docente('LuzziBis', ruolo='itp')
    d.sostegno_aggiuntivo = True
    d.ore_sostegno_aggiuntivo = 9
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/docenti/{d.id}/modifica', data={
            'cognome': d.cognome, 'nome': d.nome,
            'ore_contratto': '18', 'tipo_contratto': 'TI', 'ruolo': 'itp',
            'tipo_servizio': 'full',
            # 'sostegno_aggiuntivo' assente = checkbox deselezionata
            'ore_sostegno_aggiuntivo': '9',
            'versione': versione_str(d.modificato_il),
        })
        assert r.status_code == 302

    db.session.refresh(d)
    assert d.sostegno_aggiuntivo is False
    assert d.ore_sostegno_aggiuntivo is None


def test_docente_con_sostegno_aggiuntivo_compare_nel_menu_orario_sostegno(app, db_session, monkeypatch):
    """Prima di questa modifica, il menu di 'Orario sostegno' filtrava
    solo ruolo=='sostegno' — un ITP con sostegno aggiuntivo (Luzzi) non
    ci sarebbe mai comparso, impedendo di assegnargli l'orario."""
    import routes.orario_sostegno as mod
    if 'orario_sostegno' not in app.blueprints:
        app.register_blueprint(mod.orario_sostegno_bp)
    catturato = _cattura(monkeypatch, mod)

    d_itp_sos = crea_docente('LuzziTer', ruolo='itp')
    d_itp_sos.sostegno_aggiuntivo = True
    d_itp_sos.ore_sostegno_aggiuntivo = 9
    d_solo_itp = crea_docente('SoloItp', ruolo='itp')
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/orario-sostegno')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti_sostegno']}
    assert d_itp_sos.id in ids
    assert d_solo_itp.id not in ids
