"""
Caso reale segnalato da Roberto: un docente con cattedra spezzata su
due scuole (9 ore qui) che entra in ruolo e passa a cattedra intera
(18 ore solo qui) dall'anno successivo — caso Palermo. Il valore
"ore contratto" base va aggiornato al nuovo regime (18h, valido da
quell'anno in poi), ma l'anno passato/in corso deve continuare a
vedere le vere 9 ore — meccanismo già esistente
(Docente.ore_max_anno/anno_scol_ore_max), ma routes/assegnazioni.py
lo ignorava nei controlli "ore eccessive": usava sempre
Docente.ore_max_effettive (il campo base, aggiornato al nuovo
regime), non il valore per l'anno specifico dell'assegnazione.
"""
from models import db
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.classe_concorso import ClasseConcorso
from tests.conftest import crea_docente


def _cc(codice='B-14'):
    cc = ClasseConcorso(codice=codice, nome='Costruzioni')
    db.session.add(cc)
    db.session.commit()
    return cc


def _palermo():
    """Docente con ore_contratto=18 (nuovo regime, dal 2026-2027) ma
    ore_max_anno=9 per il 2025-2026 (il vero valore di quell'anno,
    cattedra ancora spezzata su due scuole)."""
    d = crea_docente('Palermo', tipo_contratto='TI')
    d.ore_contratto = 18
    d.ore_max_anno = 9
    d.anno_scol_ore_max = '2025-2026'
    db.session.commit()
    return d


def test_nomina_rispetta_ore_max_dellanno_non_il_contratto_base(app, db_session):
    import routes.assegnazioni as mod
    if 'assegnazioni' not in app.blueprints:
        app.register_blueprint(mod.assegnazioni_bp)

    doc = _palermo()
    cc = _cc()

    # Assegnazione 2025-2026: 10 ore su una classe — supera le sue vere
    # 9 ore di quell'anno, anche se il campo base ora dice 18.
    asgn_2526 = AssegnazioneDocente(anno_scol='2025-2026', id_classe_concorso=cc.id,
                                     nome_placeholder='Supplente', tipo='supplente')
    db.session.add(asgn_2526)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn_2526.id, indirizzo='CAT',
                                       anno_corso=3, sezione='A', ore=10))
    db.session.commit()

    with app.test_client() as c:
        c.post(f'/assegnazioni/{asgn_2526.id}/nomina', data={'id_docente': doc.id})

    db.session.refresh(asgn_2526)
    assert asgn_2526.id_docente is None  # rifiutata: 10h > 9h del 2025-2026

    # Stessa cosa ma per il 2026-2027 (nuovo regime, 18h): 10 ore
    # rientrano tranquillamente.
    asgn_2627 = AssegnazioneDocente(anno_scol='2026-2027', id_classe_concorso=cc.id,
                                     nome_placeholder='Supplente', tipo='supplente')
    db.session.add(asgn_2627)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn_2627.id, indirizzo='CAT',
                                       anno_corso=3, sezione='A', ore=10))
    db.session.commit()

    with app.test_client() as c:
        c.post(f'/assegnazioni/{asgn_2627.id}/nomina', data={'id_docente': doc.id})

    db.session.refresh(asgn_2627)
    assert asgn_2627.id_docente == doc.id  # accettata: 10h <= 18h del 2026-2027


def test_modifica_docente_salva_lanno_dellore_max_override(app, db_session):
    """Roberto: impostava "Ore max (override)" = 9 per il 2025-2026 dalla
    scheda docente, ma continuava a vedere 18 (il contratto base) in
    anagrafica per quell'anno. Causa: routes/docenti.py::modifica()
    salvava ore_max_anno dal form ma non anno_scol_ore_max — il campo
    accoppiato che dice A QUALE anno si riferisce quel numero — quindi
    l'override non trovava mai corrispondenza con l'anno richiesto e
    ore_max_effettive_per_anno() ricadeva sempre sul contratto base."""
    import routes.docenti as mod
    from concorrenza import versione_str
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    d = crea_docente('PalermoModifica', tipo_contratto='TI')
    d.ore_contratto = 18
    db.session.commit()

    with app.test_client() as c:
        r = c.post(f'/docenti/{d.id}/modifica', data={
            'cognome': d.cognome, 'nome': d.nome,
            'ore_contratto': '18',
            'ore_max_anno': '9',
            'anno_scol_ore_max': '2025-2026',
            'tipo_contratto': 'TI',
            'ruolo': 'titolare',
            'tipo_servizio': 'full',
            'versione': versione_str(d.modificato_il),
        })
        assert r.status_code == 302

    db.session.refresh(d)
    assert d.ore_max_anno == 9
    assert d.anno_scol_ore_max == '2025-2026'
    assert d.ore_max_effettive_per_anno('2025-2026') == 9
    assert d.ore_max_effettive_per_anno('2026-2027') == 18
