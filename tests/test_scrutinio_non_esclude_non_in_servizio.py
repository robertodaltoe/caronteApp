"""
Roberto, sul caso Volpe (TD_GS, escluso dal preset di 4 scrutini di
fine agosto perché il contratto "fino a giorno scrutini" risulta
scaduto per quelle date): "in realtà non va tolto ma andrà sostituito
quindi è importante che compaia per poterlo sostituire idem gli altri
indicati come assenti (mi pare May e altri)".

Causa: _preset_partecipanti() per tipo=='scrutinio' filtrava
_non_in_servizio_per_data() esattamente come consiglio_classe/glo — ma
lo scrutinio è un atto dovuto con una funzione di sostituzione dedicata
(Sostituzioni, badge "non in servizio" in presenze()): chi non è più
in servizio deve restare nell'elenco per essere sostituito, non
sparire. Escluderlo dal preset lo faceva comparire "da rimuovere" in
qualunque risincronizzazione, perdendo il riferimento a chi sostituire.

Fix: per tipo=='scrutinio', _preset_partecipanti() non filtra più per
esclusi_ids — consiglio_classe/glo restano invariati (per quelli non
esiste un meccanismo di sostituzione, non ha senso tenerli in elenco
per un incontro futuro che chi è uscito non farà mai).
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)
ANNO = f'{FUTURO.year}-{FUTURO.year+1}' if FUTURO.month >= 9 else f'{FUTURO.year-1}-{FUTURO.year}'


def _assegna(docente, anno_corso, indirizzo, sezione='A', ore=9):
    cc = ClasseConcorso.query.filter_by(codice='A012').first()
    if not cc:
        cc = ClasseConcorso(codice='A012', nome='A012')
        db.session.add(cc)
        db.session.commit()
    asgn = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                id_docente=docente.id, tipo='titolare')
    db.session.add(asgn)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn.id, indirizzo=indirizzo,
                                       anno_corso=anno_corso, sezione=sezione, ore=ore))
    db.session.commit()


def test_scrutinio_include_docente_con_contratto_td_gs_scaduto_ad_agosto(app, db_session):
    """Stesso scenario reale di Volpe: contratto TD_GS, scrutinio ad
    agosto (dopo la presunta scadenza) — deve restare nel preset."""
    d = crea_docente('Volpe', tipo_contratto='TD_GS')
    _assegna(d, 1, 'LSU', sezione='B')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1B LSU', classe='1B LSU',
                      data=date(int(ANNO[:4]) + 1, 8, 30), origine='manuale')
    db.session.add(ev)
    db.session.flush()

    from routes.attivita_ist import _preset_partecipanti
    assert d.id in _preset_partecipanti(ev)


def test_consiglio_di_classe_continua_a_escludere_lo_stesso_docente(app, db_session):
    """A differenza dello scrutinio, un Consiglio di classe non ha un
    meccanismo di sostituzione: chi non è più in servizio resta escluso
    dal preset, comportamento invariato."""
    d = crea_docente('Volpe', tipo_contratto='TD_GS')
    _assegna(d, 1, 'LSU', sezione='B')
    db.session.commit()

    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 1B LSU', classe='1B LSU',
                      data=date(int(ANNO[:4]) + 1, 8, 30), origine='manuale')
    db.session.add(ev)
    db.session.flush()

    from routes.attivita_ist import _preset_partecipanti
    assert d.id not in _preset_partecipanti(ev)


def test_diff_risincronizzazione_non_propone_piu_di_rimuovere_lo_scrutinatore_scaduto(app, db_session):
    from models.attivita_ist import AttivitaIstPartecipante
    d = crea_docente('May', tipo_contratto='TD_GS')
    _assegna(d, 1, 'LSU', sezione='B')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1B LSU', classe='1B LSU',
                      data=date(int(ANNO[:4]) + 1, 8, 30), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    from routes.attivita_ist import _diff_risincronizzazione
    _, da_rimuovibili, non_rimovibili = _diff_risincronizzazione(ev)
    assert d.id not in [x.id for x in da_rimuovibili]
    assert d.id not in [x.id for x in non_rimovibili]
