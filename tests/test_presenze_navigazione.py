"""
Roberto: gestendo le presenze di molte classi in sequenza (es. i 27
scrutini di un giorno), l'unico modo per passare da una all'altra era
tornare alla Lista e ripescare l'evento successivo ogni volta. Chiesto
un link precedente/successivo che scorra TUTTI gli eventi in ordine
cronologico, anche su giorni diversi — non solo quelli dello stesso
giorno.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst
from tests.conftest import crea_docente


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


def _evento(tipo, titolo, data, ora_inizio, classe=None):
    ev = AttivitaIst(tipo=tipo, titolo=titolo, data=data, ora_inizio=ora_inizio,
                      classe=classe, origine='manuale')
    db.session.add(ev)
    return ev


def test_precedente_successivo_scorrono_anche_su_giorni_diversi(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    # Tre eventi su due giorni diversi, inseriti fuori ordine per
    # verificare che l'ordinamento sia davvero cronologico (data, ora),
    # non l'ordine di inserimento/id.
    ev_b = _evento('scrutinio', 'Scrutinio B', date(2026, 9, 2), '09:00', '2A CAT')
    ev_a = _evento('scrutinio', 'Scrutinio A', date(2026, 9, 1), '10:00', '1A CAT')
    ev_c = _evento('scrutinio', 'Scrutinio C', date(2026, 9, 2), '11:00', '3A CAT')
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev_b.id}/presenze')
        assert r.status_code == 200

    assert catturato['kwargs']['evento_prec'].id == ev_a.id
    assert catturato['kwargs']['evento_succ'].id == ev_c.id


def test_primo_evento_non_ha_precedente_ultimo_non_ha_successivo(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    ev_unico = _evento('collegio', 'Collegio', date(2026, 9, 1), '08:30')
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev_unico.id}/presenze')
        assert r.status_code == 200

    assert catturato['kwargs']['evento_prec'] is None
    assert catturato['kwargs']['evento_succ'] is None
