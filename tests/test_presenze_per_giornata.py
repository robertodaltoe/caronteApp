"""
Roberto: un corso di formazione su più date (es. POC DM38 Modulo 1, 4 date)
deve poter avere presenze diverse per ogni giornata. Prima c'era una sola
AttivitaIstPresenza per (evento, docente), quindi la stessa presenza valeva
per tutte le date.
"""
from datetime import date
from models import db
from models.attivita_ist import (AttivitaIst, AttivitaIstSessione,
                                 AttivitaIstPresenza, AttivitaIstPresenzaGiornata)
from tests.conftest import crea_docente


def _corso(d1, d2):
    ev = AttivitaIst(tipo='formazione', titolo='POC DM38 Modulo 1', data=date(2027, 3, 1),
                     ora_inizio='14:00', ora_fine='16:00', origine='manuale')
    db.session.add(ev)
    db.session.flush()
    for dt, i, f in [(date(2027, 3, 1), '14:00', '16:00'), (date(2027, 3, 8), '14:00', '18:00')]:
        db.session.add(AttivitaIstSessione(id_attivita=ev.id, data=dt, ora_inizio=i, ora_fine=f))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d1.id, stato='presente'))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d2.id, stato='presente'))
    db.session.commit()
    return ev


def _registra(client, ev, data, **stati):
    form = {'data': data}
    form.update({f'stato_{k}': v for k, v in stati.items()})
    return client.post(f'/attivita-ist/{ev.id}/presenze', data=form)


def test_presenze_diverse_per_giornata(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    visto = {}
    monkeypatch.setattr(mod, 'render_template', lambda t, **kw: visto.update(kw) or '<html></html>')
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    d1, d2 = crea_docente('Uno'), crea_docente('Due')
    db.session.commit()
    ev = _corso(d1, d2)

    with app.test_client() as c:
        # giorno 1: entrambi presenti; giorno 2: Due assente
        _registra(c, ev, '2027-03-01', **{str(d1.id): 'presente', str(d2.id): 'presente'})
        _registra(c, ev, '2027-03-08', **{str(d1.id): 'presente', str(d2.id): 'assente'})
        assert c.get(f'/attivita-ist/{ev.id}/presenze?data=2027-03-08').status_code == 200
    assert visto['data_sel'] == date(2027, 3, 8)
    assert {r.id_docente: r.stato for r in visto['righe']} == {d1.id: 'presente', d2.id: 'assente'}

    p1 = AttivitaIstPresenza.query.filter_by(id_attivita=ev.id, id_docente=d1.id).one()
    p2 = AttivitaIstPresenza.query.filter_by(id_attivita=ev.id, id_docente=d2.id).one()
    assert p2.stato == 'presente'                      # giorno 1 invariato
    assert p2.stato_il(date(2027, 3, 8)) == 'assente'  # giorno 2 diverso
    assert p1.stato_il(date(2027, 3, 8)) == 'presente'
    # ore: Uno 2h + 4h, Due solo le 2h del primo giorno
    assert p1.ore_conteggiate == 6.0
    assert p2.ore_conteggiate == 2.0


def test_evento_data_singola_invariato(app, db_session):
    d = crea_docente('Singolo')
    db.session.commit()
    ev = AttivitaIst(tipo='formazione', titolo='x', data=date(2027, 3, 1),
                     ora_inizio='14:00', ora_fine='16:00', origine='manuale')
    db.session.add(ev)
    db.session.flush()
    p = AttivitaIstPresenza(id_attivita=ev.id, id_docente=d.id, stato='presente')
    db.session.add(p)
    db.session.commit()
    assert p.ore_conteggiate == 2.0
    p.stato = 'assente'
    assert p.ore_conteggiate == 0.0
