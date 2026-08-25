"""
Bug reale segnalato da Roberto: mentre inseriva le nomine sostituti sul
Mac mini con la pagina Protocollazione aperta sul MacBook Pro, cliccando
"Salva nomina" la nomina appena inserita spariva di nuovo poco dopo.

Causa: la coppia (evento, assente) su cui stava rinominando aveva una
lapide (SyncTombstone) da una cancellazione precedente (il blocco del
31/08 ricancellato per ricominciare, addendum 52) — il sync automatico,
trovando in locale una riga la cui chiave risulta ancora lapidata, la
cancella di nuovo al giro successivo, indipendentemente dal fatto che
sia una vecchia riga risorta o una nuova inserita apposta dall'utente.

Corretto: sostituzione_scrutinio() ora rimuove la lapide per quella
stessa chiave quando salva una nomina — una nuova nomina inserita
dall'utente prevale sempre su una lapide di cancellazione precedente.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPresenza
from models.sync_tombstone import SyncTombstone
from tests.conftest import crea_docente


def test_salvare_una_nomina_rimuove_la_lapide_della_stessa_chiave(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    assente = crea_docente('Del Curto')
    sostituto = crea_docente('Landi')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 4A CAT', classe='4A CAT',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    # Simula una lapide lasciata da una cancellazione precedente sulla
    # stessa identica coppia (evento, assente) — esattamente il caso
    # del blocco 31/08 ricancellato per essere rifatto.
    import json
    chiave = json.dumps({'id_attivita': ev.id, 'id_assente': assente.id}, sort_keys=True)
    db.session.add(SyncTombstone(tabella='sostituzioni_scrutinio', chiave_logica=chiave))
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/sostituzioni', data={
            'id_assente': assente.id,
            'id_sostituto': sostituto.id,
        })
        assert r.status_code == 302

    from models.sostituzione_scrutinio import SostituzioneScrutinio
    riga = SostituzioneScrutinio.query.filter_by(id_attivita=ev.id, id_assente=assente.id).first()
    assert riga is not None
    assert riga.id_sostituto == sostituto.id

    lapide_residua = SyncTombstone.query.filter_by(
        tabella='sostituzioni_scrutinio', chiave_logica=chiave).first()
    assert lapide_residua is None, (
        "la lapide non è stata rimossa: il prossimo sync automatico "
        "cancellerebbe di nuovo la nomina appena salvata"
    )


def test_aggiornare_una_nomina_esistente_rimuove_anche_lei_la_lapide(app, db_session):
    """Stesso fix, ramo UPDATE (riga già esistente, si cambia solo il
    sostituto) invece del ramo INSERT — entrambi i percorsi del
    salvataggio devono ripulire la lapide."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    assente = crea_docente('Federico', nome='Nadia')
    sostituto = crea_docente('Zampetti')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1A CAT', classe='1A CAT',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    from models.sostituzione_scrutinio import SostituzioneScrutinio
    riga = SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id, id_sostituto=None)
    db.session.add(riga)
    db.session.commit()

    import json
    chiave = json.dumps({'id_attivita': ev.id, 'id_assente': assente.id}, sort_keys=True)
    db.session.add(SyncTombstone(tabella='sostituzioni_scrutinio', chiave_logica=chiave))
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/sostituzioni', data={
            'id_assente': assente.id,
            'id_sostituto': sostituto.id,
        })
        assert r.status_code == 302

    db.session.refresh(riga)
    assert riga.id_sostituto == sostituto.id
    assert SyncTombstone.query.filter_by(
        tabella='sostituzioni_scrutinio', chiave_logica=chiave).first() is None
