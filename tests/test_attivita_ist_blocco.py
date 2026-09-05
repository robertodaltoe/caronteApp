"""
Roberto: "come posso cancellare un intero blocco di eventi. Ad esempio
vorrei spostare in avanti di una settimana tutti gli scrutini di
Gennaio. C'è già un modo?" — non c'era: solo Modifica/Elimina per
singolo evento. Aggiunte due route in blocco (checkbox per riga
nell'elenco, combinabili con i filtri tipo/mese già esistenti in
lista()): elimina_blocco() e sposta_blocco().
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstSessione


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_elimina_blocco_cancella_solo_gli_id_selezionati(app, db_session):
    _registra_blueprint(app)

    e1 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1A', data=date(2027, 1, 10), origine='manuale')
    e2 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1B', data=date(2027, 1, 11), origine='manuale')
    e3 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 2A', data=date(2027, 1, 12), origine='manuale')
    db.session.add_all([e1, e2, e3])
    db.session.commit()
    ids_da_tenere = e3.id

    with app.test_client() as c:
        r = c.post('/attivita-ist/elimina-blocco', data={'ids': [str(e1.id), str(e2.id)]})
        assert r.status_code == 302

    rimasti = {e.id for e in AttivitaIst.query.all()}
    assert rimasti == {ids_da_tenere}


def test_elimina_blocco_senza_selezione_non_cancella_nulla(app, db_session):
    _registra_blueprint(app)
    e1 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', data=date(2027, 1, 10), origine='manuale')
    db.session.add(e1)
    db.session.commit()

    with app.test_client() as c:
        c.post('/attivita-ist/elimina-blocco', data={})

    assert AttivitaIst.query.count() == 1


def test_sposta_blocco_avanti_di_una_settimana(app, db_session):
    _registra_blueprint(app)

    e1 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1A', data=date(2027, 1, 10),
                      ora_inizio='08:00', ora_fine='08:45', origine='manuale')
    e2 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1B', data=date(2027, 1, 11), origine='manuale')
    non_selezionato = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 2A', data=date(2027, 1, 12), origine='manuale')
    db.session.add_all([e1, e2, non_selezionato])
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/attivita-ist/sposta-blocco', data={
            'ids': [str(e1.id), str(e2.id)],
            'giorni': '7',
        })
        assert r.status_code == 302

    db.session.refresh(e1)
    db.session.refresh(e2)
    db.session.refresh(non_selezionato)
    assert e1.data == date(2027, 1, 17)
    assert e1.ora_inizio == '08:00'  # orario invariato, solo la data si sposta
    assert e2.data == date(2027, 1, 18)
    assert non_selezionato.data == date(2027, 1, 12)  # non selezionato, invariato


def test_sposta_blocco_indietro_con_giorni_negativo(app, db_session):
    _registra_blueprint(app)
    e1 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', data=date(2027, 1, 10), origine='manuale')
    db.session.add(e1)
    db.session.commit()

    with app.test_client() as c:
        c.post('/attivita-ist/sposta-blocco', data={'ids': [str(e1.id)], 'giorni': '-3'})

    db.session.refresh(e1)
    assert e1.data == date(2027, 1, 7)


def test_sposta_blocco_sposta_anche_le_sessioni_multi_giorno(app, db_session):
    _registra_blueprint(app)
    e1 = AttivitaIst(tipo='formazione', titolo='Corso', data=date(2027, 1, 10), origine='manuale')
    db.session.add(e1)
    db.session.flush()
    s1 = AttivitaIstSessione(id_attivita=e1.id, data=date(2027, 1, 10))
    s2 = AttivitaIstSessione(id_attivita=e1.id, data=date(2027, 1, 17))
    db.session.add_all([s1, s2])
    db.session.commit()

    with app.test_client() as c:
        c.post('/attivita-ist/sposta-blocco', data={'ids': [str(e1.id)], 'giorni': '7'})

    db.session.refresh(e1)
    db.session.refresh(s1)
    db.session.refresh(s2)
    assert e1.data == date(2027, 1, 17)
    assert s1.data == date(2027, 1, 17)
    assert s2.data == date(2027, 1, 24)


def test_sposta_blocco_giorni_zero_non_fa_nulla(app, db_session):
    _registra_blueprint(app)
    e1 = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', data=date(2027, 1, 10), origine='manuale')
    db.session.add(e1)
    db.session.commit()

    with app.test_client() as c:
        c.post('/attivita-ist/sposta-blocco', data={'ids': [str(e1.id)], 'giorni': '0'})

    db.session.refresh(e1)
    assert e1.data == date(2027, 1, 10)
