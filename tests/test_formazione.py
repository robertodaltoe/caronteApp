"""
Piano della Formazione (Piano Annuale delle Attività, Fase 1):
ogni corso genera un evento AttivitaIst collegato (bucket A), le
iscrizioni sono le righe AttivitaIstPartecipante di quell'evento.
"""
from datetime import date
from models import db
from models.formazione import CorsoFormazione
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente


def _crea_corso(obbligatorio=False, docenti=None, ore=4):
    from routes.formazione import _anno_scolastico
    ev = AttivitaIst(tipo='formazione', titolo='Corso test', data=date(2026, 11, 10),
                      durata_min=int(ore * 60), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    corso = CorsoFormazione(
        id_attivita=ev.id, titolo='Corso test', tipologia='test', _ore_legacy=ore,
        modalita='presenza', data_inizio=date(2026, 11, 10), data_fine=date(2026, 11, 10),
        obbligatorio_tutti=obbligatorio, anno_scol='2026-2027',
    )
    db.session.add(corso)
    db.session.flush()
    if obbligatorio and docenti:
        for d in docenti:
            db.session.add(AttivitaIstPartecipante(
                id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()
    return corso


def test_evento_collegato_e_bucket_a(db_session):
    corso = _crea_corso()
    assert corso.attivita.tipo == 'formazione'
    assert corso.attivita.bucket == 'A'
    assert corso.attivita.durata_min == 240


def test_corso_obbligatorio_ha_partecipanti(db_session):
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    corso = _crea_corso(obbligatorio=True, docenti=[d1, d2])
    assert corso.n_iscritti == 2


def test_corso_volontario_parte_senza_iscritti(db_session):
    d1 = crea_docente('Verdi')
    corso = _crea_corso(obbligatorio=False)
    assert corso.n_iscritti == 0


def test_iscrizione_e_disiscrizione_sono_righe_partecipante(db_session):
    d1 = crea_docente('Neri')
    corso = _crea_corso(obbligatorio=False)

    db.session.add(AttivitaIstPartecipante(
        id_attivita=corso.id_attivita, id_docente=d1.id, preset=False))
    db.session.commit()
    assert corso.n_iscritti == 1

    AttivitaIstPartecipante.query.filter_by(
        id_attivita=corso.id_attivita, id_docente=d1.id).delete()
    db.session.commit()
    assert corso.n_iscritti == 0


def test_eliminazione_corso_non_elimina_da_sola_evento_collegato(db_session):
    """La cascade di AttivitaIst->partecipanti è indipendente: il codice
    applicativo (routes/formazione.py::elimina) deve eliminare esplicitamente
    anche l'evento, altrimenti resterebbe orfano — qui si verifica solo che
    il modello stesso non impedisca l'eliminazione separata delle due righe."""
    corso = _crea_corso()
    id_evento = corso.id_attivita
    db.session.delete(corso)
    db.session.commit()
    # L'evento collegato sopravvive finché non viene eliminato esplicitamente
    assert AttivitaIst.query.get(id_evento) is not None
    db.session.delete(AttivitaIst.query.get(id_evento))
    db.session.commit()
    assert AttivitaIst.query.get(id_evento) is None


def test_periodo_label_giorno_singolo_vs_intervallo(db_session):
    corso = _crea_corso()
    assert '–' not in corso.periodo_label  # un solo giorno

    corso2 = CorsoFormazione(
        id_attivita=corso.id_attivita, titolo='Corso lungo', tipologia=None,
        _ore_legacy=10, modalita='online', data_inizio=date(2027, 1, 15),
        data_fine=date(2027, 1, 20), obbligatorio_tutti=False, anno_scol='2026-2027',
    )
    assert '–' in corso2.periodo_label
