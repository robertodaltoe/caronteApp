"""
Roberto: "con il risincronizza ho inserito in automatico tutti i
docenti in riunione FSL che però erano stati selezionati appositamente.
ora continuano a comparire nell'elenco per segnare la presenza anche se
ho modificato la riunione segnando coinvolti solo i miei 9 docenti".

Causa in routes/attivita_ist.py::form(), ramo POST "Modifica": quando
si ricrea l'elenco partecipanti, veniva ripulita solo la tabella
AttivitaIstPartecipante — AttivitaIstPresenza (quella che la pagina
Presenze mostra davvero, vedi presenze.html che itera su
evento.presenze, non su evento.partecipanti) non veniva mai toccata.
Un docente tolto dalla checklist e salvato restava quindi "orfano" per
sempre nella pagina Presenze, con la sua riga di presenza mai
cancellata — indipendentemente da come fosse arrivato in elenco
(risincronizzazione automatica, preset iniziale, selezione manuale).

Fix: alla modifica di un evento, le righe AttivitaIstPresenza di chi
non è più tra i doc_ids selezionati vengono cancellate insieme al
AttivitaIstPartecipante corrispondente.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_rimuovere_un_partecipante_dal_form_ne_cancella_anche_la_presenza(app, db_session):
    _registra_blueprint(app)

    tenuto = crea_docente('Rossi')
    tolto = crea_docente('Bianchi')
    ev = AttivitaIst(tipo='dipartimento', titolo='Riunione FSL', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=tenuto.id, preset=True))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=tolto.id, preset=True))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=tenuto.id, stato='presente'))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=tolto.id, stato='presente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'dipartimento', 'titolo': 'Riunione FSL',
            'data': FUTURO.isoformat(),
            'partecipanti_form_presente': '1',
            'docenti_ids': [str(tenuto.id)],
        })
        assert r.status_code == 302

    part_ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    pres_ids = {p.id_docente for p in AttivitaIstPresenza.query.filter_by(id_attivita=ev.id).all()}

    assert part_ids == {tenuto.id}
    assert pres_ids == {tenuto.id}
    assert tolto.id not in pres_ids


def test_selezionare_nessuno_pulisce_anche_tutte_le_presenze(app, db_session):
    _registra_blueprint(app)

    d1 = crea_docente('Verdi')
    d2 = crea_docente('Neri')
    ev = AttivitaIst(tipo='formazione', titolo='Corso', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d1.id, preset=True))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d2.id, preset=True))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d1.id, stato='presente'))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d2.id, stato='presente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'formazione', 'titolo': 'Corso',
            'data': FUTURO.isoformat(),
            'partecipanti_form_presente': '1',
            # "Nessuno": nessuna chiave docenti_ids inviata.
        })
        assert r.status_code == 302

    assert AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).count() == 0
    assert AttivitaIstPresenza.query.filter_by(id_attivita=ev.id).count() == 0


def test_presenza_gia_modificata_viene_comunque_rimossa_su_scelta_esplicita(app, db_session):
    """A differenza della risincronizzazione (che protegge chi ha una
    presenza già modificata a mano), qui l'utente sta scegliendo
    esplicitamente e direttamente chi deve restare in elenco — la
    presenza già segnata di chi viene tolto va rimossa comunque,
    altrimenti resterebbe "orfana" esattamente come nel caso segnalato
    da Roberto."""
    _registra_blueprint(app)

    tolto = crea_docente('Bianchi')
    ev = AttivitaIst(tipo='dipartimento', titolo='Riunione FSL', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=tolto.id, preset=True))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=tolto.id,
                                        stato='assente', note='già segnalato a mano'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'dipartimento', 'titolo': 'Riunione FSL',
            'data': FUTURO.isoformat(),
            'partecipanti_form_presente': '1',
        })
        assert r.status_code == 302

    assert AttivitaIstPresenza.query.filter_by(id_attivita=ev.id).count() == 0
