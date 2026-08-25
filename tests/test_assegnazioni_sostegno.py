"""
Roberto: in Assegnazioni non c'era modo di gestire le ore di sostegno —
la CC ADSS (tipo_posto='sostegno') non compariva perché l'elenco classi
(_classi_per_cc) viene derivato dal piano studi, e il sostegno non ha
un piano studi proprio (non è una materia curricolare).

Aggiunta un'area "Sostegno" dedicata: le classi mostrate sono TUTTE
quelle attive dell'anno (non filtrate dal piano studi — sta a chi
assegna scegliere dove mettere ore, sapendo quali classi hanno alunni
certificati, dato non tracciato in questa app), e il tetto ore per
classe è il monte ore settimanale COMPLESSIVO della classe (tutte le
materie, non solo "questa CC" — richiesta esplicita di Roberto: un
docente di sostegno non può coprire più ore di quante la classe ne
abbia in orario).
"""
from models import db
from models.piano_studi import PianoStudi, ClasseSezione
from models.classe_concorso import ClasseConcorso
from models.materia import Dipartimento, Materia

ANNO = '2026-2027'


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()


def _crea_cc_sostegno(codice='ADSS'):
    cc = ClasseConcorso(codice=codice, nome='Sostegno', tipo_posto='sostegno')
    db.session.add(cc)
    db.session.commit()
    return cc


def _crea_sezione(anno_corso, indirizzo, sezione='A'):
    cs = ClasseSezione(anno_scol=ANNO, anno_corso=anno_corso, indirizzo=indirizzo,
                        sezione=sezione, attiva=True)
    db.session.add(cs)
    db.session.commit()
    return cs


def test_classi_sostegno_sono_tutte_le_classi_attive_non_dal_piano_studi(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _classi_per_cc
        cc = _crea_cc_sostegno()
        _crea_sezione(1, 'LSC')
        _crea_sezione(3, 'LSC', sezione='B')
        # Nessuna riga di PianoStudi per ADSS — eppure le classi devono
        # comparire comunque, perché per il sostegno l'elenco non viene
        # più dal piano studi.
        classi = _classi_per_cc(ANNO, cc.id)
        assert set(classi) == {'1A LSC', '3B LSC'}


def test_tetto_ore_sostegno_e_il_monte_ore_totale_della_classe(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _build_area
        cc_sos = _crea_cc_sostegno()
        cc_mat = ClasseConcorso(codice='A-27', nome='Matematica', tipo_posto='cattedra')
        db.session.add(cc_mat)
        db.session.commit()

        _crea_sezione(1, 'LSC')
        # Monte ore 1A LSC = 27h (esempio reale di Roberto): due materie
        # curricolari da 27h totali, nessuna in compresenza.
        db.session.add(PianoStudi(anno_scol=ANNO, id_classe_concorso=cc_mat.id,
                                   anno_corso=1, indirizzo='LSC',
                                   ore_settimanali=27, compresenza=False))
        db.session.commit()

        blocks = _build_area(ANNO, {'nome': 'Sostegno', 'cc': ['ADSS']})
        assert len(blocks) == 1
        assert blocks[0]['piano']['1A LSC'] == 27


def test_ore_compresenza_escluse_dal_monte_ore(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _monte_ore_classe
        cc_mat = ClasseConcorso(codice='A-27', nome='Matematica', tipo_posto='cattedra')
        db.session.add(cc_mat)
        db.session.commit()
        db.session.add_all([
            PianoStudi(anno_scol=ANNO, id_classe_concorso=cc_mat.id,
                       anno_corso=1, indirizzo='LSC',
                       ore_settimanali=27, compresenza=False),
            PianoStudi(anno_scol=ANNO, id_classe_concorso=cc_mat.id,
                       anno_corso=1, indirizzo='LSC',
                       ore_settimanali=2, compresenza=True),
        ])
        db.session.commit()

        assert _monte_ore_classe(ANNO, 1, 'LSC') == 27


def test_materia_sostegno_risolta_dalla_cc_non_dal_piano_studi(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _resolve_id_materia
        cc = _crea_cc_sostegno()
        dip = Dipartimento(nome='Sostegno', sigla='SOS')
        db.session.add(dip)
        db.session.commit()
        mat = Materia(nome='Sostegno', sigla='SOS-M', id_dipartimento=dip.id,
                       id_classe_concorso=cc.id)
        db.session.add(mat)
        db.session.commit()

        id_mat = _resolve_id_materia(ANNO, cc.id, '1A LSC')
        assert id_mat == mat.id


def test_adss_e_nellelenco_aree():
    from routes.assegnazioni import AREE
    codici = set()
    for area in AREE:
        codici.update(area['cc'])
    assert 'ADSS' in codici
