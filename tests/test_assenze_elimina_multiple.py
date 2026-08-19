"""
Test di regressione per l'eliminazione multipla di assenze (Sessione 61):
Roberto segnala che un'assenza di più giorni non si può eliminare in
blocco, solo riga per riga — aggiunta una pagina "Assenze del docente"
con selezione manuale (checkbox) e un'azione di eliminazione multipla.

Copre: elimina solo le righe selezionate (non tutte le assenze del
docente), rimuove i movimenti banca ore/supplenze collegati solo alle
righe eliminate, e non tocca nulla se non viene selezionato nessun id.
"""
from datetime import date
from flask import g

from models import db
from models.assenza import Assenza
from models.movimento_banca_ore import MovimentoBancaOre
from tests.conftest import crea_docente


def _crea_tabelle_estese(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.sync_tombstone import SyncTombstone  # noqa
        db.create_all()
    # elimina_multiple() reindirizza con url_for('assenze.docente', ...):
    # serve il blueprint registrato sull'app di test per costruire l'URL,
    # la fixture 'app' leggera non lo fa (solo modelli, niente route).
    if 'assenze' not in app.blueprints:
        from routes.assenze import assenze_bp
        app.register_blueprint(assenze_bp)


class _UtenteFinto:
    def __init__(self, ruolo='ds', username='test'):
        self.ruolo = ruolo
        self.username = username


def _crea_assenza(id_docente, data_ass, motivo='ferie'):
    a = Assenza(id_docente=id_docente, data=data_ass, ora_inizio=1, ora_fine=9, motivo=motivo)
    db.session.add(a)
    db.session.flush()
    # stesso movimento banca ore che registra_assenze_form creerebbe
    db.session.add(MovimentoBancaOre(
        id_docente=id_docente, data=data_ass, minuti=-(9 * 60),
        tipo='malattia', descrizione='test',  # valore presente in TIPI_ASSENZA
    ))
    db.session.commit()
    return a


def test_elimina_solo_le_righe_selezionate(app, db_session):
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Vitali')
        a1 = _crea_assenza(d.id, date(2027, 3, 15))
        a2 = _crea_assenza(d.id, date(2027, 3, 16))
        a3 = _crea_assenza(d.id, date(2027, 3, 17))

        from routes.assenze import elimina_multiple
        with app.test_request_context('/assenze/elimina-multiple', method='POST', data={
            'ids': [str(a1.id), str(a2.id)],
            'id_docente': str(d.id),
        }):
            g.utente = _UtenteFinto()
            elimina_multiple()

        rimaste = Assenza.query.filter_by(id_docente=d.id).all()
        assert [a.id for a in rimaste] == [a3.id]
        # I movimenti banca ore delle righe eliminate spariscono, quello
        # della riga rimasta resta.
        mov = MovimentoBancaOre.query.filter_by(id_docente=d.id).all()
        assert len(mov) == 1
        assert mov[0].data == date(2027, 3, 17)


def test_nessuna_selezione_non_elimina_nulla(app, db_session):
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Colombo')
        _crea_assenza(d.id, date(2027, 3, 15))

        from routes.assenze import elimina_multiple
        with app.test_request_context('/assenze/elimina-multiple', method='POST', data={
            'ids': [],
            'id_docente': str(d.id),
        }):
            g.utente = _UtenteFinto()
            elimina_multiple()

        assert Assenza.query.filter_by(id_docente=d.id).count() == 1


def test_pagina_docente_filtra_per_periodo(app, db_session, monkeypatch):
    with app.app_context():
        d = crea_docente('Ferraro')
        _crea_assenza(d.id, date(2027, 1, 10))
        _crea_assenza(d.id, date(2027, 3, 15))
        _crea_assenza(d.id, date(2027, 6, 20))

        import routes.assenze as mod
        catturato = {}

        def _stub_render(nome, **ctx):
            catturato.update(ctx)
            return '<html></html>'
        monkeypatch.setattr(mod, 'render_template', _stub_render)

        with app.test_request_context('/assenze/docente/%d?da=2027-03-01&a=2027-04-01' % d.id):
            g.utente = _UtenteFinto()
            mod.docente(d.id)

        assenze = catturato['assenze']
        assert [a.data for a in assenze] == [date(2027, 3, 15)]
