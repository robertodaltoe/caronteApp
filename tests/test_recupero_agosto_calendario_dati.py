"""
Test di regressione per costruisci_dati_agosto() (Sessione 62):
Roberto segnala due problemi sulla pagina /recupero/agosto/calendario.

1. La tendina "Docente assistente" mostrava anche docenti non ancora in
   servizio (anno_scol_inizio nell'anno successivo, arrivano dopo le
   prove) e con contratto già scaduto — mancava del tutto il filtro per
   anno scolastico che altrove nell'app già esiste (_docenti_per_anno).
2. Un'assenza registrata DOPO l'assegnazione di un docente come
   assistente a una prova non dava alcun riscontro — nessun controllo
   incrociava le assegnazioni con il registro assenze.
"""
from datetime import date

from models import db
from models.docente import Docente
from models.assenza import Assenza
from models.recupero import RecuperoPeriodo, RecuperoDocente, RecuperoGruppo, RecuperoLezione, RecuperoAlunno

from tests.conftest import crea_docente, crea_periodo

ANNO_AGO = '2025-2026'
PERIODO_AGO = 'prove_agosto'


def _patch_anno_ago(monkeypatch):
    """Fissa ANNO_AGO nel modulo sotto test, invece di dipendere da
    get_anno_corrente() (che cambia con la data reale) — stesso problema
    di fondo per cui esiste ANNO_AGO stesso (congelato a import-time),
    qui lo fissiamo esplicitamente per un test deterministico."""
    import modules.recupero_agosto_calendario as mod
    monkeypatch.setattr(mod, 'ANNO_AGO', ANNO_AGO)


def _crea_rec_docente(docente, anno_scol=ANNO_AGO):
    rd = RecuperoDocente(id_docente=docente.id, anno_scol=anno_scol)
    db.session.add(rd)
    db.session.commit()
    return rd


def _crea_gruppo_con_lezione(rec_docente, materia, id_sorvegliante, data_lez,
                              ora_inizio='08:00', ora_fine='10:00'):
    g = RecuperoGruppo(id_rec_docente=rec_docente.id, materia=materia, classi='3ALSP',
                        periodo_codice=PERIODO_AGO, tipo_prova='scritto',
                        durata_ore=2.0, id_sorvegliante=id_sorvegliante)
    db.session.add(g)
    db.session.commit()
    db.session.add(RecuperoAlunno(id_gruppo=g.id, classe='3ALSP', cognome='ALUNNO', nome='Test'))
    db.session.add(RecuperoLezione(id_gruppo=g.id, data=data_lez,
                                    ora_inizio=ora_inizio, ora_fine=ora_fine))
    db.session.commit()
    return g


def test_docente_non_ancora_in_servizio_escluso_dalla_tendina(app, db_session, monkeypatch):
    _patch_anno_ago(monkeypatch)
    from modules.recupero_agosto_calendario import costruisci_dati_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24), data_fine=date(2026, 8, 28))
    in_servizio = crea_docente('DISPONIBILE', tipo_contratto='TI')
    non_ancora = crea_docente('NUOVOARRIVO', tipo_contratto='TI')
    non_ancora.anno_scol_inizio = '2026-2027'  # arriva dopo le prove di agosto
    db.session.commit()

    dati = costruisci_dati_agosto()
    cognomi = {d.cognome for d in dati['docenti_validi']}
    assert 'DISPONIBILE' in cognomi
    assert 'NUOVOARRIVO' not in cognomi


def test_docente_con_contratto_scaduto_escluso_dalla_tendina(app, db_session, monkeypatch):
    _patch_anno_ago(monkeypatch)
    from modules.recupero_agosto_calendario import costruisci_dati_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24), data_fine=date(2026, 8, 28))
    scaduto = crea_docente('USCITO', tipo_contratto='TD_annuale')
    scaduto.anno_scol_uscita = ANNO_AGO  # esce alla fine di questo stesso anno
    db.session.commit()

    dati = costruisci_dati_agosto()
    cognomi = {d.cognome for d in dati['docenti_validi']}
    assert 'USCITO' not in cognomi


def test_assenza_dopo_assegnazione_genera_conflitto(app, db_session, monkeypatch):
    _patch_anno_ago(monkeypatch)
    from modules.recupero_agosto_calendario import costruisci_dati_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24), data_fine=date(2026, 8, 28))
    titolare = crea_docente('SOMMINISTRA')
    assistente = crea_docente('SANTAGATATEST')
    rd = _crea_rec_docente(titolare)
    data_prova = date(2026, 8, 26)
    _crea_gruppo_con_lezione(rd, 'LATINO', assistente.id, data_prova)

    # Assenza registrata DOPO l'assegnazione (nell'ordine cronologico
    # reale: prima si assegna l'assistente, poi arriva la notizia
    # dell'assenza) — qui l'ordine di creazione non conta per la query,
    # ma rispecchia lo scenario segnalato.
    db.session.add(Assenza(id_docente=assistente.id, data=data_prova,
                            ora_inizio=1, ora_fine=9, motivo='malattia'))
    db.session.commit()

    dati = costruisci_dati_agosto()
    conflitti_assenza = [c for c in dati['conflitti'] if c['tipo'] == 'assenza']
    assert len(conflitti_assenza) == 1
    assert 'SANTAGATATEST' in conflitti_assenza[0]['msg']
    assert conflitti_assenza[0]['data'] == data_prova


def test_nessuna_assenza_nessun_conflitto(app, db_session, monkeypatch):
    _patch_anno_ago(monkeypatch)
    from modules.recupero_agosto_calendario import costruisci_dati_agosto

    crea_periodo(PERIODO_AGO, anno_scol=ANNO_AGO, data_inizio=date(2026, 8, 24), data_fine=date(2026, 8, 28))
    titolare = crea_docente('SOMMINISTRA2')
    assistente = crea_docente('PRESENTE')
    rd = _crea_rec_docente(titolare)
    _crea_gruppo_con_lezione(rd, 'LATINO', assistente.id, date(2026, 8, 26))

    dati = costruisci_dati_agosto()
    conflitti_assenza = [c for c in dati['conflitti'] if c['tipo'] == 'assenza']
    assert conflitti_assenza == []
