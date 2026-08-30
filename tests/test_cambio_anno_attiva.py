"""
Roberto, prima di eseguire il cambio anno reale: "ho un dubbio; ho
delle indisponibilità che scavalcano l'anno scolastico [...] quelli
li perderò?" — verificato nel codice: routes/cambio_anno.py::attiva()
cancellava TUTTE le righe di Indisponibilita senza alcun filtro per
data (Indisponibilita.query.delete() sull'intera tabella), non solo
quelle dell'anno che si chiude — un'indisponibilità già inserita per
il nuovo anno sarebbe sparita insieme alle vecchie.

Fix: elimina solo le righe datate entro la fine dell'anno precedente
(31/08), lasciando intatte quelle già inserite per il nuovo anno.
"""
from datetime import date
from models import db
from models.indisponibilita import Indisponibilita
from models.config_app import ConfigApp
from models.piano_studi import ClasseSezione


def _imposta_anno_corrente(anno):
    db.session.add(ConfigApp(chiave='anno_scol_corrente', valore=anno))
    db.session.commit()


def _registra_blueprint(app):
    import routes.cambio_anno as mod
    if 'cambio_anno' not in app.blueprints:
        app.register_blueprint(mod.cambio_anno_bp)


def test_attiva_elimina_solo_indisponibilita_anno_precedente(app, db_session):
    _registra_blueprint(app)
    _imposta_anno_corrente('2025-2026')

    # L'anno nuovo deve risultare "preparato" (almeno una ClasseSezione)
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.commit()

    # Indisponibilità dell'anno che si chiude (deve sparire)
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 6, 4), motivo='altro'))
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 8, 31), motivo='altro'))
    # Indisponibilità già inserita per il nuovo anno (deve restare)
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 10, 15), motivo='altro'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })
        assert r.status_code == 302

    rimaste = Indisponibilita.query.all()
    assert len(rimaste) == 1
    assert rimaste[0].data == date(2026, 10, 15)


def test_attiva_senza_indisponibilita_future_le_elimina_tutte(app, db_session):
    """Caso comune (nessuna indisponibilità ancora inserita per il nuovo
    anno): il comportamento resta lo stesso di prima, tutto svuotato."""
    _registra_blueprint(app)
    _imposta_anno_corrente('2025-2026')
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 5, 1), motivo='altro'))
    db.session.add(Indisponibilita(id_docente=2, data=date(2026, 8, 31), motivo='altro'))
    db.session.commit()

    with app.test_client() as c:
        c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })

    assert Indisponibilita.query.count() == 0
