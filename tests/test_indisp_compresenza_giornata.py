"""Due docenti in compresenza, entrambi indisponibili tutta la giornata
(ora=None) con 'genera supplenza': la classe deve risultare coperta da
una supplenza per ciascuno, indipendentemente dall'ordine di inserimento."""
from datetime import date

from models import db
from models.indisponibilita import Indisponibilita
from models.supplenza import Supplenza
from modules import compresenze
from modules.assenze_registrazione import _genera_supplenze
from tests.conftest import crea_docente
from tests.test_validita_orario import _orario

VENERDI = date(2026, 10, 30)


def _setup():
    compresenze.invalida_cache()
    g = crea_docente('Grassi')
    l = crea_docente('Longoni')
    for d in (g, l):
        _orario(d.id, VENERDI.weekday(), 3, '3A LSU')
    db.session.commit()
    return g, l


def test_compagno_indisponibile_tutto_il_giorno_non_conta_come_presente(app, db_session):
    g, l = _setup()
    db.session.add(Indisponibilita(id_docente=l.id, data=VENERDI, ora=None,
                                   motivo='uscita', genera_supplenza=True))
    db.session.commit()
    assert _genera_supplenze(g.id, VENERDI, 1, 9, True, note_display='') == 1


def test_due_indisponibili_insieme_registrati_prima_di_generare(app, db_session):
    g, l = _setup()
    for d in (g, l):
        db.session.add(Indisponibilita(id_docente=d.id, data=VENERDI, ora=None,
                                       motivo='uscita', genera_supplenza=True))
    db.session.flush()
    for d in (g, l):
        _genera_supplenze(d.id, VENERDI, 1, 9, True, note_display='')
    assert {s.id_assente for s in Supplenza.query.all()} == {g.id, l.id}
