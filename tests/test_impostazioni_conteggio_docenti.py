"""
Roberto, subito dopo il cambio anno: "perchè risultano 106 docenti
attivi? non sono 106 i docenti attivi".

Causa: routes/impostazioni.py::index() contava
Docente.query.filter_by(attivo=True).count() — il flag `attivo` non
viene mai azzerato automaticamente quando arriva anno_scol_uscita (si
aggiorna solo a mano, es. da "Elimina" in Docenti), quindi il KPI
"Docenti attivi"/"Docenti TI" in cima a Impostazioni continuava a
contare anche chi aveva lasciato la scuola proprio a partire
dall'anno appena attivato (fine_td/trasferimento/pensionamento con
anno_scol_uscita == anno corrente) — 32 persone sui 106 mostrati sul
DB reale. Corretto per usare _docenti_per_anno(anno_corrente), la
stessa funzione già usata da Docenti/Assegnazioni per questo motivo.
"""
from datetime import date
from models import db
from models.docente import Docente
from models.config_app import ConfigApp


def _imposta_anno_corrente(anno):
    db.session.add(ConfigApp(chiave='anno_scol_corrente', valore=anno))
    db.session.commit()


def _registra_blueprint(app):
    import routes.impostazioni as mod
    if 'impostazioni' not in app.blueprints:
        app.register_blueprint(mod.impostazioni_bp)


def test_docente_uscito_dallanno_corrente_non_conta_come_attivo(app, db_session, monkeypatch):
    _registra_blueprint(app)
    _imposta_anno_corrente('2026-2027')

    # Ancora davvero in servizio
    db.session.add(Docente(cognome='ROSSI', nome='Mario', attivo=True,
                            tipo_contratto='TI'))
    # Uscito PROPRIO a partire dall'anno corrente (attivo mai riportato
    # a False — caso reale trovato da Roberto)
    db.session.add(Docente(cognome='BIANCHI', nome='Anna', attivo=True,
                            tipo_contratto='TI', anno_scol_uscita='2026-2027',
                            motivo_uscita='pensionamento'))
    db.session.commit()

    import routes.impostazioni as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get('/impostazioni')
        assert r.status_code == 200

    assert catturato['kwargs']['n_docenti'] == 1
    assert catturato['kwargs']['n_ti'] == 1
