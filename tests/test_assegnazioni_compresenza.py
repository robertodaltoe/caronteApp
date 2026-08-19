"""
Test di regressione (Sessione 65): Roberto segnala che una classe con
SOLO ore di compresenza per una classe di concorso (es. B-02-ING in
5ª LLI) sparisce dalla pagina Assegnazioni, mentre altre classi della
stessa CC hanno ore proprie (es. B-02-ING in 1ª-4ª LLI, non
compresenza).

Causa: routes/assegnazioni.py::_classi_per_cc() derivava l'elenco
classi da _righe_piano() senza anno_corso/indirizzo — quella funzione
sceglie compresenza SOLO se l'intera CC non ha alcuna riga propria in
nessuna classe, un fallback pensato per le CC che esistono solo come
compresenza (B-02, B-03, B-12...), non per una singola classe dentro
una CC che ha ore proprie altrove.
"""
from models import db
from models.piano_studi import PianoStudi, ClasseSezione
from models.classe_concorso import ClasseConcorso

ANNO = '2026-2027'


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()


def _crea_cc(codice='B-02-ING', nome='Conversazione Inglese'):
    cc = ClasseConcorso(codice=codice, nome=nome, tipo_posto='itp')
    db.session.add(cc)
    db.session.commit()
    return cc


def _crea_sezione(anno_corso, indirizzo, sezione='A'):
    cs = ClasseSezione(anno_scol=ANNO, anno_corso=anno_corso, indirizzo=indirizzo,
                        sezione=sezione, attiva=True)
    db.session.add(cs)
    db.session.commit()
    return cs


def test_classe_solo_compresenza_visibile_anche_se_altre_classi_hanno_ore_proprie(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _classi_per_cc
        cc = _crea_cc()
        for ac in (1, 2, 3, 4):
            _crea_sezione(ac, 'LLI')
            db.session.add(PianoStudi(anno_scol=ANNO, id_classe_concorso=cc.id,
                                       anno_corso=ac, indirizzo='LLI',
                                       ore_settimanali=1, compresenza=False))
        _crea_sezione(5, 'LLI')
        db.session.add(PianoStudi(anno_scol=ANNO, id_classe_concorso=cc.id,
                                   anno_corso=5, indirizzo='LLI',
                                   ore_settimanali=1, compresenza=True))
        db.session.commit()

        classi = _classi_per_cc(ANNO, cc.id)
        assert '5A LLI' in classi
        assert set(classi) == {'1A LLI', '2A LLI', '3A LLI', '4A LLI', '5A LLI'}


def test_ore_classe_compresenza_restano_corrette(app, db_session):
    """Il fix riguarda solo l'elenco classi — il calcolo delle ore per
    la singola classe (già corretto) non deve cambiare."""
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _righe_piano
        cc = _crea_cc()
        _crea_sezione(5, 'LLI')
        db.session.add(PianoStudi(anno_scol=ANNO, id_classe_concorso=cc.id,
                                   anno_corso=5, indirizzo='LLI',
                                   ore_settimanali=1, compresenza=True))
        db.session.commit()

        righe = _righe_piano(ANNO, cc.id, 5, 'LLI')
        assert sum(r.ore_settimanali for r in righe) == 1


def test_cc_solo_compresenza_continua_a_funzionare(app, db_session):
    """Non regredisce il caso originale (Task 44): una CC che esiste
    SOLO come compresenza in ogni classe deve restare visibile."""
    _crea_tabelle(app)
    with app.app_context():
        from routes.assegnazioni import _classi_per_cc
        cc = _crea_cc(codice='B-03', nome='Laboratori di Fisica')
        _crea_sezione(1, 'LSC')
        db.session.add(PianoStudi(anno_scol=ANNO, id_classe_concorso=cc.id,
                                   anno_corso=1, indirizzo='LSC',
                                   ore_settimanali=1, compresenza=True))
        db.session.commit()

        classi = _classi_per_cc(ANNO, cc.id)
        assert classi == ['1A LSC']
