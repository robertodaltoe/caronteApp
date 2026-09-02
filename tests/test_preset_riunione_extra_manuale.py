"""
Trovato indagando la segnalazione di Roberto sulla "Riunione referenti
FSL": quella riunione è di tipo 'riunione_extra' ("Commissione, Staff o
altro gruppo ad hoc — titolo libero scelto da Roberto", vedi
models/attivita_ist.py TIPI_ATTIVITA) — un tipo pensato per essere
sempre composto a mano, senza logica automatica sensata (non è legato
a una classe né a un dipartimento né "tutti").

_preset_partecipanti() non aveva un branch dedicato: 'riunione_extra'
cadeva nel ramo else generico, che ritorna "tutti i docenti attivi".
Roberto aveva scelto a mano i suoi 9 referenti; una risincronizzazione
ha convocato in automatico tutti e 64 i docenti attivi dell'istituto.

Fix: nuovo branch esplicito, preset sempre vuoto (come già per GLO
senza classe) — nessuna proposta automatica per questo tipo.
"""
from datetime import date, timedelta
from models.attivita_ist import AttivitaIst

FUTURO = date.today() + timedelta(days=30)


def test_riunione_extra_non_propone_mai_tutti_i_docenti(app, db_session):
    from tests.conftest import crea_docente
    crea_docente('Rossi')
    crea_docente('Bianchi')
    crea_docente('Verdi')

    from routes.attivita_ist import _preset_partecipanti
    ev = AttivitaIst(tipo='riunione_extra', titolo='Riunione referenti FSL',
                      data=FUTURO, origine='manuale')

    assert _preset_partecipanti(ev) == []
