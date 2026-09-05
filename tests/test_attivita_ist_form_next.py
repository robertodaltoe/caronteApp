"""
routes/attivita_ist.py::form() — dopo la modifica di un evento, Roberto
vuole tornare alla pagina di origine (es. Piano annuale, con mese/anno
filtrati) invece che sempre a "Attività istituzionali" (attivita_ist.
lista). Il template già passava un campo nascosto "next" (lo stesso
pattern già usato in elimina()), ma il ramo POST lo ignorava.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst
from models.docente import Docente


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def _crea_evento():
    ev = AttivitaIst(tipo='collegio', titolo='Collegio docenti',
                      data=date(2026, 10, 5), origine='manuale')
    db.session.add(ev)
    db.session.commit()
    return ev


def test_modifica_torna_alla_pagina_next_se_fornita(app, db_session):
    _registra_blueprint(app)
    ev = _crea_evento()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'collegio', 'titolo': 'Collegio docenti — modificato',
            'data': '2026-10-06',
            'next': '/attivita-ist/piano-annuale?anno=2026-2027&mese=10',
        })
        assert r.status_code == 302
        assert r.headers['Location'] == '/attivita-ist/piano-annuale?anno=2026-2027&mese=10'

    assert db.session.get(AttivitaIst, ev.id).titolo == 'Collegio docenti — modificato'


def test_modifica_senza_next_torna_a_lista(app, db_session):
    _registra_blueprint(app)
    ev = _crea_evento()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'collegio', 'titolo': 'Collegio docenti', 'data': '2026-10-05',
        })
        assert r.status_code == 302
        assert r.headers['Location'] == '/attivita-ist'


def test_modifica_rifiuta_next_assoluto_esterno(app, db_session):
    """Sicurezza: mai un redirect verso un URL assoluto/esterno."""
    _registra_blueprint(app)
    ev = _crea_evento()

    with app.test_client() as c:
        r = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'collegio', 'titolo': 'Collegio docenti', 'data': '2026-10-05',
            'next': '//evil.example.com/phish',
        })
        assert r.status_code == 302
        assert r.headers['Location'] == '/attivita-ist'


def test_template_invia_davvero_il_campo_next_nel_form_principale():
    """Regressione: il ramo POST di form() sapeva già gestire 'next'
    (vedi i test sopra), ma il <form> principale del template — quello
    del pulsante Salva — non aveva mai il campo nascosto 'next': solo
    il form separato di eliminazione ce l'aveva. Il GET riceveva
    correttamente ?next=... (i link "Modifica" da Piano annuale/Elenco
    lo passano), ma quel valore andava perso al salvataggio, tornando
    sempre a "Attività istituzionali" invece che al punto di partenza
    (segnalato da Roberto per Piano delle attività). Verifica diretta
    sul sorgente del template, senza bisogno di un render Jinja
    completo: il campo nascosto 'next' deve comparire PRIMA del
    </form> di chiusura del form principale (id="form-ist")."""
    import re
    with open('templates/attivita_ist/form.html', encoding='utf-8') as f:
        html = f.read()

    inizio = html.index('id="form-ist"')
    fine_form_principale = html.index('</form>', inizio)
    corpo_form_principale = html[inizio:fine_form_principale]

    assert re.search(r'name="next"', corpo_form_principale), (
        "Il form principale (id=form-ist) non contiene più un campo "
        "nascosto 'next': il salvataggio tornerebbe sempre a "
        "'Attività istituzionali' invece che alla pagina di origine."
    )
