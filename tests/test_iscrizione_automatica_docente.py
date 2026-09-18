"""
Un docente nuovo/riattivato deve iscriversi automaticamente agli eventi
istituzionali futuri "per tutti" già esistenti — altrimenti resterebbe
escluso da eventi creati prima che esistesse in anagrafica, dato che il
preset viene calcolato solo alla creazione/modifica dell'evento.
Vedi routes/attivita_ist.py::iscrivi_docente_a_obbligatori.

Ambito ristretto su richiesta esplicita di Roberto (solo le riunioni
collegiali "per tutti" in senso stretto): Collegio e incontro con le
famiglie restano automatici; 'altro' e Formazione (anche quella
obbligatoria) no — l'iscrizione a un corso resta sempre una scelta
individuale, mai preimpostata.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.formazione import CorsoFormazione
from routes.attivita_ist import iscrivi_docente_a_obbligatori
from tests.conftest import crea_docente

DOMANI = date.today() + timedelta(days=10)
IERI   = date.today() - timedelta(days=10)


def _evento(tipo, data=DOMANI, classe=None, id_dipartimento=None):
    ev = AttivitaIst(tipo=tipo, titolo=f'Evento {tipo}', data=data,
                      classe=classe, id_dipartimento=id_dipartimento,
                      origine='manuale')
    db.session.add(ev)
    db.session.commit()
    return ev


def test_docente_nuovo_si_iscrive_a_collegio_futuro(db_session):
    ev = _evento('collegio')
    d = crea_docente('Rossi')
    n = iscrivi_docente_a_obbligatori(d)
    assert n == 1
    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev.id, id_docente=d.id).first() is not None


def test_docente_non_si_iscrive_a_collegio_passato(db_session):
    _evento('collegio', data=IERI)
    d = crea_docente('Bianchi')
    n = iscrivi_docente_a_obbligatori(d)
    assert n == 0


def test_docente_si_iscrive_a_incontro_famiglie_ma_non_a_altro(db_session):
    ev_incontro = _evento('incontro_famiglie')
    _evento('altro')
    d = crea_docente('Verdi')
    n = iscrivi_docente_a_obbligatori(d)
    assert n == 1
    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev_incontro.id, id_docente=d.id).first() is not None


def test_docente_non_si_iscrive_a_consiglio_classe_o_dipartimento(db_session):
    """Eventi scoped su classe/dipartimento restano fuori: dipendono da
    orario/assegnazioni che un docente appena creato non ha ancora."""
    _evento('consiglio_classe', classe='3ALLI')
    _evento('glo')
    d = crea_docente('Neri')
    n = iscrivi_docente_a_obbligatori(d)
    assert n == 0


def test_docente_non_si_iscrive_a_corso_formazione_anche_se_obbligatorio(db_session):
    """Richiesta esplicita di Roberto: la Formazione, anche quella
    'obbligatoria per tutti', non si iscrive mai in automatico --
    resta sempre una scelta individuale del singolo docente."""
    ev = AttivitaIst(tipo='formazione', titolo='Sicurezza', data=DOMANI,
                      durata_min=30, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(CorsoFormazione(
        id_attivita=ev.id, titolo='Sicurezza', _ore_legacy=0.5, modalita='presenza',
        data_inizio=DOMANI, data_fine=DOMANI, obbligatorio_tutti=True,
        anno_scol='2026-2027'))
    db.session.commit()

    d = crea_docente('Gialli')
    n = iscrivi_docente_a_obbligatori(d)
    assert n == 0


def test_docente_non_si_iscrive_a_corso_formazione_volontario(db_session):
    ev = AttivitaIst(tipo='formazione', titolo='Corso libero', data=DOMANI,
                      durata_min=60, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(CorsoFormazione(
        id_attivita=ev.id, titolo='Corso libero', _ore_legacy=1, modalita='online',
        data_inizio=DOMANI, data_fine=DOMANI, obbligatorio_tutti=False,
        anno_scol='2026-2027'))
    db.session.commit()

    d = crea_docente('Azzurri')
    n = iscrivi_docente_a_obbligatori(d)
    assert n == 0


def test_non_duplica_se_gia_iscritto(db_session):
    ev = _evento('collegio')
    d = crea_docente('Marroni')
    db.session.add(AttivitaIstPartecipante(
        id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    n = iscrivi_docente_a_obbligatori(d)
    assert n == 0
    assert AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).count() == 1
