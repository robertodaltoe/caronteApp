"""
Roberto: le ore di un corso in Piano della formazione e la durata
dell'evento collegato in Piano delle attività potevano disallinearsi
(due numeri salvati separatamente, nessun aggancio automatico) — ad
es. modificando l'orario dell'evento in Piano delle attività, il
valore "ore" del corso in Piano della formazione restava quello
vecchio (e viceversa).

Fix: CorsoFormazione.ore non è più una colonna modificabile a mano ma
una proprietà calcolata sempre dall'evento collegato (models/
formazione.py) — un solo numero, non due da tenere sincronizzati. Il
form di Piano della formazione ora chiede direttamente data/ora (più
eventuali giornate extra per corsi multi-giorno), non più un campo
"ore" libero.
"""
from datetime import date
from models import db
from models.formazione import CorsoFormazione
from models.attivita_ist import AttivitaIst


def _registra_blueprint(app):
    import routes.formazione as mod
    if 'formazione' not in app.blueprints:
        app.register_blueprint(mod.formazione_bp)


def test_creazione_corso_calcola_le_ore_dallorario(app, db_session):
    _registra_blueprint(app)
    with app.test_client() as c:
        r = c.post('/formazione/nuovo', data={
            'titolo': 'Sicurezza sul lavoro', 'tipologia': 'sicurezza',
            'modalita': 'presenza',
            'data_inizio': '2026-10-01', 'ora_inizio': '08:30', 'ora_fine': '09:00',
            'data_fine': '2026-10-01', 'anno_scol': '2026-2027',
        })
        assert r.status_code == 302

    corso = CorsoFormazione.query.filter_by(titolo='Sicurezza sul lavoro').first()
    assert corso is not None
    assert corso.ore == 0.5
    assert corso.attivita.ora_inizio == '08:30'
    assert corso.attivita.ora_fine == '09:00'


def test_modifica_orario_in_formazione_aggiorna_le_ore(app, db_session):
    _registra_blueprint(app)
    with app.test_client() as c:
        c.post('/formazione/nuovo', data={
            'titolo': 'Corso test', 'modalita': 'presenza',
            'data_inizio': '2026-10-01', 'ora_inizio': '08:30', 'ora_fine': '09:00',
            'anno_scol': '2026-2027',
        })
        corso = CorsoFormazione.query.filter_by(titolo='Corso test').first()
        assert corso.ore == 0.5

        r = c.post(f'/formazione/{corso.id}/modifica', data={
            'titolo': 'Corso test', 'modalita': 'presenza',
            'data_inizio': '2026-10-01', 'ora_inizio': '08:00', 'ora_fine': '10:00',
            'anno_scol': '2026-2027',
        })
        assert r.status_code == 302

    corso_agg = db.session.get(CorsoFormazione, corso.id)
    assert corso_agg.ore == 2.0


def test_modifica_orario_in_attivita_ist_si_riflette_nel_corso(app, db_session):
    """Il percorso inverso: modificando l'evento da Piano delle attività
    (non da Piano della formazione), corso.ore vede subito il nuovo
    valore — perché non c'è più un secondo numero salvato a parte."""
    _registra_blueprint(app)
    import routes.attivita_ist as mod_ai
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod_ai.attivita_ist_bp)

    with app.test_client() as c:
        c.post('/formazione/nuovo', data={
            'titolo': 'Corso X', 'modalita': 'presenza',
            'data_inizio': '2026-10-01', 'ora_inizio': '08:30', 'ora_fine': '09:00',
            'anno_scol': '2026-2027',
        })
        corso = CorsoFormazione.query.filter_by(titolo='Corso X').first()
        assert corso.ore == 0.5

        r = c.post(f'/attivita-ist/{corso.id_attivita}/modifica', data={
            'tipo': 'formazione', 'titolo': 'Corso X',
            'data': '2026-10-01', 'ora_inizio': '08:00', 'ora_fine': '11:00',
        })
        assert r.status_code == 302

    corso_agg = db.session.get(CorsoFormazione, corso.id)
    assert corso_agg.ore == 3.0


def test_corso_multi_giorno_somma_le_giornate(app, db_session):
    _registra_blueprint(app)
    with app.test_client() as c:
        r = c.post('/formazione/nuovo', data={
            'titolo': 'Modulo 1 - Valutazione', 'modalita': 'presenza',
            'data_inizio': '2026-09-15', 'ora_inizio': '11:30', 'ora_fine': '13:30',
            'extra_data[]': ['2026-09-22', '2026-09-29', '2026-10-06'],
            'extra_ora_inizio[]': ['09:00', '09:00', '09:00'],
            'extra_ora_fine[]': ['11:00', '12:00', '12:00'],
            'anno_scol': '2026-2027',
        })
        assert r.status_code == 302

    corso = CorsoFormazione.query.filter_by(titolo='Modulo 1 - Valutazione').first()
    assert len(corso.attivita.sessioni) == 4
    assert corso.ore == 2.0 + 2.0 + 3.0 + 3.0


def test_corso_semplice_non_crea_sessioni(app, db_session):
    """Il caso comune (corso a giorno singolo) non deve popolare
    AttivitaIstSessione — comportamento invariato."""
    _registra_blueprint(app)
    with app.test_client() as c:
        c.post('/formazione/nuovo', data={
            'titolo': 'Corso semplice', 'modalita': 'presenza',
            'data_inizio': '2026-10-01', 'ora_inizio': '09:00', 'ora_fine': '11:00',
            'anno_scol': '2026-2027',
        })

    corso = CorsoFormazione.query.filter_by(titolo='Corso semplice').first()
    assert corso.attivita.sessioni == []
    assert corso.ore == 2.0
