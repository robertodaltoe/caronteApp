"""
Roberto: Di Liberto (e altri neoimmessi in ruolo che iniziano il
contratto nel 2026-2027) non compariva in "Docenti per anno"
(2026-2027) pur comparendo in Anagrafica docenti.

Causa: la pagina divide i docenti in due sezioni che dovrebbero
coprirsi a vicenda — "docenti_gestione" esclude chi ha
anno_scol_inizio == anno (assumendo compaia nell'altra sezione), e la
sezione "TD/Supplenti inseriti per {{anno}}" (td_anno) escludeva
esplicitamente i TI (assumendo un TI con anno_scol_inizio == anno
fosse sempre uno storico già tracciato altrove). Un TI NEOIMMESSO che
inizia esattamente in quell'anno cadeva nel buco tra le due esclusioni
— invisibile su tutta la pagina.
"""
from models import db
from tests.conftest import crea_docente


def test_ti_neoimmesso_compare_nella_sezione_docenti_inseriti(app, db_session, monkeypatch):
    import routes.impostazione_anno as mod
    if 'impostazione_anno' not in app.blueprints:
        app.register_blueprint(mod.impostazione_anno_bp)
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    d = crea_docente('DiLiberto', tipo_contratto='TI')
    d.anno_scol_inizio = '2026-2027'
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/impostazione-anno/docenti-anno?anno=2026-2027')
        assert r.status_code == 200

    ids_td = {x.id for x in catturato['kwargs']['td_anno']}
    assert d.id in ids_td


def test_ti_neoimmesso_non_compare_in_docenti_gestione(app, db_session, monkeypatch):
    """Non deve comparire in ENTRAMBE le sezioni (di nuovo il pattern
    'due meccanismi paralleli' che Roberto ha già chiesto di evitare)."""
    import routes.impostazione_anno as mod
    if 'impostazione_anno' not in app.blueprints:
        app.register_blueprint(mod.impostazione_anno_bp)
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    d = crea_docente('DiLibertoBis', tipo_contratto='TI')
    d.anno_scol_inizio = '2026-2027'
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/impostazione-anno/docenti-anno?anno=2026-2027')
        assert r.status_code == 200

    ids_td = {x.id for x in catturato['kwargs']['td_anno']}
    ids_gestione = {x.id for x in catturato['kwargs']['docenti_gestione']}
    assert d.id in ids_td
    assert d.id not in ids_gestione


def test_td_supplente_neoimmesso_continua_a_comparire(app, db_session, monkeypatch):
    """Verifica di non-regressione: un TD/supplente inserito per
    l'anno (il caso originale per cui questa sezione esisteva) deve
    continuare a comparire lì."""
    import routes.impostazione_anno as mod
    if 'impostazione_anno' not in app.blueprints:
        app.register_blueprint(mod.impostazione_anno_bp)
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    d = crea_docente('Cantarella', tipo_contratto='TD_annuale')
    d.anno_scol_inizio = '2026-2027'
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/impostazione-anno/docenti-anno?anno=2026-2027')
        assert r.status_code == 200

    ids_td = {x.id for x in catturato['kwargs']['td_anno']}
    assert d.id in ids_td
