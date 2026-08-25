"""
Bug reale, seguito diretto del fix precedente (tests/
test_nomina_rimuove_lapide.py): rimuovere la lapide LOCALE al momento
del salvataggio non basta — se il file su Drive è ancora quello
pubblicato PRIMA del salvataggio, contiene ancora la vecchia lapide.
Il giro di sync successivo la re-importa (perché non è più presente in
locale) e la applica subito, cancellando la riga appena salvata — a
prescindere da chi/dove l'avesse inserita.

Corretto confrontando l'orario della lapide con quello dell'ultima
modifica della riga (colonna_timestamp in TABELLE): una riga più
recente della lapide la supera, non viene cancellata, e una lapide più
vecchia arrivata dal remoto non sovrascrive più una riga locale più
recente.
"""
import os
import tempfile
from datetime import date, datetime, timedelta
import pytest
from flask import Flask
from models import db
from models.attivita_ist import AttivitaIst
from models.sostituzione_scrutinio import SostituzioneScrutinio
from models.sync_tombstone import SyncTombstone
from tests.conftest import crea_docente


@pytest.fixture
def db_remoto(tmp_path):
    path = str(tmp_path / 'remoto.db')
    remote_app = Flask('remoto')
    remote_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path}'
    remote_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(remote_app)
    with remote_app.app_context():
        db.create_all()
    return path


def _popola_remoto(path, docenti=None, eventi=None, tombstones=None):
    remote_app = Flask('remoto_write')
    remote_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path}'
    remote_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(remote_app)
    with remote_app.app_context():
        for d in (docenti or []):
            db.session.add(d)
        for e in (eventi or []):
            db.session.add(e)
        db.session.flush()
        for t in (tombstones or []):
            db.session.add(t)
        db.session.commit()


def test_riga_piu_recente_della_lapide_remota_non_viene_cancellata(app, db_session, db_remoto):
    """Riproduce esattamente lo scenario di Roberto: una lapide vecchia
    (pubblicata su Drive PRIMA del salvataggio) non deve cancellare la
    riga appena inserita in locale per la stessa chiave."""
    assente = crea_docente('DelCurto')
    sostituto = crea_docente('Landi')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 4A CAT', classe='4A CAT',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    # La riga locale, appena salvata (modificato_il = adesso).
    riga = SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                  id_sostituto=sostituto.id)
    db.session.add(riga)
    db.session.commit()

    # Sul "remoto" (Drive, non ancora aggiornato) c'è ancora la vecchia
    # lapide per la stessa chiave, con un orario PRECEDENTE al
    # salvataggio appena fatto in locale.
    import json
    chiave = json.dumps({'id_attivita': ev.id, 'id_assente': assente.id}, sort_keys=True)
    vecchia = SyncTombstone(tabella='sostituzioni_scrutinio', chiave_logica=chiave,
                             eliminato_il=datetime.utcnow() - timedelta(minutes=10))
    _popola_remoto(db_remoto, tombstones=[vecchia])

    from modules.auto_sync import _merge_additivo
    ris = _merge_additivo(db, db_remoto)

    assert ris['eliminate'] == 0
    ancora_presente = SostituzioneScrutinio.query.filter_by(
        id_attivita=ev.id, id_assente=assente.id).first()
    assert ancora_presente is not None
    assert ancora_presente.id_sostituto == sostituto.id


def test_lapide_piu_recente_della_riga_locale_la_cancella_comunque(app, db_session, db_remoto):
    """Il caso opposto deve continuare a funzionare come prima: una
    lapide GENUINAMENTE più recente (una cancellazione vera fatta
    dopo, su un'altra postazione) deve ancora poter cancellare una
    riga locale più vecchia."""
    assente = crea_docente('Ghezzi')
    sostituto = crea_docente('Valena')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 3A LSU', classe='3A LSU',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    riga = SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                  id_sostituto=sostituto.id)
    db.session.add(riga)
    db.session.commit()

    import json
    chiave = json.dumps({'id_attivita': ev.id, 'id_assente': assente.id}, sort_keys=True)
    nuova = SyncTombstone(tabella='sostituzioni_scrutinio', chiave_logica=chiave,
                           eliminato_il=datetime.utcnow() + timedelta(minutes=10))
    _popola_remoto(db_remoto, tombstones=[nuova])

    from modules.auto_sync import _merge_additivo
    ris = _merge_additivo(db, db_remoto)

    assert ris['eliminate'] == 1
    assert SostituzioneScrutinio.query.filter_by(
        id_attivita=ev.id, id_assente=assente.id).first() is None
