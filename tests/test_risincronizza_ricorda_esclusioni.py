"""
Roberto: "continuo a non riuscire a far sparire dall'elenco le voci
che insistono a propormi la sincronizzazione di docenti che non devono
partecipare alla riunione. esempio di ATS unplugged dove escludo tutti
dalla sincronizzazione ma al caricamento successivo continuo a
vederli."

Causa: deselezionare i badge "da aggiungere" nella pagina di
risincronizzazione applicava correttamente "nessuna aggiunta" QUELLA
volta, ma non lasciava alcuna traccia della scelta — al giro
successivo _diff_risincronizzazione() ricalcolava lo stesso preset,
vedeva ancora gli stessi docenti mancanti dall'elenco, e li riproponeva
identici, all'infinito.

Fix: _applica_scelte_risincronizzazione() ora marca
evento.partecipanti_manuali quando il risultato finale non coincide
col preset puro (cioè quando l'utente ha rifiutato almeno una
proposta) — stesso flag già usato per la modifica manuale dal form
principale (addendum 119): una volta impostato, _diff_risincronizzazione()
smette di proporre "da aggiungere" per quell'evento.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_escludere_tutte_le_aggiunte_non_le_ripropone_al_giro_successivo(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    ev = AttivitaIst(tipo='formazione', titolo='UNPLUGGED', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()
    # d1/d2 attivi -> preset 'formazione' li include entrambi, ma
    # l'evento non ha ancora nessun partecipante -> entrambi "da aggiungere".

    with app.test_client() as c:
        # Primo giro: propone d1 e d2, l'utente li deseleziona entrambi
        # (sentinella presente, nessun id selezionato).
        r = c.post(f'/attivita-ist/{ev.id}/risincronizza', data={
            'aggiungi_selezione_presente': '1',
        })
        assert r.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert ids == set()

    db.session.refresh(ev)
    assert ev.partecipanti_manuali is True

    from routes.attivita_ist import _diff_risincronizzazione
    da_aggiungere, _, _ = _diff_risincronizzazione(ev)
    assert da_aggiungere == []


def test_escludere_solo_alcune_aggiunte_le_ricorda_e_non_le_ripropone(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    ev = AttivitaIst(tipo='formazione', titolo='Corso', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/risincronizza', data={
            'aggiungi_selezione_presente': '1',
            'aggiungi_ids': [str(d1.id)],
        })
        assert r.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert ids == {d1.id}

    db.session.refresh(ev)
    assert ev.partecipanti_manuali is True  # d2 escluso -> non coincide col preset

    from routes.attivita_ist import _diff_risincronizzazione
    da_aggiungere, _, _ = _diff_risincronizzazione(ev)
    assert da_aggiungere == []  # d2 non viene riproposto


def test_risincronizza_tutti_non_marca_manuali_se_applica_tutto(app, db_session):
    """Applicando l'INTERA proposta (caso bulk, nessuna esclusione), il
    risultato coincide col preset: l'evento resta sincronizzabile."""
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    ev = AttivitaIst(tipo='formazione', titolo='Corso', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        c.post('/attivita-ist/risincronizza-tutti')

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert ids == {d1.id}

    db.session.refresh(ev)
    assert ev.partecipanti_manuali is False
