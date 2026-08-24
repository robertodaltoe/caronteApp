"""
Roberto: nella pagina Presenze di uno scrutinio, oltre a Presenti/
Assenti/Giustificati/Totale vuole una card "Sostituti individuati"
(X/Y) che dica a colpo d'occhio quanti dei docenti da sostituire hanno
già una nomina registrata, senza dover aprire la pagina Sostituzioni.
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


def test_conta_sostituti_individuati_su_assenti_e_non_in_servizio(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d_assente_nominato   = crea_docente('AssenteNominato')
    d_assente_senza      = crea_docente('AssenteSenzaSostituto')
    d_non_servizio       = crea_docente('NonInServizio')
    d_non_servizio.anno_scol_uscita = '2025-2026'
    d_presente            = crea_docente('Presente')
    d_sostituto            = crea_docente('Sostituto')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='2A LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d_assente_nominato.id, stato='assente'))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d_assente_senza.id, stato='assente'))
    # stato di default 'presente', ma non in servizio -> va comunque sostituito
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d_non_servizio.id))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d_presente.id, stato='presente'))
    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=d_assente_nominato.id,
                                          id_sostituto=d_sostituto.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/presenze')
        assert r.status_code == 200

    # 3 da sostituire (2 assenti + 1 non in servizio), 1 già nominato.
    assert catturato['kwargs']['n_da_sostituire'] == 3
    assert catturato['kwargs']['n_sostituti_individuati'] == 1


def test_nessuna_card_se_tipo_non_e_scrutinio(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d = crea_docente('AssenteCollegio')
    db.session.commit()

    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 1), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d.id, stato='assente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/presenze')
        assert r.status_code == 200

    assert catturato['kwargs']['n_da_sostituire'] == 0
    assert catturato['kwargs']['n_sostituti_individuati'] == 0
