"""
routes/generatore_cdc.py::eventi_unici() — Collegio, Incontro
scuola-famiglia, e il nuovo tipo "riunione_extra" (Commissione, Staff
o altro gruppo ad hoc, richiesto da Roberto: non rientra in nessun
bucket normativo, partecipanti scelti a mano invece che "tutti" o
"coordinatori").

Verifica anche che, dopo la creazione, si torni sulla stessa pagina
(non più al Piano Annuale) — stesso motivo già applicato al generatore
CdC/scrutini e a quello dipartimenti (addendum 69): Roberto crea più
eventi di seguito e vuole restare dove stava lavorando.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, TIPI_ATTIVITA, BUCKET_NO
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _registra_blueprint(app):
    import routes.generatore_cdc as mod
    if 'generatore_cdc' not in app.blueprints:
        app.register_blueprint(mod.generatore_cdc_bp)


def test_riunione_extra_e_fuori_conteggio():
    assert TIPI_ATTIVITA['riunione_extra']['bucket'] == BUCKET_NO


def test_riunione_extra_usa_solo_i_docenti_scelti_a_mano(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    d3 = crea_docente('Verdi')  # non selezionato, non deve comparire

    with app.test_client() as c:
        r = c.post('/generatore-cdc/eventi-unici', data={
            'anno_scol': ANNO, 'tipo': 'riunione_extra',
            'titolo': 'Commissione elettorale',
            'data': '2026-10-05', 'ora_inizio': '15:00', 'durata_min': '60',
            'docenti_manuali': [str(d1.id), str(d2.id)],
        })
        assert r.status_code == 302

    ev = AttivitaIst.query.filter_by(tipo='riunione_extra').first()
    assert ev is not None
    assert ev.titolo == 'Commissione elettorale'
    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert ids == {d1.id, d2.id}
    assert d3.id not in ids


def test_riunione_extra_torna_alla_stessa_pagina_non_al_piano_annuale(app, db_session):
    _registra_blueprint(app)
    with app.test_client() as c:
        r = c.post('/generatore-cdc/eventi-unici', data={
            'anno_scol': ANNO, 'tipo': 'riunione_extra',
            'titolo': 'Staff di dirigenza',
            'data': '2026-10-05', 'ora_inizio': '15:00', 'durata_min': '60',
            'docenti_manuali': [],
        })
        assert r.status_code == 302
        assert r.headers['Location'] == f'/generatore-cdc/eventi-unici?anno={ANNO}'


def test_collegio_torna_alla_stessa_pagina_non_al_piano_annuale(app, db_session):
    """Stesso comportamento anche per i tipi preesistenti (Collegio,
    Incontro scuola-famiglia), non solo per il nuovo riunione_extra."""
    _registra_blueprint(app)
    with app.test_client() as c:
        r = c.post('/generatore-cdc/eventi-unici', data={
            'anno_scol': ANNO, 'tipo': 'collegio',
            'data': '2026-10-05', 'ora_inizio': '15:00', 'durata_min': '60',
        })
        assert r.status_code == 302
        assert r.headers['Location'] == f'/generatore-cdc/eventi-unici?anno={ANNO}'


# ── Checklist docenti per "Altra riunione": sezioni per incarico + ──────────
# selettori rapidi. Roberto: l'elenco deve mostrare i docenti in
# servizio per l'anno del piano, divisi in sezioni per categoria di
# incarico (chi non ne ha nessuno in una sezione "Altri"), con un
# pulsante rapido per categoria E per singolo tipo (es. "Funzioni
# strumentali" seleziona tutti quelli con QUALUNQUE incarico in quella
# categoria, "Commissione orario" solo chi ha esattamente quel tipo) —
# costruiti dai dati, non da un elenco scritto a mano, così un nuovo
# incarico aggiunto in futuro compare da solo.

def _crea_incarico(db_session, cat_codice, cat_nome, tipo_nome, docente, anno=ANNO):
    from models.incarico import CategoriaIncarico, TipoIncarico, IncaricaDocente
    cat = CategoriaIncarico.query.filter_by(codice=cat_codice).first()
    if not cat:
        cat = CategoriaIncarico(codice=cat_codice, nome=cat_nome)
        db.session.add(cat)
        db.session.commit()
    tipo = TipoIncarico.query.filter_by(nome=tipo_nome).first()
    if not tipo:
        tipo = TipoIncarico(nome=tipo_nome, categoria=cat_codice)
        db.session.add(tipo)
        db.session.commit()
    db.session.add(IncaricaDocente(anno_scol=anno, id_tipo_incarico=tipo.id, id_docente=docente.id))
    db.session.commit()
    return cat, tipo


def test_docente_con_incarico_finisce_nella_sua_sezione(app, db_session):
    from routes.generatore_cdc import _docenti_per_riunione_extra
    fs = crea_docente('Bianchi')
    _crea_incarico(db_session, 'funzione_strumentale', 'Funzioni strumentali',
                    'FS PTOF', fs)
    senza = crea_docente('Verdi')

    sezioni, altri, _ = _docenti_per_riunione_extra(ANNO)
    assert len(sezioni) == 1
    assert sezioni[0]['categoria'].nome == 'Funzioni strumentali'
    ids_sezione = {d.id for d, _ in sezioni[0]['docenti']}
    assert ids_sezione == {fs.id}
    assert {d.id for d in altri} == {senza.id}


def test_selettore_rapido_categoria_prende_qualunque_tipo_in_quella_categoria(app, db_session):
    from routes.generatore_cdc import _docenti_per_riunione_extra
    d1 = crea_docente('Bianchi')
    d2 = crea_docente('Neri')
    _crea_incarico(db_session, 'funzione_strumentale', 'Funzioni strumentali', 'FS PTOF', d1)
    _crea_incarico(db_session, 'funzione_strumentale', 'Funzioni strumentali', 'FS Inclusione', d2)

    _, _, selettori = _docenti_per_riunione_extra(ANNO)
    sel_categoria = next(s for s in selettori if s['label'] == 'Funzioni strumentali')
    assert set(sel_categoria['docenti_ids']) == {d1.id, d2.id}


def test_selettore_rapido_tipo_prende_solo_quel_tipo_specifico(app, db_session):
    from routes.generatore_cdc import _docenti_per_riunione_extra
    d1 = crea_docente('Bianchi')
    d2 = crea_docente('Neri')
    _crea_incarico(db_session, 'fis', 'FIS', 'Commissione orario', d1)
    _crea_incarico(db_session, 'fis', 'FIS', 'Commissione GLI', d2)

    _, _, selettori = _docenti_per_riunione_extra(ANNO)
    sel_tipo = next(s for s in selettori if s['label'] == 'Commissione orario')
    assert set(sel_tipo['docenti_ids']) == {d1.id}


def test_docente_non_in_servizio_escluso_da_sezioni_e_altri(app, db_session):
    from routes.generatore_cdc import _docenti_per_riunione_extra
    from models.docente import Docente
    fuori = crea_docente('Uscito')
    fuori.status_presenza = 'aspettativa'
    db.session.commit()

    sezioni, altri, selettori = _docenti_per_riunione_extra(ANNO)
    tutti_ids = {d.id for d in altri}
    for sez in sezioni:
        tutti_ids |= {d.id for d, _ in sez['docenti']}
    assert fuori.id not in tutti_ids
