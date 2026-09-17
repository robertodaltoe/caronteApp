"""
Roberto: comando dedicato in dashboard per assegnare un docente
(di potenziamento, o semplicemente libero quell'ora) a una classe per
potenziamento/compresenza — con l'esplicita richiesta che quel docente
non compaia più tra i disponibili per un'altra supplenza nella stessa
ora, pur restando selezionabile manualmente se serve dirottarlo
("può essere dirottato", confermato).

Copre:
1. routes/supplenze.py::nuovo_potenziamento() — crea una Supplenza per
   ciascuna ora selezionata, senza id_assente, tipo='potenziamento'.
2. modules/suggerimenti_supplenza.py::docenti_occupati_stessa_ora() —
   già distingueva occupati_pot_ids, verificato che continua a farlo.
3. routes/supplenze.py::api_suggerimenti() — il fix vero e proprio: un
   docente già assegnato a potenziamento/compresenza in
   quell'ora non deve comparire nei gruppi "liberi"/"potenziamento"
   per un'ALTRA supplenza nella stessa ora, ma in un gruppo a parte
   ("già assegnati"), selezionabile solo consapevolmente.
"""
from datetime import date

from models import db
from models.supplenza import Supplenza
from modules.suggerimenti_supplenza import docenti_occupati_stessa_ora
from tests.conftest import crea_docente

# Lunedì all'interno dell'anno scolastico 2026-2027 (giorno=0, non
# domenica) — evita date_sel.weekday() > 5 che la route tratta come
# "nessuna lezione".
LUNEDI = date(2026, 9, 21)


def _crea_tabelle(app):
    with app.app_context():
        from models.indisponibilita_ricorrente import IndisponibilitaRicorrente  # noqa
        from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse  # noqa
        db.create_all()


def _registra_blueprint(app):
    from routes.supplenze import supplenze_bp
    if 'supplenze' not in app.blueprints:
        app.register_blueprint(supplenze_bp)
    # nuovo_potenziamento() reindirizza a dashboard.index dopo il POST:
    # serve registrato anche se i test non toccano la dashboard stessa.
    from routes.dashboard import dashboard_bp
    if 'dashboard' not in app.blueprints:
        app.register_blueprint(dashboard_bp)


# ── nuovo_potenziamento() ─────────────────────────────────────────

def test_nuovo_potenziamento_crea_una_supplenza_per_ogni_ora(app, db_session):
    _crea_tabelle(app)
    _registra_blueprint(app)
    doc = crea_docente('Bianchi')

    with app.test_client() as c:
        r = c.post('/supplenze/potenziamento', data={
            'data': LUNEDI.isoformat(), 'classe': '3a lsu',
            'id_sostituto': str(doc.id), 'ore': ['2', '4', '5'],
        })
        assert r.status_code == 302

    supplenze = Supplenza.query.filter_by(id_sostituto=doc.id, data=LUNEDI).order_by(Supplenza.ora).all()
    assert [s.ora for s in supplenze] == [2, 4, 5]
    for s in supplenze:
        assert s.tipo == 'potenziamento'
        assert s.id_assente is None
        assert s.stato == 'assegnata'
        assert s.classe == '3A LSU'  # normalizzata in maiuscolo come le altre supplenze


def test_nuovo_potenziamento_non_duplica_se_gia_assegnato(app, db_session):
    """Rinviare lo stesso form (es. doppio click, o riassegnazione dalla
    stessa pagina) non deve creare righe duplicate per la stessa ora."""
    _crea_tabelle(app)
    _registra_blueprint(app)
    doc = crea_docente('Bianchi')

    with app.test_client() as c:
        for _ in range(2):
            c.post('/supplenze/potenziamento', data={
                'data': LUNEDI.isoformat(), 'classe': '3A LSU',
                'id_sostituto': str(doc.id), 'ore': ['2'],
            })

    assert Supplenza.query.filter_by(id_sostituto=doc.id, data=LUNEDI, ora=2).count() == 1


def test_nuovo_potenziamento_richiede_docente_classe_e_ore(app, db_session):
    _crea_tabelle(app)
    _registra_blueprint(app)

    with app.test_client() as c:
        r = c.post('/supplenze/potenziamento', data={'data': LUNEDI.isoformat(), 'classe': '', 'ore': []})
        assert r.status_code == 302

    assert Supplenza.query.count() == 0


# ── docenti_occupati_stessa_ora() (verifica del comportamento già
#    esistente su cui si basa il fix, non una regressione da correggere) ──

def test_docenti_occupati_stessa_ora_distingue_potenziamento(app, db_session):
    _crea_tabelle(app)
    doc_pot = crea_docente('Verdi')
    doc_normale = crea_docente('Neri')
    db.session.add(Supplenza(data=LUNEDI, ora=3, classe='3A LSU',
                              id_sostituto=doc_pot.id, tipo='potenziamento', stato='assegnata'))
    db.session.add(Supplenza(data=LUNEDI, ora=3, classe='2A CAT',
                              id_sostituto=doc_normale.id, tipo='recupero', stato='assegnata'))
    db.session.commit()

    occupati_ids, occupati_pot_ids = docenti_occupati_stessa_ora(LUNEDI, 3)

    assert occupati_pot_ids == {doc_pot.id}
    assert occupati_ids == {doc_normale.id}


# ── api_suggerimenti(): il fix vero e proprio ────────────────────────

def test_api_suggerimenti_esclude_dai_gruppi_liberi_chi_e_gia_a_potenziamento(app, db_session):
    """Il caso segnalato da Roberto: un docente assegnato a
    potenziamento/compresenza in un'ora non deve più comparire come
    "libero" quando si cerca un sostituto per un'ALTRA supplenza nella
    stessa ora."""
    _crea_tabelle(app)
    _registra_blueprint(app)
    libero = crea_docente('Rossi')  # nessun impegno in orario quel giorno -> "libero"

    db.session.add(Supplenza(data=LUNEDI, ora=3, classe='3A LSU',
                              id_sostituto=libero.id, tipo='potenziamento', stato='assegnata'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=3')
        assert r.status_code == 200
        payload = r.get_json()

    gruppi_normali = {'lib', 'adj', 'pot', 'comp'}
    for gruppo in payload['gruppi']:
        if gruppo['key'] in gruppi_normali:
            assert libero.id not in {d['id'] for d in gruppo['docenti']}, (
                f"{libero.cognome} non doveva comparire nel gruppo '{gruppo['key']}': "
                f"è già assegnato a potenziamento in quest'ora")

    gruppo_occupato = next((g for g in payload['gruppi'] if g['key'] == 'pot_occupato'), None)
    assert gruppo_occupato is not None
    assert libero.id in {d['id'] for d in gruppo_occupato['docenti']}


def test_api_suggerimenti_non_influenza_altre_ore(app, db_session):
    """L'assegnazione a potenziamento vale solo per l'ora in cui è
    stata fatta: lo stesso docente deve restare disponibile in
    un'ora diversa dello stesso giorno."""
    _crea_tabelle(app)
    _registra_blueprint(app)
    doc = crea_docente('Rossi')
    # Serve almeno un'ora in orario quel giorno, altrimenti la route lo
    # tratta come "non in servizio" e lo esclude sempre (comportamento
    # preesistente, non legato a questo fix) — un'ora lontana da quella
    # testata (3 e 4), così non interferisce con nessuna delle due.
    from models.orario_docente import OrarioDocente
    db.session.add(OrarioDocente(id_docente=doc.id, giorno=LUNEDI.weekday(), ora=8,
                                  classe='1A TEST', materia='Test', tipo_ora='lezione'))

    db.session.add(Supplenza(data=LUNEDI, ora=3, classe='3A LSU',
                              id_sostituto=doc.id, tipo='potenziamento', stato='assegnata'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=4')
        payload = r.get_json()

    tutti_gli_id = {d['id'] for g in payload['gruppi'] for d in g['docenti']}
    assert doc.id in tutti_gli_id
    gruppo_occupato = next((g for g in payload['gruppi'] if g['key'] == 'pot_occupato'), None)
    assert gruppo_occupato is None or doc.id not in {d['id'] for d in gruppo_occupato['docenti']}
