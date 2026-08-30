"""
routes/export_xlsx.py::_p9_scrivi_blocco_cc() — stesso bug già corretto
in routes/assegnazioni.py::_classi_per_cc() (addendum 78/79), ma
duplicato qui: questo export costruisce la griglia "materia -> ore per
classe" con una sua query indipendente su PianoStudi, ignorando
PianoStudiOverride. Stesso scenario reale: 1° LLI, "Lettere italiane"
generale su AS12, override sezione B verso A-11.
"""
from openpyxl import Workbook
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
    db.session.add(ClasseSezione(anno_scol=ANNO, anno_corso=anno_corso,
                                  indirizzo=indirizzo, sezione=sezione, attiva=True))
    db.session.commit()


def _scenario():
    as12 = _crea_cc('AS12', 'Discipline Letterarie sec. II grado')
    a11  = _crea_cc('A-11', 'Discipline Letterarie e Latino')
    _crea_sezione(1, 'LLI', 'A')
    _crea_sezione(1, 'LLI', 'B')

    ps = PianoStudi(anno_scol=ANNO, id_classe_concorso=as12.id,
                     anno_corso=1, indirizzo='LLI', nome_materia_locale='Lettere italiane',
                     ore_settimanali=4, id_cc_default=a11.id, atipica=True, compresenza=False)
    db.session.add(ps)
    db.session.commit()
    db.session.add(PianoStudiOverride(id_piano_studi=ps.id, sezione='B',
                                       id_cc_override=a11.id, atipica=False, note='per Sportelli'))
    db.session.commit()
    return as12, a11


def _leggi_blocco(app, cc, label_col):
    from routes.export_xlsx import _p9_scrivi_blocco_cc
    ws = Workbook().active
    label_color = {lbl: 'FFFFFFFF' for lbl in label_col}
    _p9_scrivi_blocco_cc(ws, 3, ANNO, cc, label_col, label_color,
                         ultima_classe_col=max(label_col.values()),
                         col_pot=max(label_col.values()) + 1,
                         col_richiesta=None, col_titolari=None)
    # riga 4: "Lettere italiane" (unica materia per queste due CC nello scenario)
    return {lbl: ws.cell(4, col).value for lbl, col in label_col.items()}


def test_as12_non_mostra_ore_per_la_sezione_spostata_via(app, db_session):
    as12, a11 = _scenario()
    label_col = {'1A LLI': 2, '1B LLI': 3}
    valori = _leggi_blocco(app, as12, label_col)
    assert valori['1A LLI'] == 4
    assert valori['1B LLI'] == '-'


def test_a11_mostra_ore_per_la_sezione_ricevuta_dalloverride(app, db_session):
    as12, a11 = _scenario()
    label_col = {'1A LLI': 2, '1B LLI': 3}
    valori = _leggi_blocco(app, a11, label_col)
    assert valori['1A LLI'] == '-'
    assert valori['1B LLI'] == 4
