"""
Roberto: alcuni eventi di formazione non si svolgono in un giorno solo
(es. "UNPLUGGED", 3 giorni con orari diversi) — prima si doveva forzare
il totale ore reale su un'unica data fittizia (durata_min sovrascritto
a mano), senza modo di rappresentare le giornate reali.

Modello scelto (confermato da Roberto): un solo AttivitaIst, con una
nuova tabella figlia AttivitaIstSessione per le giornate aggiuntive —
vuota per la stragrande maggioranza degli eventi (un solo giorno).
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstSessione


def _crea_evento_semplice():
    ev = AttivitaIst(tipo='formazione', titolo='Corso singolo',
                      data=date(2026, 9, 1), ora_inizio='09:00', ora_fine='11:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.commit()
    return ev


def _crea_evento_multi(giorni):
    """giorni: lista di (data, ora_inizio, ora_fine); la prima è anche
    salvata nei campi legacy data/ora_inizio/ora_fine, come fa il form."""
    d0, i0, f0 = giorni[0]
    ev = AttivitaIst(tipo='formazione', titolo='UNPLUGGED — ATS Montagna',
                      data=d0, ora_inizio=i0, ora_fine=f0, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    for d, i, f in giorni:
        db.session.add(AttivitaIstSessione(id_attivita=ev.id, data=d, ora_inizio=i, ora_fine=f))
    db.session.commit()
    return ev


def test_evento_senza_sessioni_usa_i_campi_legacy(app, db_session):
    ev = _crea_evento_semplice()
    assert ev.sessioni == []
    assert ev.durata_ore == 2.0


def test_durata_ore_somma_le_sessioni(app, db_session):
    ev = _crea_evento_multi([
        (date(2026, 9, 7), '09:00', '13:00'),   # 4h
        (date(2026, 9, 14), '09:00', '17:00'),  # 8h
        (date(2026, 9, 21), '09:00', '17:00'),  # 8h
    ])
    assert ev.durata_ore == 20.0


def test_espandi_eventi_multi_giorno_una_riga_per_sessione(app, db_session):
    from routes.attivita_ist import _espandi_eventi_multi_giorno
    ev = _crea_evento_multi([
        (date(2026, 9, 7), '09:00', '13:00'),
        (date(2026, 9, 14), '09:00', '17:00'),
        (date(2026, 9, 21), '09:00', '17:00'),
    ])
    semplice = _crea_evento_semplice()

    risultato = _espandi_eventi_multi_giorno([ev, semplice])

    virtuali = [r for r in risultato if r.id == ev.id]
    assert len(virtuali) == 3
    assert [v.data for v in virtuali] == [date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21)]
    assert virtuali[0].titolo == 'UNPLUGGED — ATS Montagna (giorno 1/3)'
    assert virtuali[2].titolo == 'UNPLUGGED — ATS Montagna (giorno 3/3)'
    assert virtuali[1].durata_ore == 8.0

    # l'evento a giorno singolo non viene toccato/espanso
    assert semplice in risultato


def test_righe_piano_annuale_mostra_levento_su_ogni_giorno_reale(app, db_session):
    from routes.attivita_ist import _righe_piano_annuale
    _crea_evento_multi([
        (date(2026, 9, 7), '09:00', '13:00'),
        (date(2026, 9, 14), '09:00', '17:00'),
        (date(2026, 9, 21), '09:00', '17:00'),
    ])

    mesi, _anni, n_eventi = _righe_piano_annuale('2026-2027')
    assert n_eventi == 1  # un solo AttivitaIst nel DB, non 3

    date_con_evento = set()
    for _etichetta, righe in mesi:
        for data_r, tipo_r, contenuto in righe:
            if tipo_r == 'eventi':
                for e in contenuto:
                    if 'UNPLUGGED' in e.titolo:
                        date_con_evento.add(data_r)
    assert date_con_evento == {date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21)}


def test_form_post_crea_le_sessioni_dalle_giornate_extra(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    with app.test_client() as c:
        r = c.post('/attivita-ist/nuova', data={
            'tipo': 'formazione', 'titolo': 'Corso multi',
            'data': '2026-09-07', 'ora_inizio': '09:00', 'ora_fine': '13:00',
            'extra_data[]': ['2026-09-14', '2026-09-21'],
            'extra_ora_inizio[]': ['09:00', '10:00'],
            'extra_ora_fine[]': ['17:00', '12:00'],
        })
        assert r.status_code == 302

    ev = AttivitaIst.query.filter_by(titolo='Corso multi').first()
    assert ev is not None
    assert len(ev.sessioni) == 3
    assert ev.durata_ore == 4.0 + 8.0 + 2.0


def test_form_post_senza_giornate_extra_non_crea_sessioni(app, db_session):
    """Il caso comune (evento a giorno singolo) non deve creare righe in
    AttivitaIstSessione — comportamento invariato per la stragrande
    maggioranza degli eventi."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    with app.test_client() as c:
        r = c.post('/attivita-ist/nuova', data={
            'tipo': 'collegio', 'titolo': 'Collegio ordinario',
            'data': '2026-09-01', 'ora_inizio': '09:00', 'ora_fine': '11:00',
        })
        assert r.status_code == 302

    ev = AttivitaIst.query.filter_by(titolo='Collegio ordinario').first()
    assert ev.sessioni == []
    assert ev.durata_ore == 2.0


def test_form_modifica_rigenera_le_sessioni(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    ev = _crea_evento_multi([
        (date(2026, 9, 7), '09:00', '13:00'),
        (date(2026, 9, 14), '09:00', '17:00'),
    ])

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'formazione', 'titolo': 'UNPLUGGED — ATS Montagna',
            'data': '2026-09-07', 'ora_inizio': '09:00', 'ora_fine': '13:00',
            'extra_data[]': ['2026-09-14'],
            'extra_ora_inizio[]': ['09:00'],
            'extra_ora_fine[]': ['12:00'],  # ridotta rispetto a prima (17:00 -> 12:00)
        })
        assert r.status_code == 302

    aggiornato = db.session.get(AttivitaIst, ev.id)
    assert len(aggiornato.sessioni) == 2
    assert aggiornato.durata_ore == 4.0 + 3.0
