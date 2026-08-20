"""
Generatore Consigli di Classe (Piano Annuale delle Attività, Fase 3).
Test sulla logica pura di modules/generatore_cdc.py — la maggior parte
usa un docenti_map fittizio (monkeypatch di docenti_reali_per_classe)
per isolare la logica di scheduling dal setup di Assegnazioni; un test
dedicato verifica anche la query reale.
"""
from datetime import date
from models import db
import modules.generatore_cdc as gcdc
from models.generatore_cdc import VincoloOrarioClasse, VincoloGeneratoreCdc
from models.sospensione import SospensioneDidattica
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.classe_concorso import ClasseConcorso
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _fissa_docenti(monkeypatch, mappa):
    monkeypatch.setattr(gcdc, 'docenti_reali_per_classe', lambda anno_scol: mappa)


def test_due_classi_senza_docenti_comuni_stesso_slot(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {3, 4}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 18),
        '14:00', '18:00', durata_min=60)
    assert all(not r['conflitto'] for r in ris)
    a = next(r for r in ris if r['classe'] == '1A LLI')
    b = next(r for r in ris if r['classe'] == '1A CAT')
    assert (a['data'], a['ora_inizio']) == (b['data'], b['ora_inizio'])


def test_due_classi_con_docente_comune_slot_diversi(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {2, 5}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 18),
        '14:00', '18:00', durata_min=60)
    assert all(not r['conflitto'] for r in ris)
    a = next(r for r in ris if r['classe'] == '1A LLI')
    b = next(r for r in ris if r['classe'] == '1A CAT')
    assert (a['data'], a['ora_inizio']) != (b['data'], b['ora_inizio'])


def test_vincolo_orario_esclude_slot_per_indirizzo(db_session, monkeypatch):
    """Martedì 13:30-15:30 CAT non è libero da lezione (rientro
    pomeridiano) — il generatore non deve proporre quello slot per CAT."""
    _fissa_docenti(monkeypatch, {'1A CAT': {1}})
    martedi = date(2026, 9, 15)
    assert martedi.weekday() == 1
    db.session.add(VincoloOrarioClasse(
        giorno_settimana=1, ora_inizio='13:30', ora_fine='15:30',
        indirizzi='CAT', descrizione='Rientro pomeridiano'))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A CAT'], martedi, martedi, '13:30', '15:30', durata_min=60)
    # Unico giorno nel periodo è il martedì vincolato: nessuno slot libero
    assert ris[0]['conflitto'] is True


def test_vincolo_orario_non_si_applica_ad_altro_indirizzo(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1}})
    martedi = date(2026, 9, 15)
    db.session.add(VincoloOrarioClasse(
        giorno_settimana=1, ora_inizio='13:30', ora_fine='15:30',
        indirizzi='CAT', descrizione='Rientro pomeridiano CAT'))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI'], martedi, martedi, '13:30', '15:30', durata_min=60)
    assert ris[0]['conflitto'] is False  # LLI non è coinvolto dal vincolo CAT


def test_vincolo_entro_data_rispetta_scadenza(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': set()})
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='entro_data',
        scadenza=date(2026, 9, 15)))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT'], date(2026, 9, 14), date(2026, 9, 20),
        '14:00', '15:00', durata_min=60)
    assert ris[0]['conflitto'] is False
    assert ris[0]['data'] <= date(2026, 9, 15)


def test_vincolo_entro_data_senza_slot_prima_della_scadenza_da_conflitto(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': set()})
    lunedi_sospeso = date(2026, 9, 14)
    db.session.add(SospensioneDidattica(
        data_inizio=lunedi_sospeso, data_fine=lunedi_sospeso, descrizione='Sciopero'))
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='entro_data',
        scadenza=lunedi_sospeso))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT'], lunedi_sospeso, date(2026, 9, 20),
        '14:00', '15:00', durata_min=60)
    assert ris[0]['conflitto'] is True


def test_vincolo_fisso_piazza_allo_slot_esatto(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': set()})
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='fissa',
        data_fissa=date(2026, 9, 16), ora_fissa='16:00'))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT'], date(2026, 9, 14), date(2026, 9, 20),
        '14:00', '18:00', durata_min=60)
    assert ris[0]['conflitto'] is False
    assert ris[0]['data'] == date(2026, 9, 16)
    assert ris[0]['ora_inizio'] == '16:00'


def test_vincolo_fisso_in_conflitto_con_altro_fisso_da_errore(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'5A CAT': {1}, '5A LLI': {1}})  # docente condiviso
    slot = (date(2026, 9, 16), '16:00')
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A CAT', tipo='fissa',
        data_fissa=slot[0], ora_fissa=slot[1]))
    db.session.add(VincoloGeneratoreCdc(
        anno_scol=ANNO, classe='5A LLI', tipo='fissa',
        data_fissa=slot[0], ora_fissa=slot[1]))
    db.session.commit()

    ris = gcdc.genera_bozza_cdc(
        ANNO, ['5A CAT', '5A LLI'], date(2026, 9, 14), date(2026, 9, 20),
        '14:00', '18:00', durata_min=60)
    esiti = {r['classe']: r['conflitto'] for r in ris}
    # La prima piazzata occupa lo slot, la seconda (stesso slot fisso,
    # docente condiviso) va in conflitto — non può essere spostata da sola
    assert sum(esiti.values()) == 1


def test_presenza_ds_impedisce_stesso_slot_anche_senza_docenti_comuni(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {3, 4}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 14),
        '14:00', '15:00', durata_min=60,  # un solo slot disponibile in tutto il periodo
        classi_richiedono_ds={'1A LLI', '1A CAT'})
    esiti = {r['classe']: r['conflitto'] for r in ris}
    # Un solo slot esiste: non possono starci entrambe se richiedono il DS
    assert sum(esiti.values()) == 1


def test_ds_non_conflitto_se_solo_una_classe_lo_richiede(db_session, monkeypatch):
    _fissa_docenti(monkeypatch, {'1A LLI': {1, 2}, '1A CAT': {3, 4}})
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A LLI', '1A CAT'], date(2026, 9, 14), date(2026, 9, 14),
        '14:00', '15:00', durata_min=60,
        classi_richiedono_ds={'1A LLI'})
    assert all(not r['conflitto'] for r in ris)
    a = next(r for r in ris if r['classe'] == '1A LLI')
    b = next(r for r in ris if r['classe'] == '1A CAT')
    assert (a['data'], a['ora_inizio']) == (b['data'], b['ora_inizio'])  # stesso slot, ok


def test_preferenza_stesso_indirizzo_a_parita_di_condizioni(db_session, monkeypatch):
    """Tre classi CAT senza docenti comuni e una LLI: il generatore deve
    preferire accorpare le CAT tra loro quando possibile, non sparpagliarle."""
    _fissa_docenti(monkeypatch, {
        '1A CAT': {1}, '2A CAT': {2}, '3A CAT': {3}, '1A LLI': {4},
    })
    ris = gcdc.genera_bozza_cdc(
        ANNO, ['1A CAT', '2A CAT', '3A CAT', '1A LLI'],
        date(2026, 9, 14), date(2026, 9, 18), '14:00', '18:00', durata_min=60)
    cat_slots = {(r['data'], r['ora_inizio']) for r in ris if 'CAT' in r['classe']}
    assert len(cat_slots) == 1  # tutte e tre le CAT nello stesso slot


def test_giorni_lavorativi_esclude_domenica_e_sospensioni(db_session):
    db.session.add(SospensioneDidattica(
        data_inizio=date(2026, 9, 16), data_fine=date(2026, 9, 16), descrizione='Festa'))
    db.session.commit()
    giorni = gcdc.giorni_lavorativi(date(2026, 9, 13), date(2026, 9, 20))  # dom 13 - dom 20
    assert date(2026, 9, 13) not in giorni  # domenica
    assert date(2026, 9, 16) not in giorni  # sospensione
    assert date(2026, 9, 14) in giorni
    assert date(2026, 9, 19) in giorni  # sabato incluso


# ── Query reale (non monkeypatchata) ─────────────────────────────────────────

def test_docenti_reali_per_classe_dalle_assegnazioni(db_session):
    cc = ClasseConcorso(codice='A026', nome='Matematica')
    db.session.add(cc)
    db.session.commit()
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')

    asgn1 = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id, id_docente=d1.id, tipo='titolare')
    db.session.add(asgn1)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn1.id, indirizzo='LLI', anno_corso=3, sezione='A', ore=4))

    # Placeholder: non deve comparire nella mappa
    asgn2 = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id, nome_placeholder='Da nominare', tipo='supplente')
    db.session.add(asgn2)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn2.id, indirizzo='LLI', anno_corso=3, sezione='A', ore=2))
    db.session.commit()

    mappa = gcdc.docenti_reali_per_classe(ANNO)
    assert mappa['3A LLI'] == {d1.id}


# ── Anno di default: attività preparatoria per il nuovo anno ────────────────

def test_pagina_generatore_apre_di_default_sullanno_in_preparazione(app, db_session, monkeypatch):
    """Il Piano Annuale è un'attività preparatoria per il nuovo anno,
    come Assegnazioni/richiesta organico — la pagina deve aprirsi di
    default sull'anno in preparazione (_anno_default_piano), non
    sull'anno scolastico corrente calcolato dalla data odierna. Bug
    segnalato da Roberto: nessun modo di selezionare 2026-2027."""
    from routes.generatore_cdc import generatore_cdc_bp
    if 'generatore_cdc' not in app.blueprints:
        app.register_blueprint(generatore_cdc_bp)

    from models.piano_studi import PianoStudi
    cc = ClasseConcorso(codice='A026', nome='Matematica')
    db.session.add(cc)
    db.session.commit()
    db.session.add(PianoStudi(
        anno_scol=ANNO, indirizzo='LLI', anno_corso=3,
        id_classe_concorso=cc.id, ore_settimanali=4))
    db.session.commit()

    catturato = {}
    import routes.generatore_cdc as mod

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get('/generatore-cdc')  # nessun ?anno= esplicito
        assert r.status_code == 200

    assert catturato['kwargs']['anno'] == ANNO


# ── Scrutini nello stesso generatore ─────────────────────────────────────────

def _registra(app):
    from routes.generatore_cdc import generatore_cdc_bp
    from routes.attivita_ist import attivita_ist_bp
    if 'generatore_cdc' not in app.blueprints:
        app.register_blueprint(generatore_cdc_bp)
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(attivita_ist_bp)


def test_genera_scrutinio_usa_tipo_e_durata_corretti(app, db_session, monkeypatch):
    """Stessa logica di raggruppamento dei Consigli, ma tipo/durata di
    default diversi — richiesto da Roberto: gli scrutini seguono la
    stessa regola dei Consigli di classe."""
    _registra(app)
    _fissa_docenti(monkeypatch, {'1A LLI': {1}})

    catturato = {}
    import routes.generatore_cdc as mod

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.post('/generatore-cdc', data={
            'azione': 'genera', 'anno_scol': ANNO, 'tipo': 'scrutinio',
            'classi': ['1A LLI'],
            'n_turni': '1', 'data_inizio_0': '2026-09-14', 'data_fine_0': '2026-09-18',
            'ora_inizio_giorno': '14:00', 'ora_fine_giorno': '18:00',
            'durata_min': '45',
        })
        assert r.status_code == 200

    assert catturato['kwargs']['tipo'] == 'scrutinio'
    assert catturato['kwargs']['tipo_label'] == 'Scrutinio'
    assert catturato['kwargs']['bozza'][0]['conflitto'] is False


def test_conferma_scrutinio_crea_eventi_tipo_scrutinio(app, db_session):
    _registra(app)
    with app.test_client() as c:
        r = c.post('/generatore-cdc', data={
            'azione': 'conferma', 'anno_scol': ANNO, 'tipo': 'scrutinio',
            'n_righe': '1',
            'classe_0': '1A LLI', 'data_0': '2026-09-14',
            'ora_inizio_0': '14:00', 'ora_fine_0': '14:45',
        }, follow_redirects=False)
        assert r.status_code == 302

    from models.attivita_ist import AttivitaIst
    ev = AttivitaIst.query.filter_by(tipo='scrutinio', classe='1A LLI').first()
    assert ev is not None
    assert ev.titolo == 'Scrutinio 1A LLI'


# ── GLO nello stesso generatore ──────────────────────────────────────────────

def test_genera_glo_richiede_comunque_selezione_classi(app, db_session, monkeypatch):
    """Richiesta di Roberto: selezionando GLO si sceglie comunque
    l'elenco classi del turno, stesso form degli altri tipi — l'unica
    differenza è l'insieme docenti usato per evitare sovrapposizioni
    (l'intera classe, per eccesso, non solo chi segue quello specifico
    alunno — non c'è un dato più preciso da cui partire)."""
    _registra(app)
    _fissa_docenti(monkeypatch, {'2A LLI': {7}})

    catturato = {}
    import routes.generatore_cdc as mod

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.post('/generatore-cdc', data={
            'azione': 'genera', 'anno_scol': ANNO, 'tipo': 'glo',
            'classi': ['2A LLI'],
            'n_turni': '1', 'data_inizio_0': '2026-09-14', 'data_fine_0': '2026-09-18',
            'ora_inizio_giorno': '14:00', 'ora_fine_giorno': '18:00',
            'durata_min': '45',
        })
        assert r.status_code == 200

    assert catturato['kwargs']['tipo'] == 'glo'
    assert catturato['kwargs']['tipo_label'] == 'GLO'
    assert catturato['kwargs']['bozza'][0]['classe'] == '2A LLI'
    assert catturato['kwargs']['bozza'][0]['conflitto'] is False


def test_conferma_glo_crea_evento_tipo_glo(app, db_session):
    _registra(app)
    with app.test_client() as c:
        r = c.post('/generatore-cdc', data={
            'azione': 'conferma', 'anno_scol': ANNO, 'tipo': 'glo',
            'n_righe': '1',
            'classe_0': '2A LLI', 'data_0': '2026-09-14',
            'ora_inizio_0': '14:00', 'ora_fine_0': '14:45',
        }, follow_redirects=False)
        assert r.status_code == 302

    from models.attivita_ist import AttivitaIst
    ev = AttivitaIst.query.filter_by(tipo='glo', classe='2A LLI').first()
    assert ev is not None
    assert ev.titolo == 'GLO 2A LLI'


# ── Turni multipli nello stesso invio ────────────────────────────────────────

def test_due_turni_generano_bozze_indipendenti_nello_stesso_invio(app, db_session, monkeypatch):
    """Richiesta di Roberto: poter scegliere quanti turni di Consigli
    predisporre (es. ottobre e marzo) in un solo invio, stesse classi
    per ognuno, generati indipendentemente l'uno dall'altro."""
    _registra(app)
    _fissa_docenti(monkeypatch, {'1A LLI': {1}})

    catturato = {}
    import routes.generatore_cdc as mod

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.post('/generatore-cdc', data={
            'azione': 'genera', 'anno_scol': ANNO, 'tipo': 'consiglio_classe',
            'classi': ['1A LLI'],
            'n_turni': '2',
            'data_inizio_0': '2026-10-05', 'data_fine_0': '2026-10-09',
            'data_inizio_1': '2027-03-08', 'data_fine_1': '2027-03-12',
            'ora_inizio_giorno': '14:00', 'ora_fine_giorno': '18:00',
            'durata_min': '60',
        })
        assert r.status_code == 200

    bozza = catturato['kwargs']['bozza']
    assert catturato['kwargs']['n_turni'] == 2
    assert len(bozza) == 2  # una riga per turno, stessa classe
    turni = {r['turno']: r['data'] for r in bozza}
    assert turni[1] < date(2027, 1, 1)   # primo turno in ottobre
    assert turni[2] >= date(2027, 3, 1)  # secondo turno in marzo


def test_turno_senza_date_viene_ignorato(app, db_session, monkeypatch):
    """Un turno aggiunto e poi rimosso lato client non invia i suoi
    campi: la route non deve inciampare su un indice mancante."""
    _registra(app)
    _fissa_docenti(monkeypatch, {'1A LLI': {1}})

    catturato = {}
    import routes.generatore_cdc as mod

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.post('/generatore-cdc', data={
            'azione': 'genera', 'anno_scol': ANNO, 'tipo': 'consiglio_classe',
            'classi': ['1A LLI'],
            'n_turni': '3',  # il turno 1 (indice 1) non ha campi: rimosso lato client
            'data_inizio_0': '2026-10-05', 'data_fine_0': '2026-10-09',
            'data_inizio_2': '2027-03-08', 'data_fine_2': '2027-03-12',
            'ora_inizio_giorno': '14:00', 'ora_fine_giorno': '18:00',
            'durata_min': '60',
        })
        assert r.status_code == 200

    assert catturato['kwargs']['n_turni'] == 2  # solo i due turni con date valide


# ── Riunioni dipartimento/materia: nessun motore, solo piazzamento ──────────

def _registra_dip(app):
    from routes.generatore_cdc import generatore_cdc_bp
    from routes.attivita_ist import attivita_ist_bp
    if 'generatore_cdc' not in app.blueprints:
        app.register_blueprint(generatore_cdc_bp)
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(attivita_ist_bp)


def _dipartimento(nome, sigla):
    from models.materia import Dipartimento
    d = Dipartimento(nome=nome, sigla=sigla)
    db.session.add(d)
    db.session.commit()
    return d


def test_dipartimenti_bozza_piazza_tutti_nello_stesso_slot_senza_verificare_conflitti(app, db_session, monkeypatch):
    """Richiesta di Roberto: i dipartimenti non condividono mai docenti,
    quindi si piazzano semplicemente, anche tutti nella stessa data/ora
    — nessun controllo di sovrapposizione da fare."""
    _registra_dip(app)
    d1 = _dipartimento('Lettere', 'LET')
    d2 = _dipartimento('Matematica e Fisica', 'MATFIS')

    catturato = {}
    import routes.generatore_cdc as mod

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.post('/generatore-cdc/dipartimenti', data={
            'azione': 'genera', 'anno_scol': ANNO, 'tipo': 'dipartimento',
            'dipartimenti': [str(d1.id), str(d2.id)],
            'data': '2026-10-15', 'ora_inizio': '15:00', 'durata_min': '60',
        })
        assert r.status_code == 200

    righe = catturato['kwargs']['righe']
    assert len(righe) == 2
    # Stessa data/ora per entrambi: nessuna logica di conflitto le separa
    assert righe[0]['data'] == righe[1]['data'] == '2026-10-15'
    assert righe[0]['ora_inizio'] == righe[1]['ora_inizio'] == '15:00'


def test_conferma_dipartimenti_crea_eventi_con_partecipanti_da_docente_materia(app, db_session):
    _registra_dip(app)
    d1 = _dipartimento('Lettere', 'LET')
    doc = crea_docente('Verdi')

    from models.materia import Materia, DocenteMateria
    mat = Materia(nome='Italiano', sigla='ITA', id_dipartimento=d1.id)
    db.session.add(mat)
    db.session.commit()
    db.session.add(DocenteMateria(id_docente=doc.id, id_materia=mat.id, anno_scol=ANNO))
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/generatore-cdc/dipartimenti', data={
            'azione': 'conferma', 'anno_scol': ANNO, 'tipo': 'dipartimento',
            'n_righe': '1',
            'id_dipartimento_0': str(d1.id), 'sigla_0': 'LET',
            'data_0': '2026-10-15', 'ora_inizio_0': '15:00', 'ora_fine_0': '16:00',
        }, follow_redirects=False)
        assert r.status_code == 302

    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
    ev = AttivitaIst.query.filter_by(tipo='dipartimento', id_dipartimento=d1.id).first()
    assert ev is not None
    assert ev.titolo == 'Riunione dipartimento LET'
    partecipanti = AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()
    assert {p.id_docente for p in partecipanti} == {doc.id}
