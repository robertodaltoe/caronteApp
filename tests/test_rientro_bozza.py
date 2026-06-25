"""
Test per _genera_bozza_rientro: il generatore di calendario per i
colloqui di rientro dall'estero. Verifica i comportamenti critici che
sono già stati corretti a mano più volte durante lo sviluppo:
- nessuna sovrapposizione tra colloqui che condividono un membro
- nessuna sovrapposizione con le prove di agosto (lettura cross-modulo)
- la modalità "completa bozza" (solo_vuoti=True) non toglie un orario
  già assegnato manualmente
"""
from datetime import date
from models import db
from models.docente import Docente
from models.recupero import RecuperoPeriodo, RecuperoDocente, RecuperoGruppo, RecuperoLezione
from models.rientro import RientroMateriaClasse, RientroCandidato, RientroColloquio

from tests.conftest import crea_docente, crea_periodo

ANNO = '2025-2026'


def _crea_candidato(classe, cognome, nome='Test'):
    c = RientroCandidato(anno_scol=ANNO, cognome=cognome, nome=nome, classe=classe)
    db.session.add(c)
    db.session.commit()
    return c


def _crea_colloquio_con_membri(candidato, docenti):
    """Crea un RientroColloquio collegato al candidato, con i docenti
    passati come membri (docente_1..4), senza data/ora."""
    coll = RientroColloquio(id_candidato=candidato.id)
    for i, d in enumerate(docenti[:4], start=1):
        setattr(coll, f'id_docente_{i}', d.id)
    db.session.add(coll)
    db.session.commit()
    return coll


def test_nessun_periodo_non_genera_nulla(app, db_session):
    """Senza un RecuperoPeriodo con codice 'colloqui_rientro', la funzione
    deve uscire senza errori e senza piazzare nulla."""
    from routes.rientro import _genera_bozza_rientro

    doc = crea_docente('ROSSI')
    cand = _crea_candidato('3ALSP', 'BIANCHI')
    _crea_colloquio_con_membri(cand, [doc])

    _genera_bozza_rientro()

    coll = RientroColloquio.query.filter_by(id_candidato=cand.id).first()
    assert coll.data is None


def test_piazza_un_candidato_con_commissione_completa(app, db_session):
    """Un candidato con almeno un membro commissione deve ricevere una
    data/ora valida dentro il periodo configurato."""
    from routes.rientro import _genera_bozza_rientro

    crea_periodo('colloqui_rientro', data_inizio=date(2026, 8, 27), data_fine=date(2026, 8, 28))
    doc = crea_docente('ROSSI')
    cand = _crea_candidato('3ALSP', 'BIANCHI')
    _crea_colloquio_con_membri(cand, [doc])

    _genera_bozza_rientro()

    coll = RientroColloquio.query.filter_by(id_candidato=cand.id).first()
    assert coll.data in (date(2026, 8, 27), date(2026, 8, 28))
    assert coll.ora_inizio is not None
    assert coll.ora_fine is not None


def test_candidato_senza_commissione_non_viene_piazzato(app, db_session):
    """Un candidato senza nessun docente assegnato alla commissione deve
    restare senza data — non si può calendarizzare un colloquio vuoto."""
    from routes.rientro import _genera_bozza_rientro

    crea_periodo('colloqui_rientro', data_inizio=date(2026, 8, 27), data_fine=date(2026, 8, 28))
    cand = _crea_candidato('3ALSP', 'BIANCHI')
    coll = RientroColloquio(id_candidato=cand.id)  # nessun membro
    db.session.add(coll)
    db.session.commit()

    _genera_bozza_rientro()

    coll = RientroColloquio.query.filter_by(id_candidato=cand.id).first()
    assert coll.data is None


def test_due_candidati_stesso_docente_non_si_sovrappongono(app, db_session):
    """Se due candidati condividono un membro della commissione, i loro
    slot orari non devono mai sovrapporsi."""
    from routes.rientro import _genera_bozza_rientro

    crea_periodo('colloqui_rientro', data_inizio=date(2026, 8, 27), data_fine=date(2026, 8, 28),
                 ora_inizio='08:00', ora_fine='13:00')
    doc_comune = crea_docente('ROSSI')

    cand1 = _crea_candidato('3ALSP', 'BIANCHI')
    cand2 = _crea_candidato('3ALSP', 'VERDI')
    _crea_colloquio_con_membri(cand1, [doc_comune])
    _crea_colloquio_con_membri(cand2, [doc_comune])

    _genera_bozza_rientro()

    c1 = RientroColloquio.query.filter_by(id_candidato=cand1.id).first()
    c2 = RientroColloquio.query.filter_by(id_candidato=cand2.id).first()
    assert c1.data is not None and c2.data is not None

    def _to_min(s):
        h, m = map(int, s.split(':'))
        return h * 60 + m

    if c1.data == c2.data:
        ini1, fin1 = _to_min(c1.ora_inizio), _to_min(c1.ora_fine)
        ini2, fin2 = _to_min(c2.ora_inizio), _to_min(c2.ora_fine)
        # Non devono sovrapporsi: uno finisce prima che l'altro inizi
        assert fin1 <= ini2 or fin2 <= ini1


def test_conflitto_con_prova_agosto_stesso_docente(app, db_session):
    """Se un docente è già impegnato in una prova di recupero di agosto
    in un certo slot, il colloquio rientro con lo stesso docente non deve
    essere piazzato in quello stesso slot."""
    from routes.rientro import _genera_bozza_rientro

    # Periodo rientro: un solo giorno con una sola fascia oraria minima,
    # cosi' l'unico slot disponibile è quello occupato dalla prova agosto.
    crea_periodo('colloqui_rientro', data_inizio=date(2026, 8, 27), data_fine=date(2026, 8, 27),
                 ora_inizio='08:00', ora_fine='08:45')

    doc = crea_docente('ROSSI')

    # Costruisce un gruppo prova agosto che occupa l'intera (unica) fascia
    # disponibile, con lo stesso docente come titolare ("somministratore").
    rec_doc = RecuperoDocente(id_docente=doc.id, anno_scol=ANNO)
    db.session.add(rec_doc)
    db.session.commit()

    gruppo_ago = RecuperoGruppo(id_rec_docente=rec_doc.id, materia='MATEMATICA',
                                 classi='3ALSP', periodo_codice='prove_agosto')
    db.session.add(gruppo_ago)
    db.session.commit()

    lezione_ago = RecuperoLezione(id_gruppo=gruppo_ago.id, data=date(2026, 8, 27),
                                   ora_inizio='08:00', ora_fine='08:45')
    db.session.add(lezione_ago)
    db.session.commit()

    cand = _crea_candidato('3ALSP', 'BIANCHI')
    _crea_colloquio_con_membri(cand, [doc])

    _genera_bozza_rientro()

    coll = RientroColloquio.query.filter_by(id_candidato=cand.id).first()
    # L'unico slot del periodo è occupato dalla prova di agosto con lo
    # stesso docente: il colloquio non deve essere piazzato.
    assert coll.data is None


def test_completa_bozza_non_tocca_colloquio_esistente(app, db_session):
    """solo_vuoti=True non deve modificare un colloquio che ha già
    data/ora impostate manualmente."""
    from routes.rientro import _genera_bozza_rientro

    crea_periodo('colloqui_rientro', data_inizio=date(2026, 8, 27), data_fine=date(2026, 8, 28),
                 ora_inizio='08:00', ora_fine='13:00')
    doc1 = crea_docente('ROSSI')
    doc2 = crea_docente('VERDI')

    cand1 = _crea_candidato('3ALSP', 'BIANCHI')
    coll1 = _crea_colloquio_con_membri(cand1, [doc1])
    # Imposta manualmente data/ora — simula un inserimento fatto a mano
    coll1.data = date(2026, 8, 27)
    coll1.ora_inizio = '10:30'
    coll1.ora_fine = '11:15'
    db.session.commit()

    cand2 = _crea_candidato('3ALSP', 'VERDI_C')
    _crea_colloquio_con_membri(cand2, [doc2])

    _genera_bozza_rientro(solo_vuoti=True)

    coll1_dopo = RientroColloquio.query.filter_by(id_candidato=cand1.id).first()
    assert coll1_dopo.data == date(2026, 8, 27)
    assert coll1_dopo.ora_inizio == '10:30'
    assert coll1_dopo.ora_fine == '11:15'

    coll2_dopo = RientroColloquio.query.filter_by(id_candidato=cand2.id).first()
    assert coll2_dopo.data is not None
