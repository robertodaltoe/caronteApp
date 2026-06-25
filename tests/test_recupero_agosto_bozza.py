"""
Test per _genera_bozza_agosto: il generatore di calendario per le prove
di recupero di agosto. Verifica i comportamenti critici corretti più
volte a mano durante lo sviluppo:
- nessuna sovrapposizione tra gruppi che condividono titolare/assistente/alunni
- rispetto del limite massimo di prove in contemporanea (4)
- la modalità "completa bozza" (solo_incompleti=True) non sovrascrive
  i gruppi già pianificati
"""
from datetime import date
from models import db
from models.docente import Docente
from models.recupero import RecuperoPeriodo, RecuperoDocente, RecuperoGruppo, RecuperoLezione, RecuperoAlunno

from tests.conftest import crea_docente, crea_periodo

ANNO_AGO = '2025-2026'
PERIODO_AGO = 'prove_agosto'


def _crea_rec_docente(docente):
    rd = RecuperoDocente(id_docente=docente.id, anno_scol=ANNO_AGO)
    db.session.add(rd)
    db.session.commit()
    return rd


def _crea_gruppo(rec_docente, materia, classi, tipo_prova='scritto', durata_ore=2.0,
                  id_sorvegliante=None, n_alunni=2):
    g = RecuperoGruppo(id_rec_docente=rec_docente.id, materia=materia, classi=classi,
                        periodo_codice=PERIODO_AGO, tipo_prova=tipo_prova,
                        durata_ore=durata_ore, id_sorvegliante=id_sorvegliante)
    db.session.add(g)
    db.session.commit()
    for i in range(n_alunni):
        db.session.add(RecuperoAlunno(id_gruppo=g.id, classe=classi.split(',')[0].strip(),
                                       cognome=f'ALUNNO{i}', nome='Test'))
    db.session.commit()
    return g


def test_nessun_periodo_non_genera_nulla(app, db_session):
    from routes.recupero import _genera_bozza_agosto

    doc = crea_docente('ROSSI')
    rd = _crea_rec_docente(doc)
    g = _crea_gruppo(rd, 'MATEMATICA', '3ALSP')

    _genera_bozza_agosto()

    g_dopo = db.session.get(RecuperoGruppo, g.id)
    assert len(g_dopo.lezioni) == 0


def test_piazza_gruppo_semplice(app, db_session):
    """Un gruppo scritto con titolare e assistente impostati deve
    ricevere una lezione dentro il periodo configurato."""
    from routes.recupero import _genera_bozza_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24),
                 data_fine=date(2026, 8, 28))
    titolare = crea_docente('ROSSI')
    assistente = crea_docente('BIANCHI')
    rd = _crea_rec_docente(titolare)
    g = _crea_gruppo(rd, 'MATEMATICA', '3ALSP', id_sorvegliante=assistente.id)

    _genera_bozza_agosto()

    g_dopo = db.session.get(RecuperoGruppo, g.id)
    assert len(g_dopo.lezioni) == 1
    lez = g_dopo.lezioni[0]
    assert date(2026, 8, 24) <= lez.data <= date(2026, 8, 28)


def test_due_gruppi_stesso_titolare_non_si_sovrappongono(app, db_session):
    """Se due gruppi condividono il titolare, le loro lezioni non
    devono avere lo stesso giorno+orario."""
    from routes.recupero import _genera_bozza_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24),
                 data_fine=date(2026, 8, 28))
    titolare_comune = crea_docente('ROSSI')
    assistente1 = crea_docente('BIANCHI')
    assistente2 = crea_docente('VERDI')
    rd = _crea_rec_docente(titolare_comune)

    g1 = _crea_gruppo(rd, 'MATEMATICA', '3ALSP', id_sorvegliante=assistente1.id)
    g2 = _crea_gruppo(rd, 'MATEMATICA', '4ALSP', id_sorvegliante=assistente2.id)

    _genera_bozza_agosto()

    l1 = db.session.get(RecuperoGruppo, g1.id).lezioni[0]
    l2 = db.session.get(RecuperoGruppo, g2.id).lezioni[0]

    def _to_min(s):
        h, m = map(int, s.split(':'))
        return h * 60 + m

    if l1.data == l2.data:
        ini1, fin1 = _to_min(l1.ora_inizio), _to_min(l1.ora_fine)
        ini2, fin2 = _to_min(l2.ora_inizio), _to_min(l2.ora_fine)
        assert fin1 <= ini2 or fin2 <= ini1


def test_due_gruppi_stessi_alunni_non_si_sovrappongono(app, db_session):
    """Se due gruppi condividono almeno un alunno (stessa classe+nome+
    cognome), non devono avere lo stesso slot, anche con docenti diversi."""
    from routes.recupero import _genera_bozza_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24),
                 data_fine=date(2026, 8, 24), ora_inizio='08:00', ora_fine='10:00')

    tit1 = crea_docente('ROSSI')
    tit2 = crea_docente('NERI')
    rd1 = _crea_rec_docente(tit1)
    rd2 = _crea_rec_docente(tit2)

    g1 = RecuperoGruppo(id_rec_docente=rd1.id, materia='MATEMATICA', classi='3ALSP',
                         periodo_codice=PERIODO_AGO, tipo_prova='scritto', durata_ore=2.0)
    db.session.add(g1)
    db.session.commit()
    db.session.add(RecuperoAlunno(id_gruppo=g1.id, classe='3ALSP', cognome='STUDENTE', nome='Unico'))

    g2 = RecuperoGruppo(id_rec_docente=rd2.id, materia='FISICA', classi='3ALSP',
                         periodo_codice=PERIODO_AGO, tipo_prova='scritto', durata_ore=2.0)
    db.session.add(g2)
    db.session.commit()
    db.session.add(RecuperoAlunno(id_gruppo=g2.id, classe='3ALSP', cognome='STUDENTE', nome='Unico'))
    db.session.commit()

    _genera_bozza_agosto()

    g1_dopo = db.session.get(RecuperoGruppo, g1.id)
    g2_dopo = db.session.get(RecuperoGruppo, g2.id)

    # Con un periodo cosi' ristretto (un solo giorno, 2 ore), se entrambi
    # i gruppi fossero piazzati dovrebbero condividere lo slot — verifica
    # che non accada per via dello stesso alunno in comune.
    if g1_dopo.lezioni and g2_dopo.lezioni:
        l1, l2 = g1_dopo.lezioni[0], g2_dopo.lezioni[0]
        assert not (l1.data == l2.data and l1.ora_inizio == l2.ora_inizio)


def test_completa_bozza_non_tocca_gruppo_gia_pianificato(app, db_session):
    """solo_incompleti=True non deve modificare un gruppo che ha già una
    lezione pianificata, ma deve comunque piazzare gli altri."""
    from routes.recupero import _genera_bozza_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24),
                 data_fine=date(2026, 8, 28))

    tit1 = crea_docente('ROSSI')
    tit2 = crea_docente('NERI')
    rd1 = _crea_rec_docente(tit1)
    rd2 = _crea_rec_docente(tit2)

    g1 = _crea_gruppo(rd1, 'MATEMATICA', '3ALSP')
    g2 = _crea_gruppo(rd2, 'FISICA', '4ALSP')

    # Pianifica manualmente g1
    db.session.add(RecuperoLezione(id_gruppo=g1.id, data=date(2026, 8, 25),
                                    ora_inizio='10:30', ora_fine='12:30'))
    db.session.commit()

    _genera_bozza_agosto(solo_incompleti=True)

    g1_dopo = db.session.get(RecuperoGruppo, g1.id)
    g2_dopo = db.session.get(RecuperoGruppo, g2.id)

    # g1 deve avere ESATTAMENTE la lezione manuale, non altre aggiunte
    assert len(g1_dopo.lezioni) == 1
    assert g1_dopo.lezioni[0].data == date(2026, 8, 25)
    assert g1_dopo.lezioni[0].ora_inizio == '10:30'

    # g2 era vuoto: deve essere stato piazzato
    assert len(g2_dopo.lezioni) >= 1


def test_max_quattro_prove_parallele(app, db_session):
    """Non devono mai esistere più di 4 prove in contemporanea nello
    stesso giorno+orario, anche con molti gruppi indipendenti (docenti e
    alunni tutti diversi tra loro, quindi nessun vincolo li separerebbe
    a parte il limite di parallelismo)."""
    from routes.recupero import _genera_bozza_agosto
    from collections import Counter

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24),
                 data_fine=date(2026, 8, 24), ora_inizio='08:00', ora_fine='10:00')

    gruppi_creati = []
    for i in range(8):
        tit = crea_docente(f'DOC{i}')
        rd = _crea_rec_docente(tit)
        g = RecuperoGruppo(id_rec_docente=rd.id, materia='MATEMATICA', classi=f'{i}ALSP',
                            periodo_codice=PERIODO_AGO, tipo_prova='scritto', durata_ore=2.0)
        db.session.add(g)
        db.session.commit()
        db.session.add(RecuperoAlunno(id_gruppo=g.id, classe=f'{i}ALSP',
                                       cognome=f'ALUNNO{i}', nome='Test'))
        db.session.commit()
        gruppi_creati.append(g)

    _genera_bozza_agosto()

    slot_counter = Counter()
    for g in gruppi_creati:
        g_dopo = db.session.get(RecuperoGruppo, g.id)
        for l in g_dopo.lezioni:
            slot_counter[(l.data, l.ora_inizio, l.ora_fine)] += 1

    assert slot_counter, "nessuna lezione piazzata: il test non sta verificando nulla"
    assert max(slot_counter.values()) <= 4
