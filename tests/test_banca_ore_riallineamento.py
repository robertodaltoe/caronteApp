"""Una supplenza a recupero con sostituto conta nel saldo solo se esiste il
movimento +60 min: l'autosync copia la riga ma non il movimento, quindi lo
crea; per i casi già esistenti c'è il riallineamento a scelta."""
import sqlite3
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine

from models import db
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from modules import banca_ore_riallineamento as ria
from modules.auto_sync import _merge_additivo
from tests.conftest import crea_docente


@pytest.fixture
def remoto_path(tmp_path):
    path = tmp_path / 'remoto.db'
    engine = create_engine(f'sqlite:///{path}')
    db.metadata.create_all(engine)
    engine.dispose()
    return str(path)


def _supplenza_remota(path, id_sostituto, id_assente, tipo='recupero', stato='assegnata'):
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO supplenze (data, ora, classe, id_assente, id_sostituto, tipo, stato, "
        "origine, creato_il, modificato_il) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ('2026-10-29', 3, '2A', id_assente, id_sostituto, tipo, stato, 'manuale',
         datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def test_autosync_crea_il_movimento_per_la_supplenza_recupero_importata(app, db_session, remoto_path):
    sost, ass = crea_docente('DeAgostini'), crea_docente('Assente')
    db.session.commit()
    _supplenza_remota(remoto_path, sost.id, ass.id)

    _merge_additivo(db, remoto_path)

    s = Supplenza.query.one()
    m = MovimentoBancaOre.query.filter_by(id_supplenza=s.id).one()
    assert (m.id_docente, m.minuti, m.tipo) == (sost.id, 60, 'supplenza_recupero')
    assert m.anno_scol == '2026-2027'


def test_autosync_non_crea_movimento_per_altri_tipi(app, db_session, remoto_path):
    sost, ass = crea_docente('Sost'), crea_docente('Ass')
    db.session.commit()
    _supplenza_remota(remoto_path, sost.id, ass.id, tipo='completamento')

    _merge_additivo(db, remoto_path)

    assert MovimentoBancaOre.query.count() == 0


def test_autosync_non_tocca_le_anomalie_preesistenti(app, db_session, remoto_path):
    sost, ass = crea_docente('Sost2'), crea_docente('Ass2')
    db.session.commit()
    db.session.add(Supplenza(data=date(2026, 10, 20), ora=2, classe='1A', id_assente=ass.id,
                             id_sostituto=sost.id, tipo='recupero', stato='assegnata'))
    db.session.commit()

    _merge_additivo(db, remoto_path)  # remoto vuoto

    assert MovimentoBancaOre.query.count() == 0
    assert len(ria.trova()) == 1


def test_riallinea_crea_solo_le_righe_scelte(app, db_session):
    sost, ass = crea_docente('Sost3'), crea_docente('Ass3')
    db.session.commit()
    s1 = Supplenza(data=date(2026, 10, 20), ora=2, id_assente=ass.id, id_sostituto=sost.id,
                   tipo='recupero', stato='assegnata')
    s2 = Supplenza(data=date(2026, 10, 21), ora=2, id_assente=ass.id, id_sostituto=sost.id,
                   tipo='recupero', stato='assegnata')
    s3 = Supplenza(data=date(2026, 10, 22), ora=2, id_assente=ass.id, id_sostituto=sost.id,
                   tipo='pagamento', stato='assegnata')
    db.session.add_all([s1, s2, s3])
    db.session.commit()

    assert {s.id for s in ria.trova()} == {s1.id, s2.id}
    assert ria.riallinea([s1.id, s3.id]) == 1
    db.session.commit()

    assert [m.id_supplenza for m in MovimentoBancaOre.query.all()] == [s1.id]
    assert {s.id for s in ria.trova()} == {s2.id}
    assert ria.riallinea([s1.id]) == 0  # già a posto: nessun doppione
