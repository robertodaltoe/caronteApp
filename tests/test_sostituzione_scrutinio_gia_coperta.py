"""
Roberto: aprendo la pagina Sostituzioni di una classe dove un docente è
ancora da sostituire, vuole vedere se quello stesso docente è già
stato sostituito lo stesso giorno in un'altra riunione (es. Federico N.
sostituita da Zampetti C. in 1A CAT alle 10:00) — utile come contesto
per scegliere il prossimo sostituto senza dover controllare ogni
evento singolarmente.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPresenza
from models.sostituzione_scrutinio import SostituzioneScrutinio
from tests.conftest import crea_docente


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


def test_segnala_sostituzione_gia_fatta_lo_stesso_giorno_altra_classe(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    federico = crea_docente('Federico', nome='Nadia')
    zampetti = crea_docente('Zampetti', nome='Carmen')
    db.session.commit()

    ev_1a_cat = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1A CAT', classe='1A CAT',
                             data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='10:15',
                             origine='manuale')
    ev_2a_cat = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 2A CAT', classe='2A CAT',
                             data=date(2026, 8, 31), ora_inizio='10:15', ora_fine='10:30',
                             origine='manuale')
    db.session.add_all([ev_1a_cat, ev_2a_cat])
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev_1a_cat.id, id_docente=federico.id, stato='assente'))
    db.session.add(AttivitaIstPresenza(id_attivita=ev_2a_cat.id, id_docente=federico.id, stato='assente'))
    db.session.add(SostituzioneScrutinio(id_attivita=ev_1a_cat.id, id_assente=federico.id,
                                          id_sostituto=zampetti.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev_2a_cat.id}/sostituzioni')
        assert r.status_code == 200

    riga = catturato['kwargs']['righe'][0]
    assert riga['assente'].id == federico.id
    assert len(riga['altre_sostituzioni']) == 1
    altra = riga['altre_sostituzioni'][0]
    assert altra.sostituto.id == zampetti.id
    assert altra.attivita.classe == '1A CAT'
    assert altra.attivita.ora_inizio == '10:00'


def test_non_segnala_sostituzioni_di_altri_giorni(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    assente = crea_docente('Ordinana', nome='Tortosa')
    sost = crea_docente('Farina')
    db.session.commit()

    ev_ieri = AttivitaIst(tipo='scrutinio', titolo='Scrutinio ieri', classe='3A RIM',
                           data=date(2026, 8, 30), ora_inizio='10:00', ora_fine='10:15',
                           origine='manuale')
    ev_oggi = AttivitaIst(tipo='scrutinio', titolo='Scrutinio oggi', classe='4A RIM',
                           data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='10:15',
                           origine='manuale')
    db.session.add_all([ev_ieri, ev_oggi])
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev_oggi.id, id_docente=assente.id, stato='assente'))
    db.session.add(SostituzioneScrutinio(id_attivita=ev_ieri.id, id_assente=assente.id,
                                          id_sostituto=sost.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev_oggi.id}/sostituzioni')
        assert r.status_code == 200

    riga = catturato['kwargs']['righe'][0]
    assert riga['altre_sostituzioni'] == []


def test_non_segnala_se_non_ancora_nominato_altrove(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    assente = crea_docente('Del Curto')
    db.session.commit()

    ev_altra = AttivitaIst(tipo='scrutinio', titolo='Scrutinio altra', classe='2A CAT',
                            data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='10:15',
                            origine='manuale')
    ev_questa = AttivitaIst(tipo='scrutinio', titolo='Scrutinio questa', classe='3A CAT',
                             data=date(2026, 8, 31), ora_inizio='10:15', ora_fine='10:30',
                             origine='manuale')
    db.session.add_all([ev_altra, ev_questa])
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev_questa.id, id_docente=assente.id, stato='assente'))
    # Riga presente per l'altro evento ma senza sostituto ancora assegnato.
    db.session.add(SostituzioneScrutinio(id_attivita=ev_altra.id, id_assente=assente.id,
                                          id_sostituto=None))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev_questa.id}/sostituzioni')
        assert r.status_code == 200

    riga = catturato['kwargs']['righe'][0]
    assert riga['altre_sostituzioni'] == []
