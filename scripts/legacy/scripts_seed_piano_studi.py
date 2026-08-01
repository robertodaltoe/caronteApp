"""
Seed piano studi 2026/27 dal file Monteore OD.xlsx.

Popola:
  1. ClasseSezione — tutte le classi attive (quelle con almeno un valore numerico)
  2. PianoStudi    — ore per CC/materia/indirizzo/anno_corso
  3. CalcoloOrganico — calcolo COI/COE/residue per ogni CC

Le classi prime AFM e CAT NON vengono popolate nel piano studi perché
il quadro orario 2026/27 non è ancora definito — da inserire a mano
tramite l'interfaccia.

I laboratori ITP vengono trattati come classi di concorso a sé stanti,
con riferimento alla CC madre solo per l'adiacenza nell'export.
"""
import sys, os
# Percorso della cartella radice del progetto (questo script vive in
# scripts/legacy/, due livelli sotto la radice dove sta app.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from models import db
from models.piano_studi import ClasseSezione, PianoStudi, CalcoloOrganico
from models.classe_concorso import ClasseConcorso

app = create_app()
ANNO = '2026-2027'

# ── MAPPA colonna → (indirizzo, anno_corso, sezione) ─────────────────
# Derivata esattamente dal file Excel (riga 2)
COL_TO_CLASSE = {
    2:  ('AFM', 1, 'A'), 3:  ('AFM', 1, 'B'), 4:  ('AFM', 2, 'A'), 5:  ('AFM', 2, 'B'),
    6:  ('RIM', 3, 'A'), 7:  ('RIM', 3, 'B'), 8:  ('RIM', 4, 'A'), 9:  ('RIM', 4, 'B'),
    10: ('RIM', 5, 'A'), 11: ('RIM', 5, 'B'),
    12: ('CAT', 1, 'A'), 13: ('CAT', 1, 'B'), 14: ('CAT', 2, 'A'), 15: ('CAT', 2, 'B'),
    16: ('CAT', 3, 'A'), 17: ('CAT', 3, 'B'), 18: ('CAT', 4, 'A'), 19: ('CAT', 4, 'B'),
    20: ('CAT', 5, 'A'), 21: ('CAT', 5, 'B'),
    22: ('LSU', 1, 'A'), 23: ('LSU', 1, 'B'), 24: ('LSU', 2, 'A'), 25: ('LSU', 2, 'B'),
    26: ('LSU', 3, 'A'), 27: ('LSU', 3, 'B'), 28: ('LSU', 4, 'A'), 29: ('LSU', 4, 'B'),
    30: ('LSU', 5, 'A'), 31: ('LSU', 5, 'B'),
    32: ('LSC', 1, 'A'), 33: ('LSC', 1, 'B'), 34: ('LSC', 2, 'A'), 35: ('LSC', 2, 'B'),
    36: ('LSC', 3, 'A'), 37: ('LSC', 3, 'B'), 38: ('LSC', 4, 'A'), 39: ('LSC', 4, 'B'),
    40: ('LSC', 5, 'A'), 41: ('LSC', 5, 'B'),
    42: ('LLI', 1, 'A'), 43: ('LLI', 1, 'B'), 44: ('LLI', 2, 'A'), 45: ('LLI', 2, 'B'),
    46: ('LLI', 3, 'A'), 47: ('LLI', 3, 'B'), 48: ('LLI', 4, 'A'), 49: ('LLI', 4, 'B'),
    50: ('LLI', 5, 'A'), 51: ('LLI', 5, 'B'),
    52: ('LSP', 1, 'A'), 53: ('LSP', 2, 'A'), 54: ('LSP', 3, 'A'),
    55: ('LSP', 4, 'A'), 56: ('LSP', 5, 'A'),
}

# ── MAPPA codice CC nel file → codice nel database ────────────────────
CC_CODICE_MAP = {
    'A011': 'A-11', 'AS12': 'A-12', 'AS01': 'A-01',
    'A018': 'A-18', 'A019': 'A-19', 'A020': 'A-20',
    'A026': 'A-26', 'A027': 'A-27', 'A034': 'A-34',
    'A037': 'A-37', 'A041': 'A-41', 'A045': 'A-45',
    'A046': 'A-46', 'A047': 'A-47', 'AS48': 'A-48',
    'A050': 'A-50', 'A021': 'A-21', 'A051': 'A-51',
    'AS2B': 'A-22-ING', 'AS2D': 'A-22-TED', 'AS2C': 'A-22-SPA',
    'B02 CONV ING':  'B-02-ING', 'B02 CONV TED': 'B-02-TED',
    'B02 CONV SPA':  'B-02-SPA',
    'Lab.fisica B003':     'B-03',
    'Lab.Scienze B012':    'B-12',
    'Labortorio B014':     'B-14',
    'Lab. Informatica B016': 'B-16',
    'Laboratorio B017':    'B-17',
    'IRC': 'IRC',
}

# Mappa laboratorio → CC madre (per adiacenza nell'export)
LAB_MADRE = {
    'B-03': 'A-20',
    'B-12': 'A-34',
    'B-14': 'A-37',
    'B-16': 'A-41',
    'B-17': 'A-37',
}

# ── DATI DEL PIANO STUDI (estratti dal file, classi prime AFM/CAT escluse)
# Formato: (codice_cc_file, nome_materia_locale, {col: ore, ...})
# Le colonne corrispondono a COL_TO_CLASSE sopra
PIANO = [
    # A011
    ('A011', 'lettere italiane',
     {22:4,23:4,24:4,26:4,28:4,30:4,32:4,34:4,36:4,37:4,38:4,40:4,
      42:4,43:4,44:4,45:4,46:4,47:4,48:4,50:4,55:4,56:4}),
    ('A011', 'lingua e cult.latina',
     {22:3,23:3,24:3,26:2,28:2,30:2,32:3,34:3,36:3,37:3,38:3,40:3,
      42:2,43:2,44:2,45:2}),
    ('A011', 'storia e geografia',
     {22:3,23:3,24:3,32:3,34:3,42:3,43:3,44:3,45:3}),
    # AS12
    ('AS12', 'lingua e lett.italiana',
     {2:4,3:4,4:4,6:4,7:4,8:4,10:4,
      12:4,13:4,14:4,16:4,18:4,20:4,
      52:4,53:4,54:4}),
    ('AS12', 'storia, cittadinanza e costituzione',
     {2:2,3:2,4:2,6:2,7:2,8:2,10:2,
      12:2,13:2,14:2,16:2,18:2,20:2,
      52:3,53:3}),
    # AS01
    ('AS01', "Disegno e storia dell'arte",
     {32:2,34:2,36:2,37:2,38:2,40:2}),
    ('AS01', "Storia dell'arte",
     {26:2,28:2,30:2,46:2,47:2,48:2,50:2}),
    # A018
    ('A018', 'Scienze umane',
     {22:4,23:4,24:4,26:5,28:5,30:5}),
    # A019
    ('A019', 'Filosofia',
     {26:3,28:3,30:3,36:3,37:3,38:3,40:3,46:2,47:2,48:2,50:2,54:2,55:2,56:2}),
    ('A019', 'Storia',
     {26:2,28:2,30:2,36:2,37:2,38:2,40:2,46:2,47:2,48:2,50:2,54:2,55:2,56:2}),
    # A020
    ('A020', 'Fisica',
     {2:4,3:4,12:4,13:4,14:3}),
    # A020 laboratorio B003
    ('Lab.fisica B003', 'Lab.fisica',
     {12:1,13:1,14:1}),
    # A026
    ('A026', 'Matematica',
     {12:4,13:4,14:4,16:3,18:3,20:3,
      22:3,23:3,24:3,32:5,34:5,
      42:3,43:3,44:3,45:3,
      52:5,53:5,54:4,55:4,56:4}),
    ('A026', 'Complementi di matematica',
     {16:1,18:1}),
    # A027
    ('A027', 'Matematica',
     {26:2,28:2,30:2,36:4,37:4,38:4,40:4,46:2,47:2,48:2,50:2}),
    ('A027', 'Fisica',
     {26:2,28:2,30:2,32:2,34:2,36:3,37:3,38:3,40:3,46:2,47:2,48:2,50:2,
      52:2,53:2,54:3,55:3,56:3}),
    # A034
    ('A034', 'Scienze integr.chimica',
     {4:2,12:2,13:2,14:3}),
    ('Lab.Scienze B012', 'Lab.Scienze B012',
     {12:1,13:1,14:1}),
    # A037
    ('A037', 'tecnol.e tecniche rappr.grafica',
     {14:3}),
    ('A037', 'Scienze e tecnol.applicate',
     {14:3}),
    ('A037', 'Progettaz.costruz.impianti',
     {16:7,18:6,20:7}),
    ('A037', 'Gestione cantiere',
     {16:2,18:2,20:2}),
    ('A037', 'Fondamenti di progettazione edilizia e ambiente',
     {12:4,13:4}),
    ('A037', 'Topografia',
     {16:4,18:4,20:4}),
    ('Labortorio B014', 'Laboratorio B014',
     {16:8,18:9,20:10}),
    ('Laboratorio B017', 'Laboratorio B017',
     {12:1,13:1,14:1}),
    # A041
    ('A041', 'Scienze e tecnol.informatiche',
     {2:2,3:2,4:2,6:2,7:2,8:2,12:3,13:3}),
    ('Lab. Informatica B016', 'Lab. Informatica B016',
     {12:2,13:2}),
    # A045
    ('A045', 'Economia aziendale',
     {2:2,3:2,4:2}),
    ('A045', 'Economia aziendale e geopolitica',
     {6:5,7:5,8:5,10:6}),
    # A046
    ('A046', 'Diritto ed economia',
     {2:2,3:2,4:2,6:2,7:2,8:2,10:2,
      12:2,13:2,14:2,
      22:2,23:2,24:2}),
    ('A046', 'Relazioni internazionali',
     {6:2,7:2,8:2,10:3}),
    ('A046', 'Diritto ed economia dello sport',
     {54:3,55:3,56:3}),
    # A047
    ('A047', 'Matematica applicata',
     {2:4,3:4,4:4,6:3,7:3,8:3,10:3}),
    # AS48
    ('AS48', 'Scienze motorie e sportive',
     {2:2,3:2,4:2,6:2,7:2,8:2,10:2,
      12:2,13:2,14:2,16:2,18:2,20:2,
      22:2,23:2,24:2,26:2,28:2,30:2,
      32:2,34:2,36:2,37:2,38:2,40:2,
      42:2,43:2,44:2,45:2,46:2,47:2,48:2,50:2,
      52:3,53:3,54:3,55:3,56:3}),
    ('AS48', 'discipline sportive',
     {52:3,53:3,54:2,55:2,56:2}),
    # A050
    ('A050', 'Scienze naturali',
     {4:2,14:2,22:2,23:2,24:2,26:2,28:2,30:2,
      32:2,34:2,36:3,37:3,38:3,40:3,
      42:2,43:2,44:2,45:2,46:2,47:2,48:2,50:2,
      52:3,53:3,54:3,55:3,56:3}),
    ('A050', 'Geografia',
     {4:3}),
    # A021
    ('A021', 'Geografia',
     {2:3,3:3,12:1,13:1}),
    # A051
    ('A051', 'Geopedologia',
     {16:3,18:4,20:4}),
    # IRC
    ('IRC', 'religione',
     {2:1,3:1,4:1,6:1,7:1,8:1,10:1,
      12:1,13:1,14:1,16:1,18:1,20:1,
      22:1,23:1,24:1,26:1,28:1,30:1,
      32:1,34:1,36:1,37:1,38:1,40:1,
      42:1,43:1,44:1,45:1,46:1,47:1,48:1,50:1,
      52:1,53:1,54:1,55:1,56:1}),
]


def calcola_tipo(ore_totali):
    """Regola generale: COI ≥18, COE 8-17, residue 1-7. Zero = nessuno."""
    if ore_totali == 0:
        return None, 0, 0
    n_coi = ore_totali // 18
    resto = ore_totali % 18
    if resto == 0:
        return 'COI', n_coi, 0
    elif resto >= 8:
        return 'COE', n_coi, resto
    else:
        return 'residue', n_coi, resto


with app.app_context():
    # ── 1. CLASSI SEZIONI ATTIVE ─────────────────────────────────────
    # Determino quali colonne hanno almeno un valore numerico nel piano
    colonne_attive = set()
    for _, _, col_ore in PIANO:
        colonne_attive.update(col_ore.keys())

    n_sezioni = 0
    for col in sorted(colonne_attive):
        if col not in COL_TO_CLASSE:
            continue
        ind, anno, sez = COL_TO_CLASSE[col]
        esiste = ClasseSezione.query.filter_by(
            anno_scol=ANNO, indirizzo=ind, anno_corso=anno, sezione=sez).first()
        if not esiste:
            db.session.add(ClasseSezione(
                anno_scol=ANNO, indirizzo=ind, anno_corso=anno, sezione=sez, attiva=True))
            n_sezioni += 1
    db.session.commit()
    print(f'ClasseSezione: {n_sezioni} inserite')

    # ── 2. PIANO STUDI ───────────────────────────────────────────────
    cc_cache = {}
    def get_cc(codice_file):
        codice_db = CC_CODICE_MAP.get(codice_file)
        if not codice_db:
            return None
        if codice_db not in cc_cache:
            cc_cache[codice_db] = ClasseConcorso.query.filter_by(codice=codice_db).first()
        return cc_cache[codice_db]

    n_piano = 0
    for codice_cc, nome_mat, col_ore in PIANO:
        cc = get_cc(codice_cc)
        if not cc:
            print(f'  ATTENZIONE: CC non trovata per {codice_cc}')
            continue
        # CC madre per laboratori
        cc_madre = None
        if cc.codice in LAB_MADRE:
            cc_madre = cc_cache.get(LAB_MADRE[cc.codice]) or \
                       ClasseConcorso.query.filter_by(codice=LAB_MADRE[cc.codice]).first()
            cc_cache[LAB_MADRE[cc.codice]] = cc_madre

        for col, ore in col_ore.items():
            if col not in COL_TO_CLASSE:
                continue
            ind, anno, _ = COL_TO_CLASSE[col]
            esiste = PianoStudi.query.filter_by(
                anno_scol=ANNO, indirizzo=ind, anno_corso=anno,
                id_classe_concorso=cc.id, nome_materia_locale=nome_mat).first()
            if not esiste:
                db.session.add(PianoStudi(
                    anno_scol=ANNO, indirizzo=ind, anno_corso=anno,
                    id_classe_concorso=cc.id,
                    nome_materia_locale=nome_mat,
                    ore_settimanali=ore,
                    id_cc_madre=cc_madre.id if cc_madre else None))
                n_piano += 1
    db.session.commit()
    print(f'PianoStudi: {n_piano} righe inserite')

    # ── 3. CALCOLO ORGANICO ──────────────────────────────────────────
    # Per ogni CC, sommo le ore su tutte le classi attive
    from sqlalchemy import func
    cc_ids = [r.id for r in ClasseConcorso.query.all()]
    n_calc = 0
    for cc_id in cc_ids:
        righe = PianoStudi.query.filter_by(anno_scol=ANNO, id_classe_concorso=cc_id).all()
        if not righe:
            continue
        # Sommo solo le righe per cui esiste una ClasseSezione attiva
        totale = 0
        for p in righe:
            cs = ClasseSezione.query.filter_by(
                anno_scol=ANNO, indirizzo=p.indirizzo,
                anno_corso=p.anno_corso, attiva=True).all()
            totale += p.ore_settimanali * len(cs)

        tipo, n_coi, resto = calcola_tipo(totale)
        esiste = CalcoloOrganico.query.filter_by(anno_scol=ANNO, id_classe_concorso=cc_id).first()
        if esiste:
            esiste.ore_totali_calcolate = totale
            esiste.n_coi_calcolato = n_coi
            esiste.ore_resto_calcolato = resto
            esiste.tipo_calcolato = tipo
        else:
            db.session.add(CalcoloOrganico(
                anno_scol=ANNO, id_classe_concorso=cc_id,
                ore_totali_calcolate=totale, n_coi_calcolato=n_coi,
                ore_resto_calcolato=resto, tipo_calcolato=tipo))
            n_calc += 1
    db.session.commit()
    print(f'CalcoloOrganico: {n_calc} righe inserite')

    # ── VERIFICA FINALE ──────────────────────────────────────────────
    print()
    print('=== CALCOLO ORGANICO 2026/27 ===')
    righe = (CalcoloOrganico.query
             .join(ClasseConcorso)
             .filter(CalcoloOrganico.anno_scol == ANNO)
             .filter(CalcoloOrganico.ore_totali_calcolate > 0)
             .order_by(ClasseConcorso.codice).all())
    for r in righe:
        print(f'  {r.classe_concorso.codice:12} {r.ore_totali_calcolate:3}h '
              f'→ {r.n_coi_calcolato} COI + {r.ore_resto_calcolato} ore ({r.tipo_calcolato})')
