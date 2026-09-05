"""
Roberto: "ma se volessi vedere il report del dirigente dell'anno
precedente?" — seguito di "mettilo per ogni report della pagina
report" (dopo aver scoperto che Banca Ore aveva già un selettore anno,
ma il Report Dirigente no).

Causa: routes/report.py::dirigente() non accettava affatto un
parametro anno — sempre Docente.query.filter_by(attivo=True) e
get_saldi_docente(d.id) senza anno_scol, quindi sempre e solo l'anno
corrente, senza modo di consultare un anno precedente.

Fix: dirigente() e index() (tab 'docenti') accettano ora ?anno=,
usano _docenti_per_anno(anno) al posto del filtro naive attivo=True
(un docente uscito nel frattempo va incluso consultando un anno
passato, uno neoassunto va escluso), e passano anno/anno_corrente/
anni_disponibili al template per il selettore. Il tab Cruscotto resta
deliberatamente sempre sull'anno corrente (pannello in tempo reale,
non ha senso "consultarlo per l'anno scorso").
"""
from models import db
from tests.conftest import crea_docente


def _registra_report(app):
    from routes.report import report_bp
    if 'report' not in app.blueprints:
        app.register_blueprint(report_bp)
    from routes.banca_ore import banca_ore_bp
    if 'banca_ore' not in app.blueprints:
        app.register_blueprint(banca_ore_bp)


def test_dirigente_neoassunto_anno_futuro_non_compare_in_anno_precedente(app, db_session, monkeypatch):
    _registra_report(app)

    d_storico = crea_docente('Rossi', tipo_contratto='TI')
    d_nuovo = crea_docente('Bianchi', tipo_contratto='TI')
    d_nuovo.anno_scol_inizio = '2026-2027'
    db.session.commit()

    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda: '2025-2026')

    catturato = {}
    import routes.report as report_mod
    def _fake_render_template(nome, **ctx):
        catturato['ctx'] = ctx
        return ''
    monkeypatch.setattr(report_mod, 'render_template', _fake_render_template)

    with app.test_client() as client:
        client.get('/report/dirigente?anno=2025-2026')
        assert catturato['ctx']['n_docenti'] == 1
        assert catturato['ctx']['anno'] == '2025-2026'
        assert catturato['ctx']['anno_corrente'] == '2025-2026'

        client.get('/report/dirigente?anno=2026-2027')
        assert catturato['ctx']['n_docenti'] == 2


def test_dirigente_default_senza_anno_usa_anno_corrente(app, db_session, monkeypatch):
    _registra_report(app)
    crea_docente('Verdi', tipo_contratto='TI')

    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda: '2025-2026')

    catturato = {}
    import routes.report as report_mod
    def _fake_render_template(nome, **ctx):
        catturato['ctx'] = ctx
        return ''
    monkeypatch.setattr(report_mod, 'render_template', _fake_render_template)

    with app.test_client() as client:
        client.get('/report/dirigente')
        assert catturato['ctx']['anno'] == '2025-2026'


def test_tab_docenti_rispetta_lanno_selezionato(app, db_session, monkeypatch):
    _registra_report(app)

    d_storico = crea_docente('Neri', tipo_contratto='TI')
    d_nuovo = crea_docente('Gialli', tipo_contratto='TI')
    d_nuovo.anno_scol_inizio = '2026-2027'
    db.session.commit()

    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda: '2025-2026')

    catturato = {}
    import routes.report as report_mod
    def _fake_render_template(nome, **ctx):
        catturato['ctx'] = ctx
        return ''
    monkeypatch.setattr(report_mod, 'render_template', _fake_render_template)

    with app.test_client() as client:
        client.get('/report?tab=docenti&anno=2025-2026')
        cognomi = {d.cognome for d in catturato['ctx']['docenti']}
        assert 'Neri' in cognomi
        assert 'Gialli' not in cognomi

        # Il tab Cruscotto, invece, non prende l'anno dalla query string:
        # resta sempre sull'anno corrente (pannello in tempo reale).
        client.get('/report?tab=cruscotto')
        cognomi_cruscotto = {d.cognome for d in catturato['ctx']['docenti']}
        assert 'Neri' in cognomi_cruscotto
        assert 'Gialli' in cognomi_cruscotto  # attivo=True, non filtrato per anno qui
