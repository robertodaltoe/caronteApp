"""
Generatore Consigli di Classe (Piano Annuale delle Attività, Fase 3).
Test sulla logica pura di modules/generatore_cdc.py — la maggior parte
usa un docenti_map fittizio (monkeypatch di docenti_reali_per_classe)
per isolare la logica di scheduling dal setup di Assegnazioni; un test
dedicato verifica anche la query reale.
"""
from datetime import date
from models import db
import modules.generatore_cdc as gcdc
from models.generatore_cdc import VincoloOrarioClasse, VincoloGeneratoreCdc
from models.sospensione import SospensioneDidattica
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.classe_concorso import ClasseConcorso
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _fissa_docenti(monkeypatch, mappa):
    monkeypatch.setattr(gcdc, 'docenti_reali_per_classe', lambda anno_scol: mappa)


def test_due_classi_senza_docenti_comuni_stesso_slot(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {3, 4}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 18),
        '14:00', '18:00', durata_min=60)
    assert all(not r['conflitto'] for r in ris)
    a = next(r for r in ris if r['classe'] == '1A LLI')
    b = next(r for r in ris if r['classe'] == '1A CAT')
    assert (a['data'], a['ora_inizio']) == (b['data'], b['ora_inizio'])


def test_due_classi_con_docente_comune_slot_diversi(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {2, 5}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 18),
        '14:00', '18:00', durata_min=60)
    assert all(not r['conflitto'] for r in ris)
    a = next(r for r in ris if r['classe'] == '1A LLI')
    b = next(r for r in ris if r['classe'] == '1A CAT')
    assert (a['data'], a['ora_inizio']) != (b['data'], b['ora_inizio'])


def test_vincolo_orario_esclude_slot_per_indirizzo(db_session, monkeypatch):
    """Martedì 13:30-15:30 CAT non è libero da lezione (rientro
    pomeridiano) — il generatore non deve proporre quello slot per CAT."""
    _fissa_docenti(monkeypatch, {'1A CAT': {1}})
    martedi = date(2026, 9, 15)
    assert martedi.weekday() == 1
    db.session.add(VincoloOrarioClasse(
        giorno_settimana=1, ora_inizio='13:30', ora_fine='15:30',
        indirizzi='CAT', descrizione='Rientro pomeridiano'))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A CAT'], martedi, martedi, '13:30', '15:30', durata_min=60)
    # Unico giorno nel periodo è il martedì vincolato: nessuno slot libero
    assert ris[0]['conflitto'] is True


def test_vincolo_orario_non_si_applica_ad_altro_indirizzo(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1}})
    martedi = date(2026, 9, 15)
    db.session.add(VincoloOrarioClasse(
        giorno_settimana=1, ora_inizio='13:30', ora_fine='15:30',
        indirizzi='CAT', descrizione='Rientro pomeridiano CAT'))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI'], martedi, martedi, '13:30', '15:30', durata_min=60)
    assert ris[0]['conflitto'] is False  # LLI non è coinvolto dal vincolo CAT


def test_vincolo_entro_data_rispetta_scadenza(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': set()})
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='entro_data',
        scadenza=date(2026, 9, 15)))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT'], date(2026, 9, 14), date(2026, 9, 20),
        '14:00', '15:00', durata_min=60)
    assert ris[0]['conflitto'] is False
    assert ris[0]['data'] <= date(2026, 9, 15)


def test_vincolo_entro_data_senza_slot_prima_della_scadenza_da_conflitto(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': set()})
    lunedi_sospeso = date(2026, 9, 14)
    db.session.add(SospensioneDidattica(
        data_inizio=lunedi_sospeso, data_fine=lunedi_sospeso, descrizione='Sciopero'))
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='entro_data',
        scadenza=lunedi_sospeso))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT'], lunedi_sospeso, date(2026, 9, 20),
        '14:00', '15:00', durata_min=60)
    assert ris[0]['conflitto'] is True


def test_vincolo_fisso_piazza_allo_slot_esatto(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': set()})
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='fissa',
        data_fissa=date(2026, 9, 16), ora_fissa='16:00'))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT'], date(2026, 9, 14), date(2026, 9, 20),
        '14:00', '18:00', durata_min=60)
    assert ris[0]['conflitto'] is False
    assert ris[0]['data'] == date(2026, 9, 16)
    assert ris[0]['ora_inizio'] == '16:00'


def test_vincolo_fisso_in_conflitto_con_altro_fisso_da_errore(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': {1}, '5A LLI': {1}})  # docente condiviso
    slot = (date(2026, 9, 16), '16:00')
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='fissa',
        data_fissa=slot[0], ora_fissa=slot[1]))
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A LLI', tipo='fissa',
        data_fissa=slot[0], ora_fissa=slot[1]))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT', '5A LLI'], date(2026, 9, 14), date(2026, 9, 20),
        '14:00', '18:00', durata_min=60)
    esiti = {r['classe']: r['conflitto'] for r in ris}
    # La prima piazzata occupa lo slot, la seconda (stesso slot fisso,
    # docente condiviso) va in conflitto — non può essere spostata da sola
    assert sum(esiti.values()) == 1


def test_presenza_ds_impedisce_stesso_slot_anche_senza_docenti_comuni(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {3, 4}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 14),
        '14:00', '15:00', durata_min=60,  # un solo slot disponibile in tutto il periodo
        classi_richiedono_ds={'1A LLI', '1A CAT'})
    esiti = {r['classe']: r['conflitto'] for r in ris}
    # Un solo slot esiste: non possono starci entrambe se richiedono il DS
    assert sum(esiti.values()) == 1


def test_ds_non_conflitto_se_solo_una_classe_lo_richiede(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {3, 4}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 14),
        '14:00', '15:00', durata_min=60,
        classi_richiedono_ds={'1A LLI'})
    assert all(not r['conflitto'] for r in ris)
    a = next(r for r in ris if r['classe'] == '1A LLI')
    b = next(r for r in ris if r['classe'] == '1A CAT')
    assert (a['data'], a['ora_inizio']) == (b['data'], b['ora_inizio'])  # stesso slot, ok


def test_preferenza_stesso_indirizzo_a_parita_di_condizioni(db_session, monkeypatch):
    """Tre classi CAT senza docenti comuni e una LLI: il generatore deve
    preferire accorpare le CAT tra loro quando possibile, non sparpagliarle."""
    _fissa_docenti(monkeypatch, {
        '1A CAT': {1}, '2A CAT': {2}, '3A CAT': {3}, '1A LLI': {4},
    })
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A CAT', '2A CAT', '3A CAT', '1A LLI'],
        date(2026, 9, 14), date(2026, 9, 18), '14:00', '18:00', durata_min=60)
    cat_slots = {(r['data'], r['ora_inizio']) for r in ris if 'CAT' in r['classe']}
    assert len(cat_slots) == 1  # tutte e tre le CAT nello stesso slot


def test_giorni_lavorativi_esclude_domenica_e_sospensioni(db_session):
    db.session.add(SospensioneDidattica(
        data_inizio=date(2026, 9, 16), data_fine=date(2026, 9, 16), descrizione='Festa'))
    db.session.commit()
    giorni = gcdc.giorni_lavorativi(date(2026, 9, 13), date(2026, 9, 20))  # dom 13 - dom 20
    assert date(2026, 9, 13) not in giorni  # domenica
    assert date(2026, 9, 16) not in giorni  # sospensione
    assert date(2026, 9, 14) in giorni
    assert date(2026, 9, 19) in giorni  # sabato incluso


# ── Query reale (non monkeypatchata) ─────────────────────────────────────────

def test_docenti_reali_per_classe_dalle_assegnazioni(db_session):
    cc = ClasseConcorso(codice='A026', nome='Matematica')
    db.session.add(cc)
    db.session.commit()
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')

    asgn1 = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id, id_docente=d1.id, tipo='titolare')
    db.session.add(asgn1)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn1.id, indirizzo='LLI', anno_corso=3, sezione='A', ore=4))

    # Placeholder: non deve comparire nella mappa
    asgn2 = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id, nome_placeholder='Da nominare', tipo='supplente')
    db.session.add(asgn2)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn2.id, indirizzo='LLI', anno_corso=3, sezione='A', ore=2))
    db.session.commit()

    mappa = gcdc.docenti_reali_per_classe(ANNO)
    assert mappa['3A LLI'] == {d1.id}
