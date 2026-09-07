"""
Audit usabilità (Sessione 66): docenti.modifica() non gestiva affatto
un parametro 'next' — a differenza di assenze/supplenze/indisponibilità/
cambi_quadro.modifica(), che tornano fedelmente dove si era partiti.
"Modifica docente" è raggiungibile anche da Assegnazioni e dalla Ricerca
globale (non solo dall'elenco Docenti): senza 'next', dopo il salvataggio
si veniva sempre dirottati sull'elenco completo, perdendo il contesto.
"""
from models import db
from tests.conftest import crea_docente


def _registra_blueprint(app):
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)
    return mod


def test_get_modifica_passa_next_al_template(app, db_session, monkeypatch):
    mod = _registra_blueprint(app)
    d = crea_docente('Ricci')
    db.session.commit()

    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/docenti/{d.id}/modifica?next=/assegnazioni')
        assert r.status_code == 200
    assert catturato['kwargs']['next'] == '/assegnazioni'


def test_post_modifica_con_next_torna_alla_pagina_di_provenienza(app, db_session):
    _registra_blueprint(app)
    from concorrenza import versione_str
    d = crea_docente('Bianchi')
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/docenti/{d.id}/modifica', data={
            'cognome': d.cognome, 'nome': d.nome,
            'ore_contratto': '18', 'tipo_contratto': 'TI', 'ruolo': 'titolare',
            'versione': versione_str(d.modificato_il),
            'next': '/assegnazioni?anno=2026-2027',
        })
        assert r.status_code == 302
        assert r.headers['Location'] == '/assegnazioni?anno=2026-2027'


def test_post_modifica_senza_next_torna_allelenco_come_prima(app, db_session):
    """Comportamento invariato quando non si arriva da un altro contesto
    (es. dall'elenco Docenti stesso, che non passa 'next')."""
    _registra_blueprint(app)
    from concorrenza import versione_str
    d = crea_docente('Verdi')
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/docenti/{d.id}/modifica', data={
            'cognome': d.cognome, 'nome': d.nome,
            'ore_contratto': '18', 'tipo_contratto': 'TI', 'ruolo': 'titolare',
            'versione': versione_str(d.modificato_il),
        })
        assert r.status_code == 302
        assert r.headers['Location'] == '/docenti'
