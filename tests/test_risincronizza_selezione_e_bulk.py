"""
Roberto: "quando 'risincronizza' mi suggerisce aggiunte o rimozioni,
dovrei poter scegliere chi aggiungere e chi no con un click sul badge
del nome. Inoltre, non è possibile mettere un tasto sincronizza che
agisca su tutte le riunioni già programmate?"

Due estensioni a routes/attivita_ist.py::risincronizza_partecipanti():

1. I badge "da aggiungere"/"da rimuovere" nel form diventano checkbox
   cliccabili (tutte spuntate di default): la POST ora legge
   aggiungi_ids/rimuovi_ids e applica solo le selezionate, invece di
   applicare sempre l'intera proposta. Una sentinella per gruppo
   (aggiungi_selezione_presente/rimuovi_selezione_presente, stesso
   pattern già usato per "Nessuno" nei partecipanti) distingue "gruppo
   non inviato affatto" (retrocompatibilità: applica tutta la proposta,
   comportamento di sempre) da "inviato con zero selezionati" (l'utente
   ha deselezionato tutto: non si applica nulla).

2. Nuova route risincronizza_tutti(): stessa logica applicata in blocco
   a tutti gli eventi futuri con differenze, senza selezione per-badge
   (impraticabile su tanti eventi insieme) ma con le stesse garanzie di
   sicurezza (mai i non_rimovibili, mai i preset=False).
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
from tests.conftest import crea_docente


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_applica_solo_gli_id_selezionati_in_aggiunta(app, db_session):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    rossi = crea_docente('Rossi')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=rossi.id, preset=True))
    db.session.commit()

    # Due nuovi assunti: solo uno viene selezionato per l'aggiunta.
    bianchi = crea_docente('Bianchi')
    verdi = crea_docente('Verdi')

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/risincronizza', data={
            'aggiungi_selezione_presente': '1',
            'aggiungi_ids': [str(bianchi.id)],
        })
        assert r.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert bianchi.id in ids
    assert verdi.id not in ids
    assert rossi.id in ids


def test_applica_solo_gli_id_selezionati_in_rimozione(app, db_session):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    uscito1 = crea_docente('Verdi', attivo=False)
    uscito2 = crea_docente('Neri', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito1.id, preset=True))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito2.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        # Solo uscito1 selezionato per la rimozione — uscito2 resta.
        r = c.post(f'/attivita-ist/{ev.id}/risincronizza', data={
            'rimuovi_selezione_presente': '1',
            'rimuovi_ids': [str(uscito1.id)],
        })
        assert r.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert uscito1.id not in ids
    assert uscito2.id in ids


def test_deselezionare_tutto_non_applica_nulla(app, db_session):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    uscito = crea_docente('Verdi', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        # Sentinella presente (la card "da rimuovere" è stata inviata)
        # ma nessuna checkbox spuntata: l'utente ha deselezionato tutto.
        r = c.post(f'/attivita-ist/{ev.id}/risincronizza', data={
            'rimuovi_selezione_presente': '1',
        })
        assert r.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert uscito.id in ids


def test_bulk_elenca_solo_eventi_futuri_con_differenze(app, db_session, monkeypatch):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)
    passato = date.today() - timedelta(days=5)

    rossi = crea_docente('Rossi')
    ev_con_diff = AttivitaIst(tipo='collegio', titolo='Collegio A', data=futuro, origine='manuale')
    ev_allineato = AttivitaIst(tipo='collegio', titolo='Collegio B', data=futuro, origine='manuale')
    ev_passato = AttivitaIst(tipo='collegio', titolo='Collegio passato', data=passato, origine='manuale')
    db.session.add_all([ev_con_diff, ev_allineato, ev_passato])
    db.session.flush()
    # ev_con_diff: creato senza Rossi -> "da aggiungere".
    # ev_allineato: già ha Rossi -> nessuna differenza.
    db.session.add(AttivitaIstPartecipante(id_attivita=ev_allineato.id, id_docente=rossi.id, preset=True))
    db.session.commit()

    import routes.attivita_ist as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get('/attivita-ist/risincronizza-tutti')
        assert r.status_code == 200

    titoli = {row['evento'].titolo for row in catturato['kwargs']['righe']}
    assert titoli == {'Collegio A'}


def test_bulk_applica_a_tutti_gli_eventi_elencati(app, db_session):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    rossi = crea_docente('Rossi')
    ev1 = AttivitaIst(tipo='collegio', titolo='Collegio A', data=futuro, origine='manuale')
    ev2 = AttivitaIst(tipo='collegio', titolo='Collegio B', data=futuro, origine='manuale')
    db.session.add_all([ev1, ev2])
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/attivita-ist/risincronizza-tutti')
        assert r.status_code == 302

    ids1 = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev1.id).all()}
    ids2 = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev2.id).all()}
    assert rossi.id in ids1
    assert rossi.id in ids2


def test_bulk_non_tocca_presenze_modificate_a_mano(app, db_session):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    uscito = crea_docente('Verdi', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito.id, preset=True))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=uscito.id,
                                        stato='assente', note='già segnalato a mano'))
    db.session.commit()

    with app.test_client() as c:
        c.post('/attivita-ist/risincronizza-tutti')

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert uscito.id in ids
