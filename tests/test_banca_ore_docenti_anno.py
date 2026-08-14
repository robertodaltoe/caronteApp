"""
Test di regressione: la pagina Banca Ore non deve elencare docenti il cui
anno_scol_inizio e' successivo all'anno scolastico visualizzato.

Prima del fix, routes/banca_ore.py::index() interrogava semplicemente
Docente.query.filter_by(attivo=True), ignorando anno_scol_inizio/
anno_scol_uscita: un docente neoassunto per il 2026-2027 (attivo=True fin
da subito) compariva anche nell'elenco Banca Ore del 2025-2026. Stesso bug
gia' preso in passato per la pagina Docenti (Task 35) e risolto li' con
_docenti_per_anno(); qui il fix mancava perche' la stessa logica era
duplicata invece di essere condivisa.
"""
from models import db
from tests.conftest import crea_docente


def _registra_banca_ore(app):
    from routes.banca_ore import banca_ore_bp
    with app.app_context():
        from models.config_app import ConfigApp  # noqa
        db.create_all()
    if 'banca_ore' not in app.blueprints:
        app.register_blueprint(banca_ore_bp)
    return app


def test_neoassunto_anno_futuro_non_compare_in_anno_precedente(app, db_session, monkeypatch):
    _registra_banca_ore(app)

    d_storico = crea_docente('Rossi', tipo_contratto='TI')
    d_nuovo = crea_docente('Bianchi', tipo_contratto='TI')
    d_nuovo.anno_scol_inizio = '2026-2027'
    db.session.commit()

    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda: '2025-2026')

    # Evitiamo il rendering Jinja completo (il fixture 'app' non ha il
    # template_folder del progetto): catturiamo direttamente i cognomi dei
    # docenti passati al template dalla view, che e' l'unica cosa che
    # interessa a questo test di regressione.
    catturato = {}
    import routes.banca_ore as banca_ore_mod
    def _fake_render_template(nome, **ctx):
        catturato['cognomi'] = {d.cognome for d in ctx['docenti']}
        return ''
    monkeypatch.setattr(banca_ore_mod, 'render_template', _fake_render_template)

    with app.test_client() as client:
        client.get('/banca-ore?anno=2025-2026')
        assert 'Rossi' in catturato['cognomi']
        assert 'Bianchi' not in catturato['cognomi']

        client.get('/banca-ore?anno=2026-2027')
        assert 'Rossi' in catturato['cognomi']
        assert 'Bianchi' in catturato['cognomi']
