"""
Roberto: nella scheda di modifica evento c'era "Modifica" ma nessun
modo per eliminare la riunione — il backend esisteva già (usato dalla
pagina "Elenco/gestione eventi") ma non era raggiungibile dalla scheda
stessa. Aggiunto un pulsante "Elimina evento" nel form.

Nell'estendere l'eliminazione, sistemato anche un buco di dati:
SostituzioneScrutinio non ha una relazione con cascade dal lato
AttivitaIst (a differenza di AttivitaIstPartecipante/Presenza), quindi
eliminare uno scrutinio con sostituzioni già nominate lasciava righe
orfane con un id_attivita ormai inesistente — ora vengono ripulite (con
lapide, come le altre cancellazioni di quella tabella nel sync
automatico).
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
from models.sostituzione_scrutinio import SostituzioneScrutinio
from models.sync_tombstone import SyncTombstone
from tests.conftest import crea_docente


def test_form_modifica_mostra_il_pulsante_elimina(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        catturato['template'] = template_name
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/modifica')
        assert r.status_code == 200

    assert catturato['kwargs']['evento'].id == ev.id


def test_elimina_rimuove_levento_e_i_partecipanti(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    d = crea_docente('Rossi')
    db.session.commit()

    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d.id, stato='presente'))
    db.session.commit()
    ev_id = ev.id

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev_id}/elimina')
        assert r.status_code == 302

    assert AttivitaIst.query.get(ev_id) is None
    assert AttivitaIstPartecipante.query.filter_by(id_attivita=ev_id).count() == 0
    assert AttivitaIstPresenza.query.filter_by(id_attivita=ev_id).count() == 0


def test_elimina_scrutinio_ripulisce_le_sostituzioni_orfane_con_lapide(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    assente = crea_docente('DelCurto')
    sostituto = crea_docente('Boffi')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 2B LSC', classe='2B LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                          id_sostituto=sostituto.id))
    db.session.commit()
    ev_id = ev.id

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev_id}/elimina')
        assert r.status_code == 302

    assert AttivitaIst.query.get(ev_id) is None
    assert SostituzioneScrutinio.query.filter_by(id_attivita=ev_id).count() == 0

    import json
    chiave = json.dumps({'id_attivita': ev_id, 'id_assente': assente.id}, sort_keys=True)
    assert SyncTombstone.query.filter_by(
        tabella='sostituzioni_scrutinio', chiave_logica=chiave).first() is not None


def test_elimina_senza_next_torna_alla_lista(app, db_session):
    """Comportamento di sempre quando il chiamante non specifica da
    dove arriva (es. una chiamata diretta all'API)."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/elimina')
        assert r.status_code == 302
        assert r.headers['Location'].endswith('/attivita-ist')


def test_elimina_con_next_torna_alla_pagina_di_provenienza(app, db_session):
    """Roberto: eliminando da Piano delle attività, la pagina si
    ricaricava sempre su Attività istituzionali invece che tornare a
    Piano delle attività — il "next" (passato come campo nascosto dal
    form di eliminazione) deve riportare esattamente lì."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/elimina',
                    data={'next': '/attivita-ist/piano-annuale?anno=2026-2027'})
        assert r.status_code == 302
        assert r.headers['Location'] == '/attivita-ist/piano-annuale?anno=2026-2027'


def test_elimina_ignora_un_next_esterno_non_relativo(app, db_session):
    """Un 'next' che non è un percorso relativo di questa app (URL
    assoluto/esterno, o //host che il browser tratterebbe come
    protocol-relative) viene ignorato — niente open-redirect."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    for next_val in ['https://evil.example.com', '//evil.example.com', 'javascript:alert(1)']:
        ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
        db.session.add(ev)
        db.session.commit()

        with app.test_client() as c:
            r = c.post(f'/attivita-ist/{ev.id}/elimina', data={'next': next_val})
            assert r.status_code == 302
            assert r.headers['Location'].endswith('/attivita-ist')
