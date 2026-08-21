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


# ── Attività istituzionali: sostituzioni scrutinio ──────────────────────────

def test_sostituzione_scrutinio_esclude_docente_non_ancora_in_servizio(app, db_session, monkeypatch):
    """Roberto: un docente con anno_scol_inizio 2026-2027 (non ancora
    arrivato) non deve comparire come possibile sostituto per uno
    scrutinio del 31/08/2026 — quella data è ancora anno scolastico
    2025-2026. La route non riusava _non_in_servizio_per_data() come
    _preset_partecipanti(), quindi il candidato compariva comunque."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d_non_arrivato = crea_docente('NonArrivato')
    d_non_arrivato.anno_scol_inizio = '2026-2027'
    d_assente = crea_docente('Assente')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='3A LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    from models.attivita_ist import AttivitaIstPresenza
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d_assente.id, stato='assente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    riga = catturato['kwargs']['righe'][0]
    ids_candidati = {d.id for d, *_ in riga['candidati']}
    ids_disponibili = {d.id for d in riga['docenti_disponibili']}
    assert d_non_arrivato.id not in ids_candidati
    assert d_non_arrivato.id not in ids_disponibili


def test_sostituzione_scrutinio_mostra_da_sostituire_anche_se_presenza_stato_presente(app, db_session, monkeypatch):
    """Roberto: Agrò risulta correttamente col badge "non più in servizio"
    nella pagina presenze per uno scrutinio del 31/08 (contratto TD fino
    a GS, scaduto), ma "Sostituzioni" non lo mostra come qualcuno da
    sostituire. Causa: la sua riga AttivitaIstPresenza è rimasta sullo
    stato di default 'presente' (nessuno l'ha mai aggiornata a mano) —
    presenze_assenti guardava solo lo stato, mai il fatto che il docente
    non sia più in servizio a quella data."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    d_non_servizio = crea_docente('NonInServizioPresente')
    d_non_servizio.anno_scol_uscita = '2025-2026'
    d_non_servizio.motivo_uscita = 'trasferimento'

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='4A LSC',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.flush()
    from models.attivita_ist import AttivitaIstPresenza
    # stato di default 'presente', mai toccato — proprio come il caso reale
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d_non_servizio.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    righe = catturato['kwargs']['righe']
    assert len(righe) == 1
    assert righe[0]['assente'].id == d_non_servizio.id


# ── Dashboard: menu "Assegna sostituto" ─────────────────────────────────────

def test_dashboard_esclude_docente_non_ancora_in_servizio_dal_menu_sostituto(app, db_session, monkeypatch):
    import routes.dashboard as mod
    if 'dashboard' not in app.blueprints:
        app.register_blueprint(mod.dashboard_bp)
    catturato = _cattura(monkeypatch, mod)

    d_non_arrivato = crea_docente('NonArrivatoDash')
    d_non_arrivato.anno_scol_inizio = '2026-2027'
    d_attivo = crea_docente('AttivoDash')
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/dashboard?data=2026-05-15')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti']}
    assert d_non_arrivato.id not in ids
    assert d_attivo.id in ids


# ── Supplenze: form nuova/modifica ───────────────────────────────────────────

def test_supplenze_nuova_esclude_docente_non_ancora_in_servizio(app, db_session, monkeypatch):
    import routes.supplenze as mod
    if 'supplenze' not in app.blueprints:
        app.register_blueprint(mod.supplenze_bp)
    catturato = _cattura(monkeypatch, mod)

    d_non_arrivato = crea_docente('NonArrivatoSupp')
    d_non_arrivato.anno_scol_inizio = '2026-2027'
    d_attivo = crea_docente('AttivoSupp')
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/supplenze/nuova?data=2026-05-15')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti']}
    assert d_non_arrivato.id not in ids
    assert d_attivo.id in ids


def test_supplenze_modifica_non_nasconde_sostituto_gia_assegnato(app, db_session, monkeypatch):
    """Un sostituto già assegnato su una supplenza esistente resta
    visibile nel form anche se nel frattempo risulta non più in
    servizio a quella data — stesso principio già usato per gli altri
    form di questo file."""
    import routes.supplenze as mod
    from models.supplenza import Supplenza
    if 'supplenze' not in app.blueprints:
        app.register_blueprint(mod.supplenze_bp)
    catturato = _cattura(monkeypatch, mod)

    d_sost = crea_docente('SostGiaAssegnato')
    d_sost.anno_scol_inizio = '2026-2027'
    s = Supplenza(data=date(2026, 5, 15), ora=1, classe='1A', id_sostituto=None)
    db.session.add(s)
    db.session.flush()
    s.id_sostituto = d_sost.id
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/supplenze/{s.id}/modifica')
        assert r.status_code == 200

    ids = {d.id for d in catturato['kwargs']['docenti']}
    assert d_sost.id in ids


# ── Esami Integrativi: commissione/docenti idonei ────────────────────────────

def test_esami_integrativi_esclude_docente_non_in_servizio_da_disponibile_e_idonei(app, db_session, monkeypatch):
    import routes.esami_integrativi as mod
    if 'esami_integrativi' not in app.blueprints:
        app.register_blueprint(mod.esami_integrativi_bp)
    catturato = _cattura(monkeypatch, mod)

    from models.esami_integrativi import EsameIntegrativoCandidato, EsameIntegrativoMateria
    from models.orario_docente import OrarioDocente

    d_non_arrivato = crea_docente('NonArrivatoEsami')
    d_non_arrivato.anno_scol_inizio = '2026-2027'
    db.session.commit()
    db.session.add(OrarioDocente(id_docente=d_non_arrivato.id, giorno=0, ora=1,
                                  classe='1A', materia='MATEMATICA'))

    cand = EsameIntegrativoCandidato(anno_scol=mod.ANNO, cognome='Rossi', nome='Mario',
                                      classe_destinazione='1A')
    db.session.add(cand)
    db.session.flush()
    mat = EsameIntegrativoMateria(id_candidato=cand.id, materia='MATEMATICA',
                                   data=date(2025, 9, 5), id_docente_1=d_non_arrivato.id)
    db.session.add(mat)
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/esami-integrativi/calendario')
        assert r.status_code == 200

    riga = catturato['kwargs']['righe'][0]['materie'][0]
    assert riga['disponibile_1'] is False
    assert d_non_arrivato.id not in {d.id for d in riga['docenti_idonei']}
