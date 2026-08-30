"""
Test di regressione: Roberto segnala che un override per-sezione
(PianoStudiOverride) non viene rispettato in Assegnazioni. Caso reale:
1° LLI, "Lettere italiane" insegnato da AS12 in generale, con un
override per la sezione B verso A-11 (per Sportelli).

Prima del fix, routes/assegnazioni.py::_classi_per_cc() e la
costruzione di 'piano' in _build_area() ignoravano del tutto
PianoStudiOverride: AS12 continuava a mostrare la colonna "1B LLI"
(già spostata via) e A-11 non la riceveva mai — sia le colonne che le
ore "previste" della riga di controllo in fondo alla tabella erano
sbagliate per entrambe le classi di concorso coinvolte.
"""
from models import db
from models.piano_studi import PianoStudi, PianoStudiOverride, ClasseSezione
from models.classe_concorso import ClasseConcorso

ANNO = '2026-2027'


def _crea_cc(codice, nome):
    cc = ClasseConcorso(codice=codice, nome=nome, tipo_posto='normale')
    db.session.add(cc)
    db.session.commit()
    return cc


def _crea_sezione(anno_corso, indirizzo, sezione):
    cs = ClasseSezione(anno_scol=ANNO, anno_corso=anno_corso, indirizzo=indirizzo,
                        sezione=sezione, attiva=True)
    db.session.add(cs)
    db.session.commit()
    return cs


def _scenario():
    """1A e 1B LLI attive. Lettere italiane in AS12 (ore=4), override
    sezione B -> A-11 con ore diverse per verificare che vengano lette
    dalla riga giusta."""
    as12 = _crea_cc('AS12', 'Discipline Letterarie sec. II grado')
    a11  = _crea_cc('A-11', 'Discipline Letterarie e Latino')
    _crea_sezione(1, 'LLI', 'A')
    _crea_sezione(1, 'LLI', 'B')

    ps = PianoStudi(anno_scol=ANNO, id_classe_concorso=as12.id,
                     anno_corso=1, indirizzo='LLI',
                     ore_settimanali=4, id_cc_default=a11.id,
                     atipica=True, compresenza=False)
    db.session.add(ps)
    db.session.commit()

    db.session.add(PianoStudiOverride(
        id_piano_studi=ps.id, sezione='B', id_cc_override=a11.id,
        atipica=False, note='per Sportelli'))
    db.session.commit()
    return as12, a11, ps


def test_as12_perde_la_sezione_spostata_via_da_override(app, db_session):
    from routes.assegnazioni import _classi_per_cc
    as12, a11, ps = _scenario()

    classi_as12 = _classi_per_cc(ANNO, as12.id)
    assert classi_as12 == ['1A LLI']


def test_a11_riceve_la_sezione_spostata_dallo_override(app, db_session):
    from routes.assegnazioni import _classi_per_cc
    as12, a11, ps = _scenario()

    classi_a11 = _classi_per_cc(ANNO, a11.id)
    assert classi_a11 == ['1B LLI']


def test_ore_previste_per_sezione_seguono_loverride(app, db_session):
    """_righe_piano_sezione deve risolvere le ore dalla riga giusta per
    ciascuna sezione, non sempre dalla riga generale (AS12)."""
    from routes.assegnazioni import _righe_piano_sezione
    as12, a11, ps = _scenario()

    righe_a = _righe_piano_sezione(ANNO, as12.id, 1, 'LLI', 'A')
    assert [r.ore_settimanali for r in righe_a] == [4]

    righe_b_su_as12 = _righe_piano_sezione(ANNO, as12.id, 1, 'LLI', 'B')
    assert righe_b_su_as12 == []

    righe_b_su_a11 = _righe_piano_sezione(ANNO, a11.id, 1, 'LLI', 'B')
    assert [r.ore_settimanali for r in righe_b_su_a11] == [4]


def test_build_area_mostra_piano_coerente_con_override(app, db_session):
    """Verifica end-to-end sul dict prodotto da _build_area(), la
    struttura che alimenta davvero la tabella e la riga di controllo in
    fondo in templates/assegnazioni/index.html."""
    from routes.assegnazioni import _build_area
    as12, a11, ps = _scenario()

    area = {'nome': 'Test', 'cc': ['AS12', 'A-11']}
    blocks = _build_area(ANNO, area)
    by_cod = {b['cc'].codice: b for b in blocks}

    assert by_cod['AS12']['classi'] == ['1A LLI']
    assert by_cod['AS12']['piano'] == {'1A LLI': 4}

    assert by_cod['A-11']['classi'] == ['1B LLI']
    assert by_cod['A-11']['piano'] == {'1B LLI': 4}
