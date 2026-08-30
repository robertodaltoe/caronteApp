"""
Roberto: nell'elenco eventi, le riunioni di dipartimento/materia
compaiono una per dipartimento anche quando sono tutte allo stesso
orario — vuole un'unica riga generica ("Riunione dipartimento"/
"Riunione per materia") quando l'orario coincide, righe separate (col
proprio dipartimento nel titolo, comportamento già esistente) quando
gli orari sono diversi.

routes/attivita_ist.py::_raggruppa_eventi_dipartimento() è una
compattazione di sola vista: non tocca il DB, i singoli AttivitaIst
restano invariati e accessibili tramite .eventi del wrapper "gruppo".
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.materia import Dipartimento
from tests.conftest import crea_docente


def _crea_dip(sigla, nome=None):
    d = Dipartimento(sigla=sigla, nome=nome or sigla, ordine=1)
    db.session.add(d)
    db.session.commit()
    return d


def _crea_evento(tipo, dip, data, ora_ini, ora_fin, docenti=()):
    ev = AttivitaIst(tipo=tipo, titolo=f'Riunione dipartimento {dip.sigla}',
                      data=data, ora_inizio=ora_ini, ora_fine=ora_fin,
                      id_dipartimento=dip.id, origine='import_piano')
    db.session.add(ev)
    db.session.flush()
    for d in docenti:
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id))
    db.session.commit()
    return ev


def test_stesso_orario_compattato_in_un_solo_gruppo(app, db_session):
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    let = _crea_dip('LET')
    mat = _crea_dip('MAT')
    sci = _crea_dip('SCI')
    e1 = _crea_evento('dipartimento', let, date(2026, 10, 6), '15:00', '16:00')
    e2 = _crea_evento('dipartimento', mat, date(2026, 10, 6), '15:00', '16:00')
    e3 = _crea_evento('dipartimento', sci, date(2026, 10, 6), '15:00', '16:00')

    risultato = _raggruppa_eventi_dipartimento([e1, e2, e3])

    assert len(risultato) == 1
    g = risultato[0]
    assert g.is_gruppo is True
    assert set(x.id for x in g.eventi) == {e1.id, e2.id, e3.id}
    assert sorted(g.sigle_dipartimenti) == ['LET', 'MAT', 'SCI']
    assert 'Riunione dipartimento' in g.titolo
    assert '3' in g.titolo


def test_orari_diversi_restano_separati(app, db_session):
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    let = _crea_dip('LET')
    mat = _crea_dip('MAT')
    e1 = _crea_evento('dipartimento', let, date(2026, 10, 6), '15:00', '16:00')
    e2 = _crea_evento('dipartimento', mat, date(2026, 10, 6), '16:30', '17:30')

    risultato = _raggruppa_eventi_dipartimento([e1, e2])

    assert risultato == [e1, e2]
    assert not any(getattr(r, 'is_gruppo', False) for r in risultato)


def test_riunione_referenti_stesso_orario_compattata(app, db_session):
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    let = _crea_dip('LET')
    mat = _crea_dip('MAT')
    e1 = _crea_evento('riunione_referenti', let, date(2026, 10, 6), '15:00', '16:00')
    e2 = _crea_evento('riunione_referenti', mat, date(2026, 10, 6), '15:00', '16:00')

    risultato = _raggruppa_eventi_dipartimento([e1, e2])

    assert len(risultato) == 1
    g = risultato[0]
    assert g.is_gruppo is True
    assert 'Riunione referenti' in g.titolo
    assert sorted(g.sigle_dipartimenti) == ['LET', 'MAT']


def test_riunione_materia_non_si_mescola_con_dipartimento_anche_a_stesso_orario(app, db_session):
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    let = _crea_dip('LET')
    mat = _crea_dip('MAT')
    e1 = _crea_evento('dipartimento', let, date(2026, 10, 6), '15:00', '16:00')
    e2 = _crea_evento('riunione_materia', mat, date(2026, 10, 6), '15:00', '16:00')

    risultato = _raggruppa_eventi_dipartimento([e1, e2])

    assert risultato == [e1, e2]


def test_eventi_non_dipartimentali_non_vengono_toccati(app, db_session):
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    e1 = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    e2 = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add_all([e1, e2])
    db.session.commit()

    risultato = _raggruppa_eventi_dipartimento([e1, e2])
    assert risultato == [e1, e2]


def test_partecipanti_del_gruppo_sono_lunione_dei_singoli(app, db_session):
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    let = _crea_dip('LET')
    mat = _crea_dip('MAT')
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    d3 = crea_docente('Verdi')
    e1 = _crea_evento('dipartimento', let, date(2026, 10, 6), '15:00', '16:00', docenti=[d1, d2])
    e2 = _crea_evento('dipartimento', mat, date(2026, 10, 6), '15:00', '16:00', docenti=[d3])

    risultato = _raggruppa_eventi_dipartimento([e1, e2])
    g = risultato[0]
    assert len(g.partecipanti) == 3


def test_singolo_dipartimento_in_uno_slot_non_viene_raggruppato(app, db_session):
    """Un solo evento per quella chiave (giorno+orario) non ha senso
    "raggrupparlo": deve restare l'evento originale, non un wrapper."""
    from routes.attivita_ist import _raggruppa_eventi_dipartimento
    let = _crea_dip('LET')
    e1 = _crea_evento('dipartimento', let, date(2026, 10, 6), '15:00', '16:00')

    risultato = _raggruppa_eventi_dipartimento([e1])
    assert risultato == [e1]
