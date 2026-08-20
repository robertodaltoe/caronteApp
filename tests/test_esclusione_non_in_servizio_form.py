"""
Un docente con anno_scol_uscita già impostato per l'anno mostrato (fine
TD, pensionamento, trasferimento...) resta attivo=True fino a fine
dell'anno corrente, ma non deve comparire tra i selezionabili per un
anno futuro in cui non è più in servizio — bug segnalato da Roberto:
"in 2026-2027 compaiono anche i docenti che sono già stati indicati
fuori servizio". _non_in_servizio_per_data() già gestiva questo caso
per il preset automatico (_preset_partecipanti); qui si verifica che
sia applicato anche alle tendine di selezione manuale in
routes/formazione.py::form(), routes/attivita_ist.py::form() e
routes/attivita_ist.py::presenze().

Il fixture 'app' leggero non ha il template_folder reale — monkeypatch
di render_template per catturare i dati passati al template invece di
renderizzare l'HTML (stesso approccio di test_piano_annuale_riepilogo.py).
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente


def _docente_uscito(cognome, anno_scol_uscita, motivo='fine_td'):
    d = crea_docente(cognome)
    d.anno_scol_uscita = anno_scol_uscita
    d.motivo_uscita = motivo
    db.session.commit()
    return d


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


# ── Formazione ────────────────────────────────────────────────────────────

def test_formazione_form_esclude_docente_uscito_dai_selezionabili(app, db_session, monkeypatch):
    """Su un corso ESISTENTE con data nel 2026-2027, un docente con
    anno_scol_uscita='2026-2027' non deve comparire tra i selezionabili
    (caso segnalato da Roberto). Per un corso nuovo, senza ancora una
    data scelta, il riferimento è invece la data odierna — vedi test
    dedicato più sotto."""
    import routes.formazione as mod
    from models.formazione import CorsoFormazione
    if 'formazione' not in app.blueprints:
        app.register_blueprint(mod.formazione_bp)
    catturato = _cattura(monkeypatch, mod)

    d_uscito  = _docente_uscito('Uscito', '2026-2027')
    d_attivo  = crea_docente('Attivo')

    ev = AttivitaIst(tipo='formazione', titolo='Corso 26-27', data=date(2026, 10, 1),
                      durata_min=60, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    corso = CorsoFormazione(id_attivita=ev.id, titolo='Corso 26-27', ore=1,
                             modalita='presenza', data_inizio=date(2026, 10, 1),
                             data_fine=date(2026, 10, 1), obbligatorio_tutti=False,
                             anno_scol='2026-2027')
    db.session.add(corso)
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/formazione/{corso.id}/modifica')
        assert r.status_code == 200

    ids_selezionabili = {d.id for d in catturato['kwargs']['docenti_selezionabili']}
    ids_completi       = {d.id for d in catturato['kwargs']['docenti']}
    assert d_uscito.id not in ids_selezionabili
    assert d_attivo.id in ids_selezionabili
    assert d_uscito.id in ids_completi  # la lista completa resta invariata


def test_formazione_form_non_nasconde_iscritto_gia_uscito(app, db_session, monkeypatch):
    """Un docente già iscritto a un corso PRIMA di uscire deve continuare
    a comparire nell'elenco iscritti (routes/formazione.py::form usa
    'docenti', non 'docenti_selezionabili', per quel loop)."""
    import routes.formazione as mod
    from models.formazione import CorsoFormazione
    if 'formazione' not in app.blueprints:
        app.register_blueprint(mod.formazione_bp)
    catturato = _cattura(monkeypatch, mod)

    d_uscito = _docente_uscito('GiaIscritto', '2026-2027')
    ev = AttivitaIst(tipo='formazione', titolo='Corso', data=date(2026, 10, 1),
                      durata_min=60, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    corso = CorsoFormazione(id_attivita=ev.id, titolo='Corso', ore=1,
                             modalita='presenza', data_inizio=date(2026, 10, 1),
                             data_fine=date(2026, 10, 1), obbligatorio_tutti=False,
                             anno_scol='2026-2027')
    db.session.add(corso)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d_uscito.id, preset=False))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/formazione/{corso.id}/modifica')
        assert r.status_code == 200

    assert d_uscito.id in catturato['kwargs']['iscritti_ids']
    ids_completi = {d.id for d in catturato['kwargs']['docenti']}
    assert d_uscito.id in ids_completi  # resta visibile nell'elenco "già iscritto"


# ── Attività istituzionali: form evento ─────────────────────────────────────

def test_attivita_ist_form_esclude_docente_uscito(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d_uscito = _docente_uscito('Uscito2', '2026-2027')
    d_attivo = crea_docente('Attivo2')

    with app.test_client() as c:
        r = c.get('/attivita-ist/nuova?data=2026-10-01')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti']}
    assert d_uscito.id not in ids
    assert d_attivo.id in ids


def test_attivita_ist_form_non_nasconde_partecipante_gia_selezionato(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d_uscito = _docente_uscito('GiaSelezionato', '2026-2027')
    ev = AttivitaIst(tipo='altro', titolo='Evento', data=date(2026, 10, 1), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d_uscito.id, preset=False))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/modifica')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti']}
    assert d_uscito.id in ids  # già selezionato: resta visibile, non sparisce


# ── Attività istituzionali: presenze (+ aggiungi docente) ───────────────────

def test_presenze_esclude_docente_uscito_da_aggiungi(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d_uscito = _docente_uscito('Uscito3', '2026-2027')
    d_attivo = crea_docente('Attivo3')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 10, 1), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/presenze')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti_extra']}
    assert d_uscito.id not in ids
    assert d_attivo.id in ids
