"""
Roberto: "sto cercando cambiare il numero di partecipanti al corso
unplugged selezionando nessuno dei docenti e poi salvando ma tornando
in riepilogo la modifica non diventa effettiva".

Causa: routes/attivita_ist.py::form(), ramo POST — "doc_ids vuoto" era
usato per decidere se ricadere sul preset, ma un form inviato con la
checklist Partecipanti PRESENTE e ZERO checkbox selezionate (l'utente
ha cliccato "Nessuno") produce esattamente la stessa cosa lato server
di un form che non invia affatto il campo docenti_ids — non c'era modo
di distinguerli, quindi "Nessuno" veniva sempre silenziosamente
riscritto col preset subito dopo il salvataggio.

Fix: un campo nascosto sentinella (partecipanti_form_presente) nel
template, sempre inviato insieme alla checklist — il preset scatta
solo se quel campo manca del tutto (form diverso, non questo).
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_selezionare_nessuno_svuota_davvero_i_partecipanti(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    ev = AttivitaIst(tipo='formazione', titolo='UNPLUGGED', data=date(2026, 9, 7),
                      ora_inizio='09:00', ora_fine='18:00', origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d1.id, preset=True))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d2.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'formazione', 'titolo': 'UNPLUGGED',
            'data': '2026-09-07', 'ora_inizio': '09:00', 'ora_fine': '18:00',
            'partecipanti_form_presente': '1',
            # nessuna chiave 'docenti_ids': l'utente ha cliccato "Nessuno"
        })
        assert r.status_code == 302

    partecipanti = AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()
    assert partecipanti == []


def test_senza_sentinella_ricade_ancora_sul_preset(app, db_session):
    """Comportamento invariato per chi non manda affatto la checklist
    (nessuna richiesta oggi lo fa attraverso questa route, ma il
    fallback resta per eventuali altri chiamanti futuri)."""
    _registra_blueprint(app)
    d1 = crea_docente('Verdi')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'collegio', 'titolo': 'Collegio',
            'data': '2026-09-01',
            # niente 'partecipanti_form_presente' e niente 'docenti_ids'
        })
        assert r.status_code == 302

    partecipanti_ids = {p.id_docente for p in
                         AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert d1.id in partecipanti_ids  # preset applicato (collegio -> tutti)


def test_selezione_manuale_normale_resta_intatta(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Neri')
    d2 = crea_docente('Gialli')
    ev = AttivitaIst(tipo='formazione', titolo='Corso', data=date(2026, 9, 7), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'formazione', 'titolo': 'Corso', 'data': '2026-09-07',
            'partecipanti_form_presente': '1',
            'docenti_ids': [str(d1.id)],
        })
        assert r.status_code == 302

    partecipanti_ids = {p.id_docente for p in
                         AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert partecipanti_ids == {d1.id}
