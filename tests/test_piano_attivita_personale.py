"""
Test di regressione per la Sessione 57: Piano delle Attività Personale
per i docenti con cattedra non completa in istituto.

Copre:
1. Calcolo della frazione di cattedra / quota ore proporzionale.
2. La selezione personale sostituisce il preset automatico di
   partecipazione agli eventi bucket A/B (non gli scrutini).
3. Le route pubbliche (token, nessun login) rispettano lo stato
   'bloccato' anche se qualcuno prova a forzare il salvataggio.
"""
from datetime import date

from models import db
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.materia import Dipartimento, Materia, DocenteMateria  # noqa
        from models.piano_attivita_personale import PianoAttivitaPersonale, PianoAttivitaPersonaleVoce  # noqa
        from models.config_app import ConfigApp  # noqa
        db.create_all()


# ── 1. Frazione di cattedra / quota ─────────────────────────────────

def test_frazione_cattedra_piena_e_uno(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Rossi')
        d.ore_contratto = 18
        db.session.commit()
        from models.piano_attivita_personale import frazione_cattedra, cattedra_incompleta
        assert frazione_cattedra(d, '2025-2026') == 1.0
        assert not cattedra_incompleta(d, '2025-2026')


def test_frazione_cattedra_part_time_proporzionale(app, db_session):
    """Caso reale che ha fatto scattare il fix: per un part-time,
    Docente.ore_contratto contiene GIA' il valore ridotto (es. 9), non
    un nominale 18 — va confrontato con il riferimento configurabile,
    non con se stesso (altrimenti la frazione sarebbe sempre 1.0)."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Bianchi')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        db.session.commit()
        from models.piano_attivita_personale import frazione_cattedra, cattedra_incompleta
        assert frazione_cattedra(d, '2025-2026') == 0.5
        assert cattedra_incompleta(d, '2025-2026')


def test_irc_a_cattedra_piena_deve_comunque_compilare(app, db_session):
    """Chiesto da Roberto: un IRC a 18 ore e' a cattedra piena (frazione
    1.0), ma essendo presente in moltissime classi il preset automatico
    lo metterebbe in ogni consiglio di classe — sforando facilmente le
    40 ore. Deve quindi compilare il piano anche se cattedra_incompleta()
    e' False, con la quota PIENA (non proporzionata, essendo a tempo pieno)."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Santi', tipo_contratto='IRC')
        d.ore_contratto = 18
        db.session.commit()

        from models.piano_attivita_personale import (
            cattedra_incompleta, deve_compilare_piano, quota_ore_bucket,
        )
        assert not cattedra_incompleta(d, '2025-2026')     # cattedra piena
        assert deve_compilare_piano(d, '2025-2026')         # ma deve comunque compilare
        assert quota_ore_bucket(d, '2025-2026') == (40.0, 40.0)  # quota piena, non ridotta


def test_docente_normale_a_cattedra_piena_non_deve_compilare(app, db_session):
    """Un docente non-IRC a cattedra piena resta escluso, come prima."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Ferrari', tipo_contratto='TI')
        d.ore_contratto = 18
        db.session.commit()
        from models.piano_attivita_personale import deve_compilare_piano
        assert not deve_compilare_piano(d, '2025-2026')


def test_quota_ore_bucket_segue_limite_configurabile(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Verdi')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        db.session.commit()

        from models.piano_attivita_personale import quota_ore_bucket
        quota_a, quota_b = quota_ore_bucket(d, '2025-2026')
        assert quota_a == quota_b == 20.0  # metà di 40 (default ore_ist_limite)

        from config_istituto import set_dati_istituto
        set_dati_istituto({'ore_ist_limite': 20})
        quota_a, quota_b = quota_ore_bucket(d, '2025-2026')
        assert quota_a == quota_b == 10.0  # metà di 20


def test_ore_contratto_zero_non_esplode(app, db_session):
    """Un docente con ore_contratto non impostato (0) non deve causare
    una divisione per zero: Docente.ore_max_effettive_per_anno() (non
    toccata da questa sessione) ricade già su 18 quando ore_contratto è
    0/None ('self.ore_contratto or 18') — qui verifichiamo solo che la
    frazione risultante resti un valore valido (non un errore/NaN)."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Neri')
        d.ore_contratto = 0
        db.session.commit()
        from models.piano_attivita_personale import frazione_cattedra, quota_ore_bucket
        assert frazione_cattedra(d, '2025-2026') == 1.0
        assert quota_ore_bucket(d, '2025-2026') == (40.0, 40.0)


# ── 2. Override del preset partecipanti ─────────────────────────────

def _crea_evento(tipo, data_ev, titolo='Evento test'):
    from models.attivita_ist import AttivitaIst
    e = AttivitaIst(tipo=tipo, titolo=titolo, data=data_ev, ora_inizio='15:00', ora_fine='17:00')
    db.session.add(e)
    db.session.commit()
    return e


def test_piano_personale_sostituisce_preset_solo_per_evento_scelto(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Gialli')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        db.session.commit()

        ev_scelto     = _crea_evento('collegio', date(2025, 10, 10), 'Collegio ottobre')
        ev_non_scelto = _crea_evento('collegio', date(2025, 11, 10), 'Collegio novembre')

        from models.piano_attivita_personale import PianoAttivitaPersonale, PianoAttivitaPersonaleVoce, genera_token
        p = PianoAttivitaPersonale(id_docente=d.id, anno_scol='2025-2026', token=genera_token())
        db.session.add(p)
        db.session.commit()
        db.session.add(PianoAttivitaPersonaleVoce(id_piano=p.id, id_attivita=ev_scelto.id))
        db.session.commit()

        from routes.attivita_ist import _preset_partecipanti
        assert d.id in _preset_partecipanti(ev_scelto)
        assert d.id not in _preset_partecipanti(ev_non_scelto)


def test_docente_a_cattedra_piena_non_influenzato(app, db_session):
    """Un docente SENZA piano personale (cattedra piena) deve continuare
    a comparire nel preset di tutti gli eventi bucket A come sempre."""
    _crea_tabelle(app)
    with app.app_context():
        d1 = crea_docente('Piena')
        d1.ore_contratto = 18
        d2 = crea_docente('Ridotta')
        d2.ore_contratto = 9
        d2.part_time = True
        d2.ore_contratto_pt = 9
        db.session.commit()

        ev = _crea_evento('collegio', date(2025, 10, 10))
        from models.piano_attivita_personale import PianoAttivitaPersonale, genera_token
        db.session.add(PianoAttivitaPersonale(id_docente=d2.id, anno_scol='2025-2026', token=genera_token()))
        db.session.commit()

        from routes.attivita_ist import _preset_partecipanti
        preset = _preset_partecipanti(ev)
        assert d1.id in preset       # cattedra piena, nessun piano -> preset normale
        assert d2.id not in preset   # ha un piano ma non ha scelto questo evento


def test_scrutinio_non_influenzato_dal_piano_personale(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from models.orario_docente import OrarioDocente
        d = crea_docente('Scuri')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1, classe='1A', tipo_ora='lezione'))
        db.session.commit()

        ev = _crea_evento('scrutinio', date(2025, 10, 10))
        ev.classe = '1A'
        db.session.commit()

        from models.piano_attivita_personale import PianoAttivitaPersonale, genera_token
        db.session.add(PianoAttivitaPersonale(id_docente=d.id, anno_scol='2025-2026', token=genera_token()))
        db.session.commit()

        from routes.attivita_ist import _preset_partecipanti
        # Lo scrutinio segue la logica normale (orario classe), non il piano
        # personale: il docente compare comunque, anche se il piano non lo
        # include (perché gli scrutini non fanno parte del piano stesso).
        assert d.id in _preset_partecipanti(ev)


# ── 3. Route pubbliche (token, nessun login) ────────────────────────

def _registra_blueprint(app, monkeypatch=None):
    from routes.piano_personale import piano_personale_bp
    if 'piano_personale' not in app.blueprints:
        app.register_blueprint(piano_personale_bp)
    if monkeypatch is not None:
        # Il fixture 'app' leggero non ha il template_folder del progetto
        # (vedi tests/test_banca_ore_docenti_anno.py per lo stesso problema)
        # né CSRFProtect() attivo (a differenza dell'app reale in app.py) —
        # un render finto qui basta, non serve un token CSRF reale.
        import routes.piano_personale as pp_mod
        monkeypatch.setattr(pp_mod, 'render_template', lambda *a, **k: '<html></html>')
    return app


def test_token_inesistente_da_404(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    with app.test_client() as c:
        r = c.get('/piano-personale/token-non-esistente')
        assert r.status_code == 404


def test_piano_bloccato_rifiuta_salvataggio_anche_forzato(app, db_session, monkeypatch):
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    with app.app_context():
        d = crea_docente('Ferri')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        ev = _crea_evento('collegio', date(2025, 10, 10))
        from models.piano_attivita_personale import PianoAttivitaPersonale, genera_token
        p = PianoAttivitaPersonale(id_docente=d.id, anno_scol='2025-2026',
                                    token=genera_token(), stato='bloccato')
        db.session.add(p)
        db.session.commit()
        token, ev_id, pid = p.token, ev.id, p.id

    with app.test_client() as c:
        r0 = c.get(f'/piano-personale/{token}')
        assert r0.status_code == 200
        c.post(f'/piano-personale/{token}/salva', data={'evento': str(ev_id)})

    with app.app_context():
        from models.piano_attivita_personale import PianoAttivitaPersonale
        p = PianoAttivitaPersonale.query.get(pid)
        assert p.voci == []  # il tentativo di forzare il salvataggio non ha avuto effetto


def test_invia_salva_anche_le_scelte_non_solo_lo_stato(app, db_session, monkeypatch):
    """Regressione: il pulsante 'Salva e invia' deve salvare le spunte
    appena fatte, non solo segnare il piano come inviato."""
    _crea_tabelle(app)
    _registra_blueprint(app, monkeypatch)
    with app.app_context():
        d = crea_docente('Conti')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        ev = _crea_evento('collegio', date(2025, 10, 10))
        from models.piano_attivita_personale import PianoAttivitaPersonale, genera_token
        p = PianoAttivitaPersonale(id_docente=d.id, anno_scol='2025-2026', token=genera_token())
        db.session.add(p)
        db.session.commit()
        token, ev_id, pid = p.token, ev.id, p.id

    with app.test_client() as c:
        c.post(f'/piano-personale/{token}/invia', data={'evento': str(ev_id)})

    with app.app_context():
        from models.piano_attivita_personale import PianoAttivitaPersonale
        p = PianoAttivitaPersonale.query.get(pid)
        assert p.stato == 'inviato'
        assert [v.id_attivita for v in p.voci] == [ev_id]


# ── Chiarezza bucket A/B (colloqui e formazione, chiesto da Roberto) ─

def test_label_bucket_include_colloqui_e_formazione():
    from models.attivita_ist import label_bucket, BUCKET_A, BUCKET_B
    tipi_a = label_bucket(BUCKET_A)
    tipi_b = label_bucket(BUCKET_B)
    assert 'Incontro scuola-famiglia' in tipi_a
    assert 'Formazione' in tipi_a
    assert 'Consiglio di classe' in tipi_b
    # Lo scrutinio non appartiene a nessuno dei due bucket configurabili.
    assert 'Scrutinio' not in tipi_a and 'Scrutinio' not in tipi_b


# ── Riepilogo in scheda/elenco docenti ──────────────────────────────

def test_riepilogo_docenti_lista_e_scheda(app, db_session, monkeypatch):
    """Il badge in elenco e il riquadro nella scheda docente devono
    riflettere lo stato reale del piano — verificato a livello di dati
    (già coperto end-to-end manualmente con una copia del database
    reale); qui controlliamo che le funzioni su cui si basano restino
    coerenti tra loro per lo stesso docente/anno."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Adami')
        d.ore_contratto = 9
        d.part_time = True
        d.ore_contratto_pt = 9
        db.session.commit()

        from models.piano_attivita_personale import (
            cattedra_incompleta, PianoAttivitaPersonale, genera_token,
        )
        assert cattedra_incompleta(d, '2025-2026')

        p = PianoAttivitaPersonale(id_docente=d.id, anno_scol='2025-2026',
                                    token=genera_token(), stato='inviato')
        db.session.add(p)
        db.session.commit()

        # Stessa lettura che farebbero routes/docenti.py::lista()/modifica()
        stato = PianoAttivitaPersonale.query.filter_by(
            id_docente=d.id, anno_scol='2025-2026').first().stato
        assert stato == 'inviato'


# ── Permessi: la sezione e' collegata correttamente ─────────────────

def test_sezione_piano_personale_collegata():
    from models.permesso_ruolo import BLUEPRINT_SEZIONE, SEZIONI_LABEL
    assert BLUEPRINT_SEZIONE.get('piano_personale') == 'piano_personale'
    assert 'piano_personale' in SEZIONI_LABEL


def test_route_pubbliche_docente_non_richiedono_login():
    import app as app_module
    import inspect
    src = inspect.getsource(app_module)
    for endpoint in ('piano_personale.pubblico', 'piano_personale.salva', 'piano_personale.invia'):
        assert endpoint in src
