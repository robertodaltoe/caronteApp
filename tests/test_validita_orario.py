"""
Roberto: durante la fase di orari provvisori settimanali (inizio anno)
l'orario cambia di settimana in settimana, ma finora un reimport non
toccava mai le Supplenze già generate — restavano congelate col vecchio
orario, e non c'era modo di dire "questo orario vale solo per questo
periodo".

Copre:
1. models/orario_docente.py::validita_orario_corrente() — legge la
   validità dall'ultimo import (None/None se non impostata).
2. modules/assenze_registrazione.py::_genera_supplenze() — non genera
   nulla per una data fuori dalla validità impostata.
3. modules/assenze_registrazione.py::ricalcola_supplenze_periodo() — il
   cuore della feature: cancella le supplenze automatiche non più
   coerenti col nuovo orario (anche se già assegnate), aggiunge quelle
   mancanti, non tocca mai quelle origine='manuale', e non cancella (ma
   segnala) quelle in un giorno precedente alla data di importazione.
4. Nessuna validità impostata -> comportamento invariato (orario
   "definitivo", sempre valido).
"""
from datetime import date

from models import db
from models.assenza import Assenza
from models.orario_docente import OrarioDocente, validita_orario_corrente
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from modules.assenze_registrazione import _genera_supplenze, ricalcola_supplenze_periodo
from tests.conftest import crea_docente

LUNEDI = date(2026, 9, 21)


def _orario(id_docente, giorno, ora, classe, materia='Materia',
            v_ini=None, v_fine=None, tipo_ora='lezione'):
    o = OrarioDocente(id_docente=id_docente, giorno=giorno, ora=ora,
                       classe=classe, materia=materia, tipo_ora=tipo_ora,
                       data_inizio_validita=v_ini, data_fine_validita=v_fine)
    db.session.add(o)
    return o


def _assenza(id_docente, data, ora_inizio=1, ora_fine=9, motivo='malattia'):
    a = Assenza(id_docente=id_docente, data=data, ora_inizio=ora_inizio,
                ora_fine=ora_fine, motivo=motivo)
    db.session.add(a)
    db.session.commit()
    return a


# ── validita_orario_corrente() ────────────────────────────────────

def test_validita_orario_corrente_vuota_se_non_impostata(app, db_session):
    doc = crea_docente('Bianchi')
    _orario(doc.id, giorno=0, ora=1, classe='3A LSU')
    db.session.commit()

    assert validita_orario_corrente() == (None, None)


def test_validita_orario_corrente_legge_intervallo(app, db_session):
    doc = crea_docente('Bianchi')
    _orario(doc.id, giorno=0, ora=1, classe='3A LSU',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    assert validita_orario_corrente() == (date(2026, 9, 21), date(2026, 9, 26))


# ── _genera_supplenze(): guardia sulla validità ───────────────────

def test_genera_supplenze_niente_fuori_dalla_validita(app, db_session):
    doc = crea_docente('Bianchi')
    _orario(doc.id, giorno=LUNEDI.weekday(), ora=3, classe='3A LSU',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    fuori = date(2026, 9, 28)  # oltre la validità impostata
    n = _genera_supplenze(doc.id, fuori, 1, 9, True, note_display='')
    assert n == 0
    assert Supplenza.query.count() == 0


def test_genera_supplenze_normale_dentro_la_validita(app, db_session):
    doc = crea_docente('Bianchi')
    _orario(doc.id, giorno=LUNEDI.weekday(), ora=3, classe='3A LSU',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    n = _genera_supplenze(doc.id, LUNEDI, 1, 9, True, note_display='')
    assert n == 1
    assert Supplenza.query.filter_by(id_assente=doc.id, data=LUNEDI, ora=3).count() == 1


# ── ricalcola_supplenze_periodo(): il cuore della feature ─────────

def test_ricalcola_cancella_supplenza_obsoleta_anche_se_assegnata(app, db_session):
    """Il caso segnalato da Roberto: una supplenza già assegnata a un
    sostituto per una classe che nel nuovo orario non esiste più a
    quell'ora va cancellata comunque (non solo se ancora 'scoperta')."""
    assente = crea_docente('Rossi')
    sostituto = crea_docente('Verdi')

    # Vecchio stato: supplenza automatica già assegnata su 3A LSU ora 3.
    s = Supplenza(data=LUNEDI, ora=3, classe='3A LSU', id_assente=assente.id,
                  id_sostituto=sostituto.id, tipo='recupero', stato='assegnata',
                  origine='automatica')
    db.session.add(s)
    db.session.commit()
    db.session.add(MovimentoBancaOre(id_docente=sostituto.id, data=LUNEDI,
                                      minuti=60, tipo='supplenza_recupero',
                                      id_supplenza=s.id))
    db.session.commit()

    _assenza(assente.id, LUNEDI)

    # Nuovo orario: quel docente ora fa 3B RIM all'ora 3, non più 3A LSU.
    _orario(assente.id, giorno=LUNEDI.weekday(), ora=3, classe='3B RIM',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    esito = ricalcola_supplenze_periodo(date(2026, 9, 21), date(2026, 9, 26),
                                         oggi=date(2026, 9, 21))

    assert esito['cancellate'] == 1
    assert esito['create'] == 1
    assert Supplenza.query.filter_by(data=LUNEDI, ora=3, classe='3A LSU').count() == 0
    nuova = Supplenza.query.filter_by(data=LUNEDI, ora=3, classe='3B RIM').first()
    assert nuova is not None
    assert nuova.stato == 'scoperta'  # riparte da zero, non eredita il sostituto
    assert MovimentoBancaOre.query.filter_by(id_supplenza=s.id).count() == 0


def test_ricalcola_non_tocca_supplenze_manuali(app, db_session):
    assente = crea_docente('Rossi')
    s_manuale = Supplenza(data=LUNEDI, ora=3, classe='3A LSU', id_assente=assente.id,
                           tipo='recupero', stato='scoperta', origine='manuale')
    db.session.add(s_manuale)
    db.session.commit()

    _assenza(assente.id, LUNEDI)
    _orario(assente.id, giorno=LUNEDI.weekday(), ora=3, classe='3B RIM',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    esito = ricalcola_supplenze_periodo(date(2026, 9, 21), date(2026, 9, 26),
                                         oggi=date(2026, 9, 21))

    assert esito['cancellate'] == 0
    assert Supplenza.query.filter_by(id=s_manuale.id).count() == 1


def test_ricalcola_segnala_ma_non_cancella_se_giorno_precedente_importazione(app, db_session):
    assente = crea_docente('Rossi')
    ieri = date(2026, 9, 18)  # venerdì -- LUNEDI = 21/9

    s = Supplenza(data=ieri, ora=3, classe='3A LSU', id_assente=assente.id,
                  tipo='recupero', stato='assegnata', origine='automatica')
    db.session.add(s)
    db.session.commit()

    _assenza(assente.id, ieri)
    # Il nuovo orario non ha più quella classe/ora per il docente.
    _orario(assente.id, giorno=ieri.weekday(), ora=3, classe='3B RIM',
            v_ini=date(2026, 9, 18), v_fine=date(2026, 9, 26))
    db.session.commit()

    esito = ricalcola_supplenze_periodo(date(2026, 9, 18), date(2026, 9, 26),
                                         oggi=date(2026, 9, 21))

    assert esito['cancellate'] == 0
    assert len(esito['da_rivedere']) == 1
    assert esito['da_rivedere'][0]['data'] == ieri.isoformat()
    assert esito['da_rivedere'][0]['ora'] == 3
    assert esito['da_rivedere'][0]['docente'] == 'Rossi'
    # Non cancellata: resta esattamente com'era.
    assert Supplenza.query.filter_by(id=s.id).count() == 1


def test_ricalcola_aggiunge_supplenza_mancante(app, db_session):
    assente = crea_docente('Rossi')
    _assenza(assente.id, LUNEDI)
    _orario(assente.id, giorno=LUNEDI.weekday(), ora=4, classe='2A CAT',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    esito = ricalcola_supplenze_periodo(date(2026, 9, 21), date(2026, 9, 26))

    assert esito['create'] == 1
    assert Supplenza.query.filter_by(data=LUNEDI, ora=4, classe='2A CAT').count() == 1


def test_ricalcola_nessun_effetto_se_supplenza_ancora_coerente(app, db_session):
    """Se classe/ora non cambiano, la supplenza esistente resta intoccata
    (nessuna cancellazione + ricreazione inutile)."""
    assente = crea_docente('Rossi')
    sostituto = crea_docente('Verdi')
    s = Supplenza(data=LUNEDI, ora=3, classe='3A LSU', id_assente=assente.id,
                  id_sostituto=sostituto.id, tipo='recupero', stato='assegnata',
                  origine='automatica')
    db.session.add(s)
    db.session.commit()

    _assenza(assente.id, LUNEDI)
    _orario(assente.id, giorno=LUNEDI.weekday(), ora=3, classe='3A LSU',
            v_ini=date(2026, 9, 21), v_fine=date(2026, 9, 26))
    db.session.commit()

    esito = ricalcola_supplenze_periodo(date(2026, 9, 21), date(2026, 9, 26))

    assert esito['cancellate'] == 0
    assert esito['create'] == 0
    ancora = Supplenza.query.filter_by(id=s.id).first()
    assert ancora is not None
    assert ancora.id_sostituto == sostituto.id  # non toccata


# ── Nessuna validità impostata: comportamento invariato ───────────

def test_genera_supplenze_senza_validita_funziona_come_prima(app, db_session):
    doc = crea_docente('Bianchi')
    _orario(doc.id, giorno=LUNEDI.weekday(), ora=3, classe='3A LSU')  # nessuna validità
    db.session.commit()

    assert validita_orario_corrente() == (None, None)
    n = _genera_supplenze(doc.id, LUNEDI, 1, 9, True, note_display='')
    assert n == 1
