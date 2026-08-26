"""
Roberto: un docente di sostegno assegnato via Assegnazioni compare
automaticamente nelle riunioni (Consiglio di classe/scrutinio) già
esistenti al momento dell'assegnazione (iscrivi_docente_a_eventi_classe,
chiamata da routes/assegnazioni.py su salva/aggiorna-ore/nomina) — ma
non in quelle create DOPO, perché _preset_partecipanti() per
consiglio_classe/scrutinio derivava l'elenco docenti solo da
OrarioDocente, e il sostegno non ha mai righe lì (il suo orario vive
in OrarioSostegno, tabella separata).

Estesa _preset_partecipanti() (via il nuovo _docenti_sostegno_per_classe)
a includere anche i docenti di sostegno assegnati su quella classe per
l'anno scolastico dell'evento, così un Consiglio di classe/scrutinio
creato dopo l'assegnazione include comunque il docente di sostegno fin
dalla creazione.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)
ANNO = f'{FUTURO.year}-{FUTURO.year+1}' if FUTURO.month >= 9 else f'{FUTURO.year-1}-{FUTURO.year}'


def _assegna_sostegno(docente, anno_corso, indirizzo, sezione='A', ore=9):
    cc = ClasseConcorso.query.filter_by(codice='ADSS').first()
    if not cc:
        cc = ClasseConcorso(codice='ADSS', nome='Sostegno', tipo_posto='sostegno')
        db.session.add(cc)
        db.session.commit()
    asgn = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                id_docente=docente.id, tipo='titolare')
    db.session.add(asgn)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn.id, indirizzo=indirizzo,
                                       anno_corso=anno_corso, sezione=sezione, ore=ore))
    db.session.commit()
    return asgn


def test_docente_sostegno_incluso_nel_preset_di_una_riunione_creata_dopo(app, db_session):
    sos = crea_docente('Ferrari')
    _assegna_sostegno(sos, 3, 'LSC', sezione='A')

    from routes.attivita_ist import _preset_partecipanti
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LSC',
                      classe='3A LSC', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()

    ids = _preset_partecipanti(ev)
    assert sos.id in ids


def test_docente_sostegno_non_incluso_su_unaltra_classe(app, db_session):
    sos = crea_docente('Ferrari')
    _assegna_sostegno(sos, 3, 'LSC', sezione='A')

    from routes.attivita_ist import _preset_partecipanti
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A AFM',
                      classe='1A AFM', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()

    ids = _preset_partecipanti(ev)
    assert sos.id not in ids


def test_placeholder_sostegno_non_incluso(app, db_session):
    cc = ClasseConcorso(codice='ADSS', nome='Sostegno', tipo_posto='sostegno')
    db.session.add(cc)
    db.session.commit()
    asgn = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                nome_placeholder='Da nominare', tipo='supplente')
    db.session.add(asgn)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn.id, indirizzo='LSC',
                                       anno_corso=3, sezione='A', ore=9))
    db.session.commit()

    from routes.attivita_ist import _preset_partecipanti
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LSC',
                      classe='3A LSC', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()

    ids = _preset_partecipanti(ev)
    assert ids == []
