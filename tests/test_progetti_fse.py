"""
Test per il nuovo modulo "Progetti FSE/FESR" (area amministrativa
isolata per Piano Estate e progetti simili — modello generico, non
legato a un singolo bando). Copre:
1. Il calcolo del costo di gestione stimato (UCS), che replica la
   logica reale di SIF2127 descritta nella lettera di autorizzazione
   del progetto "Menti in Movimento" (CUP D94D26002650007): riconosce
   solo le ore di presenza dei migliori N partecipanti (N = dichiarati
   in candidatura), non tutte le presenze registrate.
2. Il CRUD di base (progetto, modulo, incarico) attraverso le route.
"""
from datetime import date
from models import db
from models.progetto_fse import ProgettoFSE, ModuloFSE, IncaricoFSE, PresenzaFSE, SessioneFSE
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()


def _registra_blueprint(app, monkeypatch=None):
    from routes.progetti_fse import progetti_fse_bp
    if 'progetti_fse' not in app.blueprints:
        app.register_blueprint(progetti_fse_bp)
    if monkeypatch is not None:
        # L'app di test (tests/conftest.py) non ha la cartella templates/
        # del progetto reale: le route che RENDERIZZANO (non solo
        # redirect) vanno con render_template finto, come altrove nella
        # suite (es. test_piano_personale_link_disabilitato.py).
        import routes.progetti_fse as mod
        monkeypatch.setattr(mod, 'render_template', lambda *a, **k: '<html></html>')


def _progetto_ucs(**kw):
    difaults = dict(
        titolo='Menti in Movimento', codice_progetto='ESO4.6.A4.A-FSEPNLO-2026-1482',
        cup='D94D26002650007', tipo_costo='ucs',
        tariffa_esperto=70.0, tariffa_tutor=30.0,
        costo_gestione_ora_partecipante=5.10,
        importo_autorizzato=48105.0,
    )
    difaults.update(kw)
    return ProgettoFSE(**difaults)


# ── Calcolo costi (logica UCS) ──────────────────────────────────────

def test_costo_gestione_stimato_considera_solo_i_migliori_n_partecipanti(app, db_session):
    """Come SIF2127: se ci sono più iscritti dei 'previsti' in
    candidatura, il rimborso si calcola solo sulle ore dei migliori N,
    non su tutti i presenti — verificato sul caso reale del progetto."""
    _crea_tabelle(app)
    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo="Let's English", ore=30, n_partecipanti_previsti=2)
    db.session.add(m)
    db.session.flush()
    # 3 "presenti" (uno in più dei 2 previsti in candidatura) con ore diverse.
    db.session.add(PresenzaFSE(id_modulo=m.id, cognome='Rossi', nome='A', ore_presenza=30))
    db.session.add(PresenzaFSE(id_modulo=m.id, cognome='Bianchi', nome='B', ore_presenza=20))
    db.session.add(PresenzaFSE(id_modulo=m.id, cognome='Verdi', nome='C', ore_presenza=10))
    db.session.commit()

    # Solo i due migliori (30 + 20 = 50 ore) vanno rimborsati, non tutti e tre.
    assert m.costo_gestione_stimato() == round(50 * 5.10, 2)


def test_costo_formazione_previsto_somma_esperto_e_tutor(app, db_session):
    _crea_tabelle(app)
    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Padel 1', ore=30, n_partecipanti_previsti=15)
    db.session.add(m)
    db.session.flush()
    db.session.add(IncaricoFSE(id_modulo=m.id, nome_esterno='Esperto Test', ruolo='esperto',
                                tariffa_oraria=70, ore_previste=30))
    db.session.add(IncaricoFSE(id_modulo=m.id, nome_esterno='Tutor Test', ruolo='tutor',
                                tariffa_oraria=30, ore_previste=30))
    db.session.commit()

    assert m.costo_formazione_previsto() == 70 * 30 + 30 * 30


def test_costi_indiretti_sono_opzionali_e_non_previsti_per_default(app, db_session):
    """Il progetto Piano Estate (a costi standard) non prevede costi
    indiretti separati -- verificato sulla lettera di autorizzazione
    reale. Il campo resta disponibile ma vuoto per default."""
    _crea_tabelle(app)
    p = _progetto_ucs()
    db.session.add(p)
    db.session.commit()
    assert p.percentuale_costi_indiretti is None
    assert p.importo_costi_indiretti_fisso is None


# ── CRUD via route ──────────────────────────────────────────────────

def test_crea_progetto_modulo_e_incarico_end_to_end(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    d = crea_docente('Fontana')
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/progetti-fse/nuovo', data={
            'titolo': 'Menti in Movimento', 'codice_progetto': 'ESO4.6.A4.A-FSEPNLO-2026-1482',
            'cup': 'D94D26002650007', 'importo_autorizzato': '48105.00',
            'tipo_costo': 'ucs', 'tariffa_esperto': '70.00', 'tariffa_tutor': '30.00',
            'costo_gestione_ora_partecipante': '5.10', 'stato': 'autorizzato',
        }, follow_redirects=True)
        assert r.status_code == 200

    p = ProgettoFSE.query.filter_by(cup='D94D26002650007').first()
    assert p is not None
    assert float(p.importo_autorizzato) == 48105.0

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/{p.id}/moduli/nuovo', data={
            'titolo': "Let's English", 'ore': '30', 'n_partecipanti_previsti': '15',
            'n_partecipanti_minimo': '9', 'importo_autorizzato': '5295.00', 'stato': 'bozza',
        }, follow_redirects=True)
        assert r.status_code == 200

    m = ModuloFSE.query.filter_by(id_progetto=p.id).first()
    assert m is not None
    assert m.titolo == "Let's English"

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/moduli/{m.id}/incarichi/nuovo', data={
            'id_docente': str(d.id), 'ruolo': 'esperto', 'tipo_rapporto': 'dipendente_interno',
            'tariffa_oraria': '70.00', 'ore_previste': '30', 'stato': 'incaricato',
        }, follow_redirects=True)
        assert r.status_code == 200

    inc = IncaricoFSE.query.filter_by(id_modulo=m.id).first()
    assert inc is not None
    assert inc.id_docente == d.id
    assert inc.nome_completo == f'{d.cognome} {d.nome}'
    assert inc.costo_previsto == 70 * 30


def test_dettaglio_progetto_mostra_stima_costo_complessiva(app, db_session, monkeypatch):
    """La pagina di dettaglio calcola e passa al template il riepilogo
    per modulo e il totale stimato -- verificato sui kwargs passati a
    render_template (l'app di test non ha il template_folder reale,
    stesso pattern di test_piano_personale_link_disabilitato.py)."""
    _crea_tabelle(app)
    _registra_blueprint(app)
    import routes.progetti_fse as mod
    catturato = {}
    monkeypatch.setattr(mod, 'render_template', lambda nome, **k: catturato.update(kwargs=k) or '<html></html>')

    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Padel 2', ore=30, n_partecipanti_previsti=15)
    db.session.add(m)
    db.session.flush()
    db.session.add(IncaricoFSE(id_modulo=m.id, nome_esterno='Esperto', ruolo='esperto',
                                tariffa_oraria=70, ore_previste=30))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/progetti-fse/{p.id}')
        assert r.status_code == 200

    kwargs = catturato['kwargs']
    assert kwargs['progetto'].id == p.id
    assert len(kwargs['riepilogo_moduli']) == 1
    assert kwargs['riepilogo_moduli'][0]['costo_formazione'] == 70 * 30
    assert kwargs['totale_previsto'] == 70 * 30
    # importo_autorizzato è un Numeric (torna come Decimal da SQLAlchemy):
    # 'scostamento' deve essere un float già pronto per il template, non
    # un'operazione mista float/Decimal lasciata al Jinja (ha causato un
    # TypeError reale in collaudo dal vivo — Jinja non lo segnala a
    # tempo di importazione, solo quando la riga viene davvero eseguita).
    assert isinstance(kwargs['scostamento'], float)
    assert kwargs['scostamento'] == 70 * 30 - 48105.0


# ── Sovrapposizioni con il Piano delle Attività didattico ────────────
# Richiesta esplicita di Roberto: l'area è isolata (non condivide
# tabelle col Piano delle Attività), ma le date dei moduli devono poter
# essere incrociate con gli impegni istituzionali per accorgersi se un
# docente incaricato è atteso anche a una riunione nello stesso orario.

def _crea_tabelle_con_attivita_ist(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante  # noqa
        db.create_all()


def test_trova_conflitto_tra_sessione_fse_e_attivita_istituzionale(app, db_session):
    from modules.conflitti_progetti_fse import trova_conflitti_progetti_fse
    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante

    _crea_tabelle_con_attivita_ist(app)
    d = crea_docente('Fontana')
    db.session.commit()

    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo="Let's English", ore=30)
    db.session.add(m)
    db.session.flush()
    db.session.add(IncaricoFSE(id_modulo=m.id, id_docente=d.id, ruolo='esperto'))
    db.session.add(SessioneFSE(id_modulo=m.id, data=date(2027, 8, 30),
                                ora_inizio='09:00', ora_fine='11:00'))
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 3A LSU', classe='3A LSU',
                      data=date(2027, 8, 30), ora_inizio='10:00', ora_fine='12:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id))
    db.session.commit()

    conflitti = trova_conflitti_progetti_fse()
    assert len(conflitti) == 1
    assert conflitti[0]['docente'].id == d.id
    assert conflitti[0]['evento'].id == ev.id


def test_nessun_conflitto_se_gli_orari_non_si_sovrappongono(app, db_session):
    from modules.conflitti_progetti_fse import trova_conflitti_progetti_fse
    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante

    _crea_tabelle_con_attivita_ist(app)
    d = crea_docente('Bianchi')
    db.session.commit()

    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Padel 1', ore=30)
    db.session.add(m)
    db.session.flush()
    db.session.add(IncaricoFSE(id_modulo=m.id, id_docente=d.id, ruolo='tutor'))
    db.session.add(SessioneFSE(id_modulo=m.id, data=date(2027, 8, 30),
                                ora_inizio='09:00', ora_fine='11:00'))
    db.session.commit()

    # Stesso giorno, stesso docente, ma orario successivo senza sovrapposizione.
    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', classe='1A CAT',
                      data=date(2027, 8, 30), ora_inizio='11:00', ora_fine='12:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id))
    db.session.commit()

    assert trova_conflitti_progetti_fse() == []


def test_calendario_modulo_aggiunge_ed_elimina_sessioni(app, db_session, monkeypatch):
    _crea_tabelle_con_attivita_ist(app)
    _registra_blueprint(app, monkeypatch)

    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Padel 2', ore=30)
    db.session.add(m)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/moduli/{m.id}/calendario', data={
            'data': '2027-08-30', 'ora_inizio': '09:00', 'ora_fine': '11:00',
        }, follow_redirects=True)
        assert r.status_code == 200

    sess = SessioneFSE.query.filter_by(id_modulo=m.id).first()
    assert sess is not None
    assert sess.data == date(2027, 8, 30)

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/sessioni/{sess.id}/elimina', follow_redirects=True)
        assert r.status_code == 200

    assert SessioneFSE.query.filter_by(id_modulo=m.id).count() == 0


# ── Registro presenze ─────────────────────────────────────────────────

def test_aggiungi_e_modifica_ore_presenza_via_route(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)

    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Il club del libro', ore=30, n_partecipanti_previsti=15)
    db.session.add(m)
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/moduli/{m.id}/presenze', data={
            'cognome': 'rossi', 'nome': 'mario', 'codice_fiscale': 'rssmra01a01h163k',
            'ore_presenza': '10',
        }, follow_redirects=True)
        assert r.status_code == 200

    presenza = PresenzaFSE.query.filter_by(id_modulo=m.id).first()
    assert presenza is not None
    assert presenza.cognome == 'ROSSI'  # normalizzato in maiuscolo, come l'anagrafica docenti
    assert presenza.codice_fiscale == 'RSSMRA01A01H163K'
    assert float(presenza.ore_presenza) == 10

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/presenze/{presenza.id}/modifica-ore',
                   data={'ore_presenza': '22'}, follow_redirects=True)
        assert r.status_code == 200

    db.session.refresh(presenza)
    assert float(presenza.ore_presenza) == 22


def test_frequenza_percentuale_e_soglia_attestato_75_per_cento(app, db_session):
    """L'attestato finale (generato da SIF2127) richiede almeno il 75%
    delle ore del modulo -- verificato sulla lettera di autorizzazione
    reale del progetto."""
    _crea_tabelle(app)
    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='La corda che unisce', ore=30)
    db.session.add(m)
    db.session.flush()
    sotto_soglia = PresenzaFSE(id_modulo=m.id, cognome='Verdi', nome='Anna', ore_presenza=20)  # 66.7%
    sopra_soglia = PresenzaFSE(id_modulo=m.id, cognome='Neri', nome='Luca', ore_presenza=23)   # 76.7%
    db.session.add_all([sotto_soglia, sopra_soglia])
    db.session.commit()

    assert sotto_soglia.frequenza_percentuale(m.ore) < 75
    assert sopra_soglia.frequenza_percentuale(m.ore) >= 75


def test_elimina_presenza(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    p = _progetto_ucs()
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Padel 1', ore=30)
    db.session.add(m)
    db.session.flush()
    pres = PresenzaFSE(id_modulo=m.id, cognome='Gialli', nome='Sara', ore_presenza=5)
    db.session.add(pres)
    db.session.commit()
    id_pres = pres.id

    with app.test_client() as c:
        r = c.post(f'/progetti-fse/presenze/{id_pres}/elimina', follow_redirects=True)
        assert r.status_code == 200

    assert PresenzaFSE.query.get(id_pres) is None
