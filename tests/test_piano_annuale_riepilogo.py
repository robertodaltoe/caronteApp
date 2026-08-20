"""
Fase 2 del Piano Annuale delle Attività: vista mensile
(routes/attivita_ist.py::piano_annuale) e riepilogo ore per classe/
docente (routes/attivita_ist.py::riepilogo_ore).

Il fixture 'app' leggero non ha il template_folder del progetto né i
context processor dell'app reale (vedi test_piano_attivita_personale.py
per lo stesso problema) — monkeypatch di render_template per catturare
i dati calcolati dalla route invece di renderizzare l'HTML reale.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.classe_concorso import ClasseConcorso
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _cc(codice='AS48'):
    cc = ClasseConcorso(codice=codice, nome='Scienze motorie')
    db.session.add(cc)
    db.session.commit()
    return cc


def _placeholder(nome, codice_cc, classi_label):
    cc = _cc(codice_cc)
    asgn = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                nome_placeholder=nome, tipo='supplente')
    db.session.add(asgn)
    db.session.flush()
    for lbl in classi_label:
        anno_corso, resto = lbl.split(' ', 1)
        sezione = anno_corso[-1] if anno_corso[-1] in 'AB' else 'A'
        anno_n = int(anno_corso[:-1]) if anno_corso[-1] in 'AB' else int(anno_corso)
        db.session.add(AssegnazioneClasse(
            id_assegnazione=asgn.id, indirizzo=resto,
            anno_corso=anno_n, sezione=sezione, ore=4))
    db.session.commit()
    return asgn


def _registra_blueprint_con_cattura(app, monkeypatch):
    from routes.attivita_ist import attivita_ist_bp
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(attivita_ist_bp)

    catturato = {}
    import routes.attivita_ist as mod

    def _finto_render(template_name, **kwargs):
        catturato['template'] = template_name
        catturato['kwargs'] = kwargs
        return '<html></html>'

    monkeypatch.setattr(mod, 'render_template', _finto_render)
    return catturato


def test_piano_annuale_raggruppa_per_mese_e_giorno(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    db.session.add_all([
        AttivitaIst(tipo='collegio', titolo='Collegio apertura',
                    data=date(2026, 9, 2), origine='manuale'),
        AttivitaIst(tipo='collegio', titolo='Collegio secondo evento stesso giorno',
                    data=date(2026, 9, 2), origine='manuale'),
        AttivitaIst(tipo='scrutinio', titolo='Scrutinio giugno',
                    data=date(2027, 6, 10), classe='5A LLI', origine='manuale'),
    ])
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/piano-annuale?anno={ANNO}')
        assert r.status_code == 200

    mesi = catturato['kwargs']['mesi']
    etichette = [e for e, _ in mesi]
    # Ordine cronologico dell'anno scolastico: settembre prima di giugno
    assert etichette.index('settembre 2026') < etichette.index('giugno 2027')

    giorni_settembre = mesi[etichette.index('settembre 2026')][1]
    eventi_2_settembre = giorni_settembre[date(2026, 9, 2)]
    assert len(eventi_2_settembre) == 2  # i due eventi dello stesso giorno raggruppati


def test_piano_annuale_anno_vuoto(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    with app.test_client() as c:
        r = c.get(f'/attivita-ist/piano-annuale?anno={ANNO}')
        assert r.status_code == 200
    assert catturato['kwargs']['mesi'] == []
    assert catturato['kwargs']['n_eventi'] == 0


def test_riepilogo_ore_per_classe_somma_consigli_e_scrutini(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    db.session.add_all([
        AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LLI', data=date(2026, 10, 1),
                    classe='3A LLI', durata_min=60, origine='manuale'),
        AttivitaIst(tipo='scrutinio', titolo='Scrutinio 3A LLI', data=date(2027, 6, 10),
                    classe='3A LLI', durata_min=90, origine='manuale'),
        AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A CAT', data=date(2026, 10, 2),
                    classe='1A CAT', durata_min=45, origine='manuale'),
    ])
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    ore_per_classe = dict(catturato['kwargs']['ore_per_classe'])
    assert ore_per_classe['3A LLI'] == 2.5   # 60+90 min
    assert ore_per_classe['1A CAT'] == 0.75  # 45 min


def test_riepilogo_ore_per_docente_confronta_col_bucket(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    d = crea_docente('Rossi', tipo_contratto='TI')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 2),
                      durata_min=120, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    righe = catturato['kwargs']['riepilogo_docenti']
    assert len(righe) == 1
    assert righe[0]['docente'].cognome == 'Rossi'
    assert righe[0]['ore_a'] == 2.0
    assert righe[0]['ore_b'] == 0.0
    assert righe[0]['eccede_a'] is False


def test_riepilogo_ore_esclude_docente_gia_uscito_per_lanno_mostrato(app, db_session, monkeypatch):
    """Un docente convocato a un evento PRIMA che la sua uscita fosse
    segnalata (riga AttivitaIstPartecipante non si aggiorna da sola)
    non deve comparire nel riepilogo per l'anno in cui non è più in
    servizio — bug segnalato da Roberto dopo il fix delle tendine."""
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    d = crea_docente('Uscente', tipo_contratto='TI')
    d.anno_scol_uscita = ANNO
    d.motivo_uscita = 'pensionamento'
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 9, 2),
                      durata_min=120, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    assert catturato['kwargs']['riepilogo_docenti'] == []


def test_riepilogo_ore_docente_senza_eventi_non_compare(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    crea_docente('Bianchi')
    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200
    assert catturato['kwargs']['riepilogo_docenti'] == []


def test_riepilogo_ore_eccedenza_segnalata(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    d = crea_docente('Verdi', tipo_contratto='TI')
    for i in range(5):
        ev = AttivitaIst(tipo='collegio', titolo=f'Collegio {i}', data=date(2026, 9, 2 + i),
                          durata_min=600, origine='manuale')  # 10h l'uno, 50h totali > 40h
        db.session.add(ev)
        db.session.flush()
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    riga = catturato['kwargs']['riepilogo_docenti'][0]
    assert riga['ore_a'] == 50.0
    assert riga['eccede_a'] is True


# ── Placeholder di Assegnazioni non ancora nominati ──────────────────────────

def test_riepilogo_ore_mostra_placeholder_con_ore_consigli_classe(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    _placeholder('Supplente 1', 'AS48', ['3A LLI'])
    db.session.add(AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LLI',
                                data=date(2026, 10, 1), classe='3A LLI',
                                durata_min=90, origine='manuale'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    placeholder_righe = [r for r in catturato['kwargs']['riepilogo_docenti'] if r['is_placeholder']]
    assert len(placeholder_righe) == 1
    assert placeholder_righe[0]['etichetta'] == 'Supplente 1 — AS48'
    assert placeholder_righe[0]['ore_b'] == 1.5  # 90 min


def test_riepilogo_ore_placeholder_non_conta_ore_scrutinio(app, db_session, monkeypatch):
    """Gli scrutini sono fuori bucket (BUCKET_NO): non devono contribuire
    alle ore mostrate per un placeholder, solo i Consigli di classe."""
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    _placeholder('Supplente 2', 'A026', ['1A CAT'])
    db.session.add(AttivitaIst(tipo='scrutinio', titolo='Scrutinio 1A CAT',
                                data=date(2027, 6, 10), classe='1A CAT',
                                durata_min=120, origine='manuale'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    placeholder_righe = [r for r in catturato['kwargs']['riepilogo_docenti'] if r['is_placeholder']]
    assert placeholder_righe == []  # nessuna ora di bucket B, la riga non compare


def test_riepilogo_ore_mostra_placeholder_inserito_dopo_il_primo_caricamento(app, db_session, monkeypatch):
    """La route non ha nessuna cache: un placeholder creato DOPO aver
    già aperto la pagina deve comparire alla richiesta successiva senza
    bisogno di alcuna azione — risposta alla domanda di Roberto se
    l'elenco si aggiorna da solo quando ne inserisce uno nuovo."""
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    db.session.add(AttivitaIst(tipo='consiglio_classe', titolo='CdC 4A RIM',
                                data=date(2026, 10, 1), classe='4A RIM',
                                durata_min=60, origine='manuale'))
    db.session.commit()

    with app.test_client() as c:
        c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert not any(r['is_placeholder'] for r in catturato['kwargs']['riepilogo_docenti'])

        # Inserito ORA, dopo il primo caricamento della pagina
        _placeholder('Supplente nuovo', 'A-11', ['4A RIM'])

        c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        placeholder_righe = [r for r in catturato['kwargs']['riepilogo_docenti'] if r['is_placeholder']]
        assert len(placeholder_righe) == 1
        assert placeholder_righe[0]['etichetta'] == 'Supplente nuovo — A-11'


def test_riepilogo_ore_placeholder_sparisce_dopo_nomina(app, db_session, monkeypatch):
    catturato = _registra_blueprint_con_cattura(app, monkeypatch)
    asgn = _placeholder('Supplente 3', 'A012', ['2B AFM'])
    db.session.add(AttivitaIst(tipo='consiglio_classe', titolo='CdC 2B AFM',
                                data=date(2026, 10, 1), classe='2B AFM',
                                durata_min=60, origine='manuale'))
    db.session.commit()

    d = crea_docente('Reale')
    asgn.id_docente = d.id
    asgn.nome_placeholder = None
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/riepilogo-ore?anno={ANNO}')
        assert r.status_code == 200

    righe = catturato['kwargs']['riepilogo_docenti']
    assert not any(r['is_placeholder'] for r in righe)  # niente più placeholder
