"""
Roberto: dopo aver "annullato l'uscita" di un docente da Impostazione
anno -> Docenti per anno, non lo vedeva comparire nell'elenco a
tendina per sostituire un placeholder in Assegnazioni.

Causa: routes/impostazione_anno.py::docenti_anno(), azione
'annulla_uscita', puliva anno_scol_uscita/motivo_uscita ma non
riattivava mai attivo=True — se il docente era stato disattivato
anche su quel campo (non solo con la data di uscita), restava escluso
da _docenti_per_anno() (routes/impostazione_anno.py, richiede sempre
attivo=True), quindi invisibile in Assegnazioni. Il pulsante "Riattiva"
della pagina Docenti (routes/docenti.py::riattiva()) gestiva già
correttamente questo campo — due meccanismi paralleli, allineati ora.
"""
from datetime import date
from models import db
from models.docente import Docente
from models.config_app import ConfigApp


def _registra_blueprint(app):
    import routes.impostazione_anno as mod
    if 'impostazione_anno' not in app.blueprints:
        app.register_blueprint(mod.impostazione_anno_bp)


def _imposta_anno_corrente(anno):
    db.session.add(ConfigApp(chiave='anno_scol_corrente', valore=anno))
    db.session.commit()


def _crea_docente_uscito(cognome='ROSSI', tipo_contratto='TI'):
    d = Docente(cognome=cognome, nome='Mario', attivo=False,
                anno_scol_uscita='2025-2026', motivo_uscita='trasferimento',
                tipo_contratto=tipo_contratto, ore_contratto=18)
    db.session.add(d)
    db.session.commit()
    return d


def test_annulla_uscita_riattiva_anche_il_docente(app, db_session):
    _registra_blueprint(app)
    d = _crea_docente_uscito()
    assert d.attivo is False

    with app.test_client() as c:
        r = c.post('/impostazione-anno/docenti-anno', data={
            'azione': 'annulla_uscita', 'id_docente': str(d.id),
            'anno_scol': '2026-2027',
        })
        assert r.status_code == 302

    aggiornato = db.session.get(Docente, d.id)
    assert aggiornato.attivo is True
    assert aggiornato.anno_scol_uscita is None
    assert aggiornato.motivo_uscita is None


def test_docente_riattivato_compare_in_docenti_per_anno(app, db_session):
    """Verifica end-to-end il caso reale: dopo annulla_uscita, il
    docente deve comparire nella query che alimenta il menu di
    Assegnazioni per sostituire un placeholder."""
    _registra_blueprint(app)
    from routes.impostazione_anno import _docenti_per_anno
    d = _crea_docente_uscito()

    assert d.id not in {x.id for x in _docenti_per_anno('2026-2027')}

    with app.test_client() as c:
        c.post('/impostazione-anno/docenti-anno', data={
            'azione': 'annulla_uscita', 'id_docente': str(d.id),
            'anno_scol': '2026-2027',
        })

    assert d.id in {x.id for x in _docenti_per_anno('2026-2027')}


def test_td_senza_anno_inizio_riattivato_per_anno_futuro(app, db_session):
    """Caso reale (May, Verderame): un TD/supplente riattivato per un
    anno FUTURO rispetto all'anno corrente reale — senza
    anno_scol_inizio valorizzato, _docenti_per_anno() lo esclude
    apposta (non ancora nominato per quell'anno), anche con attivo=True
    e uscita annullata. annulla_uscita deve valorizzarlo con l'anno
    della pagina."""
    _registra_blueprint(app)
    from routes.impostazione_anno import _docenti_per_anno
    _imposta_anno_corrente('2025-2026')
    d = _crea_docente_uscito(cognome='MAY', tipo_contratto='TD_GS')
    d.anno_scol_inizio = None
    db.session.commit()

    assert d.id not in {x.id for x in _docenti_per_anno('2026-2027')}

    with app.test_client() as c:
        c.post('/impostazione-anno/docenti-anno', data={
            'azione': 'annulla_uscita', 'id_docente': str(d.id),
            'anno_scol': '2026-2027',
        })

    aggiornato = db.session.get(Docente, d.id)
    assert aggiornato.anno_scol_inizio == '2026-2027'
    assert d.id in {x.id for x in _docenti_per_anno('2026-2027')}


def test_non_sovrascrive_anno_inizio_gia_presente(app, db_session):
    """Un docente con anno_scol_inizio già impostato (es. nominato in
    passato per un anno specifico) non deve vederselo cambiato da
    annulla_uscita."""
    _registra_blueprint(app)
    d = _crea_docente_uscito(cognome='BIANCHI', tipo_contratto='TD_GS')
    d.anno_scol_inizio = '2024-2025'
    db.session.commit()

    with app.test_client() as c:
        c.post('/impostazione-anno/docenti-anno', data={
            'azione': 'annulla_uscita', 'id_docente': str(d.id),
            'anno_scol': '2026-2027',
        })

    aggiornato = db.session.get(Docente, d.id)
    assert aggiornato.anno_scol_inizio == '2024-2025'
