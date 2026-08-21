"""
Test di regressione: Roberto segnala che A-21 (Geografia) non compare
mai in Assegnazioni, pur avendo ore reali nel piano di studi 2026-2027
(1A/1B AFM, 1A/1B CAT).

Causa: routes/assegnazioni.py::AREE è un elenco fisso di codici CC per
area disciplinare, scritto a mano — _build_area() itera solo su
area['cc'] e ignora del tutto qualsiasi ClasseConcorso il cui codice
non sia in quell'elenco, anche se attiva e con ore nel piano studi.
A-21 esisteva in anagrafica ma non era mai stata aggiunta ad AREE.

Questo test previene la ricomparsa del problema per qualsiasi futura
classe di concorso attiva non-sostegno aggiunta all'anagrafica ma
dimenticata in AREE.
"""
from models import db
from models.classe_concorso import ClasseConcorso
from routes.assegnazioni import AREE


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()


def _codici_in_aree():
    codici = set()
    for area in AREE:
        codici.update(area['cc'])
    return codici


def test_a21_geografia_e_nellelenco_aree():
    assert 'A-21' in _codici_in_aree()


def test_ogni_cc_attiva_non_sostegno_e_in_qualche_area(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        db.session.add_all([
            ClasseConcorso(codice='A-99', nome='CC di prova', tipo_posto='cattedra', attiva=True),
            ClasseConcorso(codice='A-98', nome='CC disattivata', tipo_posto='cattedra', attiva=False),
            ClasseConcorso(codice='SOS-1', nome='Sostegno', tipo_posto='sostegno', attiva=True),
        ])
        db.session.commit()

        codici_area = _codici_in_aree()
        attive_non_sostegno = ClasseConcorso.query.filter_by(attiva=True).filter(
            ClasseConcorso.tipo_posto != 'sostegno').all()

        mancanti = [cc.codice for cc in attive_non_sostegno if cc.codice not in codici_area]
        # 'A-99' è nuova apposta, non in AREE: verifica che il test la
        # noti davvero (altrimenti il controllo sotto sarebbe vuoto per
        # sbaglio, non perché tutto è a posto).
        assert 'A-99' in mancanti
        mancanti.remove('A-99')
        assert mancanti == [], f'Classi di concorso attive assenti da AREE: {mancanti}'
