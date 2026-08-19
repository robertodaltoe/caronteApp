"""
Test di regressione (Sessione 62, seguito): dopo aver corretto il primo
caso segnalato da Roberto (tendina assistenti prove agosto), un audit
ha trovato lo stesso bug — nessun filtro sull'anno di servizio
(anno_scol_inizio/anno_scol_uscita) — ripetuto in altri 4 punti:

1. modules/recupero_agosto_calendario.py::genera_bozza_agosto() — il
   generatore automatico poteva ASSEGNARE (non solo proporre) un
   docente non ancora arrivato come assistente.
2. routes/recupero_giugno.py::docenti() — la lista "non ancora
   iscritto" per i corsi di recupero di giugno.
3. routes/attivita_ist.py::_non_in_servizio_per_data() — preset
   partecipanti previsti per eventi istituzionali (collegio, CdC...).

(La quarta e quinta ricorrenza — routes/recupero_agosto.py — sono
coperte indirettamente perché usano la stessa funzione condivisa
routes/recupero_costanti.py::docenti_idonei_periodo(), già testata in
tests/test_recupero_agosto_calendario_dati.py.)
"""
from datetime import date

from models import db
from models.docente import Docente
from models.recupero import RecuperoPeriodo, RecuperoDocente, RecuperoGruppo, RecuperoAlunno

from tests.conftest import crea_docente, crea_periodo

ANNO_AGO = '2025-2026'
PERIODO_AGO = 'prove_agosto'


def _patch_anno(monkeypatch, anno_ago=ANNO_AGO, anno_giugno=None):
    import modules.recupero_agosto_calendario as mod_ago
    monkeypatch.setattr(mod_ago, 'ANNO_AGO', anno_ago)
    import routes.recupero_costanti as costanti
    monkeypatch.setattr(costanti, 'ANNO_AGO', anno_ago)
    if anno_giugno:
        monkeypatch.setattr(costanti, 'ANNO', anno_giugno)


def test_generatore_automatico_non_assegna_docente_non_ancora_arrivato(app, db_session, monkeypatch):
    """Un solo candidato possibile come assistente, e non è ancora in
    servizio: il generatore non deve assegnarlo comunque."""
    _patch_anno(monkeypatch)
    from routes.recupero_agosto import _genera_bozza_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24),
                 data_fine=date(2026, 8, 28))
    titolare = crea_docente('SOMMINISTRA', tipo_contratto='TI')
    non_ancora = crea_docente('NONARRIVATO', tipo_contratto='TI')
    non_ancora.anno_scol_inizio = '2026-2027'
    db.session.commit()

    rd = RecuperoDocente(id_docente=titolare.id, anno_scol=ANNO_AGO)
    db.session.add(rd)
    db.session.commit()
    g = RecuperoGruppo(id_rec_docente=rd.id, materia='MATEMATICA', classi='3ALSP',
                        periodo_codice=PERIODO_AGO, tipo_prova='scritto', durata_ore=2.0)
    db.session.add(g)
    db.session.commit()
    db.session.add(RecuperoAlunno(id_gruppo=g.id, classe='3ALSP', cognome='ALUNNO', nome='Test'))
    db.session.commit()

    _genera_bozza_agosto()

    g_dopo = db.session.get(RecuperoGruppo, g.id)
    assert g_dopo.id_sorvegliante != non_ancora.id


def test_giugno_lista_non_ancora_iscritti_esclude_non_arrivati(app, db_session, monkeypatch):
    _patch_anno(monkeypatch, anno_giugno='2025-2026')
    from routes.recupero_costanti import docenti_in_servizio_query

    disponibile = crea_docente('DISPONIBILEGIU')
    non_ancora = crea_docente('NONARRIVATOGIU')
    non_ancora.anno_scol_inizio = '2026-2027'
    db.session.commit()

    cognomi = {d.cognome for d in docenti_in_servizio_query('2025-2026').all()}
    assert 'DISPONIBILEGIU' in cognomi
    assert 'NONARRIVATOGIU' not in cognomi


def test_attivita_ist_esclude_docente_non_ancora_arrivato(app, db_session):
    from routes.attivita_ist import _non_in_servizio_per_data

    non_ancora = crea_docente('NONARRIVATOIST')
    non_ancora.anno_scol_inizio = '2026-2027'
    presente = crea_docente('PRESENTEIST')
    db.session.commit()

    esclusi = _non_in_servizio_per_data(date(2026, 5, 15))  # evento nel 2025-2026
    assert non_ancora.id in esclusi
    assert presente.id not in esclusi
