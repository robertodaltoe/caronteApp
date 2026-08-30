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
    corso = CorsoFormazione(id_attivita=ev.id, titolo='Corso 26-27', _ore_legacy=1,
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
    corso = CorsoFormazione(id_attivita=ev.id, titolo='Corso', _ore_legacy=1,
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


# ── Contratto storico per anno (DocenteContrattoAnno) ───────────────────────

def test_agosto_usa_contratto_storico_non_quello_corrente(app, db_session):
    """Roberto: Agrò aveva contratto TD_GS (scaduto a fine giugno) nel
    2025-2026, ma il suo tipo_contratto è stato aggiornato a 'TI' per
    prepararlo al 2026-2027. Senza una riga storica per il 2025-2026,
    _non_in_servizio_per_data lo avrebbe considerato erroneamente in
    servizio ad agosto 2025-2026 guardando solo il contratto corrente
    (TI, idoneo). Con la riga storica registrata, deve invece risultare
    non in servizio per quell'agosto specifico."""
    from models.docente import DocenteContrattoAnno
    from routes.attivita_ist import _non_in_servizio_per_data

    d = crea_docente('AgroTest', tipo_contratto='TI')  # contratto corrente/nuovo

    # Senza riga storica: il contratto corrente (TI) è idoneo, quindi
    # in servizio ad agosto.
    assert d.id not in _non_in_servizio_per_data(date(2026, 8, 20))

    # Con la riga storica per il 2025-2026 (TD_GS, scaduto a giugno):
    # non in servizio a quell'agosto.
    db.session.add(DocenteContrattoAnno(id_docente=d.id, anno_scol='2025-2026',
                                         tipo_contratto='TD_GS'))
    db.session.commit()
    assert d.id in _non_in_servizio_per_data(date(2026, 8, 20))

    # Il 2026-2027 (nessuna riga storica per quell'anno) resta invariato:
    # usa il contratto corrente TI, idoneo.
    assert d.id not in _non_in_servizio_per_data(date(2027, 8, 20))


def test_docenti_idonei_periodo_agosto_usa_contratto_storico(app, db_session):
    from models.docente import DocenteContrattoAnno
    from routes.recupero_costanti import docenti_idonei_periodo

    d = crea_docente('AgroTest2', tipo_contratto='TI')
    db.session.add(DocenteContrattoAnno(id_docente=d.id, anno_scol='2025-2026',
                                         tipo_contratto='TD_GS'))
    db.session.commit()

    ids_2526 = {x.id for x in docenti_idonei_periodo('2025-2026')}
    ids_2627 = {x.id for x in docenti_idonei_periodo('2026-2027')}
    assert d.id not in ids_2526
    assert d.id in ids_2627


def test_tipo_contratto_per_anno_usa_storico_quando_esiste(app, db_session):
    """Copertura dell'helper riusato da dashboard_anno.py ed
    export_xlsx.py per i conteggi/etichette "TI" legati a un anno
    specifico (stesso bug: un TD che entra in ruolo, es. Agrò, non va
    contato/mostrato come TI per un anno in cui non lo era ancora)."""
    from models.docente import (DocenteContrattoAnno, tipo_contratto_per_anno,
                                 tipo_contratto_label_per_anno)

    d = crea_docente('AgroHelper', tipo_contratto='TI')
    # Senza riga storica: ricade sul corrente.
    assert tipo_contratto_per_anno(d, '2025-2026') == 'TI'
    assert tipo_contratto_label_per_anno(d, '2025-2026') == 'TI — Indeterminato'

    db.session.add(DocenteContrattoAnno(id_docente=d.id, anno_scol='2025-2026',
                                         tipo_contratto='TD_GS'))
    db.session.commit()
    assert tipo_contratto_per_anno(d, '2025-2026') == 'TD_GS'
    assert tipo_contratto_label_per_anno(d, '2025-2026') == 'TD 30 giugno'
    # L'anno senza riga storica resta sul corrente.
    assert tipo_contratto_per_anno(d, '2026-2027') == 'TI'


def test_conferma_contratti_anno_cumulativa(app, db_session):
    """Roberto: vuole confermare i contratti di tutti i docenti con un
    solo invio (selettori precompilati per riga), non uno alla volta.
    L'azione 'conferma_contratti_anno' legge tutti i campi
    tipo_contratto_<id> presenti nel POST e registra/aggiorna una
    DocenteContrattoAnno per ciascuno in un colpo solo."""
    from models.docente import DocenteContrattoAnno
    import routes.impostazione_anno as mod
    if 'impostazione_anno' not in app.blueprints:
        app.register_blueprint(mod.impostazione_anno_bp)

    d1 = crea_docente('Uno', tipo_contratto='TI')
    d2 = crea_docente('Due', tipo_contratto='IRC')
    # d2 ha già una riga storica per l'anno: deve essere AGGIORNATA, non
    # duplicata, se il selettore la conferma con un valore diverso.
    db.session.add(DocenteContrattoAnno(id_docente=d2.id, anno_scol='2025-2026',
                                         tipo_contratto='TD_annuale'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/impostazione-anno/docenti-anno', data={
            'azione': 'conferma_contratti_anno',
            'anno_scol': '2025-2026',
            f'tipo_contratto_{d1.id}': 'TI',
            f'tipo_contratto_{d2.id}': 'IRC',
        })
        assert r.status_code == 302

    righe = {r.id_docente: r.tipo_contratto for r in
             DocenteContrattoAnno.query.filter_by(anno_scol='2025-2026').all()}
    assert righe[d1.id] == 'TI'
    assert righe[d2.id] == 'IRC'  # aggiornata, non duplicata
    assert DocenteContrattoAnno.query.filter_by(anno_scol='2025-2026').count() == 2


def test_anagrafica_docenti_mostra_contratto_storico(app, db_session, monkeypatch):
    """Roberto: nella pagina Anagrafica Docenti (/docenti?anno=...) un
    docente TI ora ma TD nell'anno mostrato (es. Agrò) continuava a
    comparire etichettato 'TI' — la pagina leggeva ancora il contratto
    corrente, non quello storico registrato per quell'anno."""
    from models.docente import DocenteContrattoAnno
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)
    catturato = _cattura(monkeypatch, mod)

    d = crea_docente('AgroLista', tipo_contratto='TI')
    db.session.add(DocenteContrattoAnno(id_docente=d.id, anno_scol='2025-2026',
                                         tipo_contratto='TD_GS'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/docenti?anno=2025-2026')
        assert r.status_code == 200

    assert catturato['kwargs']['contratti_anno_map'].get(d.id) == 'TD_GS'


def test_piano_personale_lista_esclude_non_ancora_in_servizio(app, db_session, monkeypatch):
    """Stesso controllo mancante altrove (dashboard, supplenze, esami
    integrativi): un docente con anno_scol_inizio futuro non deve
    comparire tra chi deve compilare il Piano Attività Personale per un
    anno in cui non è ancora arrivato."""
    import routes.piano_personale as mod
    if 'piano_personale' not in app.blueprints:
        app.register_blueprint(mod.piano_personale_bp)
    catturato = _cattura(monkeypatch, mod)

    d_non_arrivato = crea_docente('NonArrivatoPiano', tipo_contratto='TI')
    d_non_arrivato.anno_scol_inizio = '2026-2027'
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/piano-personale?anno=2025-2026')
        assert r.status_code == 200

    ids = {riga['docente'].id for riga in catturato['kwargs']['righe']}
    assert d_non_arrivato.id not in ids
