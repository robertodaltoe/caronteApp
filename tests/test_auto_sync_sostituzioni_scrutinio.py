"""
Richiesta di Roberto: includere anche le sostituzioni scrutinio nel
sync automatico additivo, per rilevare i conflitti tra nomine fatte da
postazioni diverse — come già avviene per assenze/supplenze/
indisponibilita (modules/auto_sync.py). A differenza di Assegnazioni/
AttivitaFuoriAula (deliberatamente esclusi, tabelle collegate/id
auto-referenziali troppo delicate), SostituzioneScrutinio è una
tabella piatta senza figlie proprie, stessa forma di 'supplenze' — la
sua unica particolarità è una FK verso AttivitaIst (non sincronizzata):
se l'evento non esiste ancora in locale, la riga va semplicemente
saltata per quel giro (stessa logica già in uso per id_docente verso
'docenti'), mai forzata con una FK rotta.
"""
import os
import tempfile
from datetime import date, datetime
import pytest
from flask import Flask
from models import db
from models.docente import Docente
from models.attivita_ist import AttivitaIst
from models.sostituzione_scrutinio import SostituzioneScrutinio
from models.sync_conflitto import SyncConflitto
from models.sync_tombstone import SyncTombstone
from tests.conftest import crea_docente


@pytest.fixture
def db_remoto(tmp_path):
    """Un secondo database SQLite completo (stesso schema, via lo
    stesso SQLAlchemy), che simula il file scaricato da Drive
    dall'altra postazione. Ritorna il path del file .db."""
    path = str(tmp_path / 'remoto.db')
    remote_app = Flask('remoto')
    remote_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path}'
    remote_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(remote_app)
    with remote_app.app_context():
        db.create_all()
    return path


def _popola_remoto(db_remoto_path, righe_sostituzioni, docenti=None, eventi=None):
    """Scrive righe nel DB 'remoto' con una sessione a parte, per non
    interferire con la sessione locale già viva nei test."""
    remote_app = Flask('remoto_write')
    remote_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_remoto_path}'
    remote_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(remote_app)
    with remote_app.app_context():
        for d in (docenti or []):
            db.session.add(d)
        for e in (eventi or []):
            db.session.add(e)
        db.session.flush()
        for r in righe_sostituzioni:
            db.session.add(r)
        db.session.commit()


def test_riga_nuova_dal_remoto_viene_importata_in_locale(app, db_session, db_remoto):
    d_assente = crea_docente('Assente')
    d_sost = crea_docente('Sostituto')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', classe='3A LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    # Sul "remoto", stessi id (docenti/evento condivisi, come da
    # assunzione già in uso per il resto del sync) più una nomina che
    # in locale ancora non esiste.
    _popola_remoto(db_remoto, [
        SostituzioneScrutinio(id_attivita=ev.id, id_assente=d_assente.id,
                               id_sostituto=d_sost.id, n_protocollo='12/2026'),
    ])

    from modules.auto_sync import _merge_additivo
    ris = _merge_additivo(db, db_remoto)

    assert ris['inserite'] == 1
    riga = SostituzioneScrutinio.query.filter_by(id_attivita=ev.id, id_assente=d_assente.id).first()
    assert riga is not None
    assert riga.id_sostituto == d_sost.id
    assert riga.n_protocollo == '12/2026'


def test_riga_con_evento_inesistente_in_locale_viene_saltata(app, db_session, db_remoto):
    """L'evento (AttivitaIst) non è sincronizzato: se sul remoto esiste
    una sostituzione per un id_attivita che in locale non c'è (evento
    creato indipendentemente sulle due macchine), non va forzata — si
    salta, niente FK rotta."""
    d_assente = crea_docente('Assente2')
    d_sost = crea_docente('Sostituto2')
    db.session.commit()

    _popola_remoto(db_remoto, [
        SostituzioneScrutinio(id_attivita=9999, id_assente=d_assente.id,
                               id_sostituto=d_sost.id),
    ])

    from modules.auto_sync import _merge_additivo
    ris = _merge_additivo(db, db_remoto)

    assert ris['inserite'] == 0
    assert SostituzioneScrutinio.query.count() == 0


def test_stesso_assente_con_sostituto_diverso_genera_conflitto(app, db_session, db_remoto):
    """Caso reale che Roberto vuole intercettare: due postazioni
    nominano sostituti DIVERSI per lo stesso assente della stessa
    riunione — non deve essere scelto in automatico, va segnalato."""
    d_assente = crea_docente('Assente3')
    d_sost_locale = crea_docente('SostitutoLocale')
    d_sost_remoto = crea_docente('SostitutoRemoto')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', classe='3B LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=d_assente.id,
                                          id_sostituto=d_sost_locale.id))
    db.session.commit()

    _popola_remoto(db_remoto, [
        SostituzioneScrutinio(id_attivita=ev.id, id_assente=d_assente.id,
                               id_sostituto=d_sost_remoto.id),
    ])

    from modules.auto_sync import _merge_additivo
    ris = _merge_additivo(db, db_remoto)

    assert ris['conflitti_nuovi'] == 1
    conflitto = SyncConflitto.query.filter_by(tabella='sostituzioni_scrutinio').first()
    assert conflitto is not None
    assert 'id_sostituto' in conflitto.campi_diversi
    # La riga locale non viene toccata finché il conflitto non è risolto a mano.
    riga = SostituzioneScrutinio.query.filter_by(id_attivita=ev.id, id_assente=d_assente.id).first()
    assert riga.id_sostituto == d_sost_locale.id


def test_stessa_nomina_su_entrambe_non_genera_conflitto(app, db_session, db_remoto):
    d_assente = crea_docente('Assente4')
    d_sost = crea_docente('Sostituto4')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', classe='3C LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=d_assente.id,
                                          id_sostituto=d_sost.id, n_protocollo='5/2026'))
    db.session.commit()

    _popola_remoto(db_remoto, [
        SostituzioneScrutinio(id_attivita=ev.id, id_assente=d_assente.id,
                               id_sostituto=d_sost.id, n_protocollo='5/2026'),
    ])

    from modules.auto_sync import _merge_additivo
    ris = _merge_additivo(db, db_remoto)

    assert ris['inserite'] == 0
    assert ris['conflitti_nuovi'] == 0
