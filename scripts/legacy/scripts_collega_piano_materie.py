"""
Collega PianoStudi.id_materia alla tabella Materia, usando il
nome_materia_locale come chiave di abbinamento.

Logica:
  1. Mappa esplicita nome_locale → sigla_materia (per i casi ambigui
     o con nomi divergenti).
  2. Corrispondenza automatica per nome (case-insensitive) sui rimasti.
  3. Crea le materie mancanti e le collega alla CC giusta.
  4. Aggiorna PianoStudi.id_materia per tutte le righe.
"""
import sys, os
# Percorso della cartella radice del progetto (questo script vive in
# scripts/legacy/, due livelli sotto la radice dove sta app.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from models import db
from models.materia import Materia
from models.piano_studi import PianoStudi
from models.classe_concorso import ClasseConcorso

app = create_app()
ANNO = '2026-2027'

# ── MAPPA ESPLICITA nome_locale → sigla ────────────────────────────────
# Copre i casi in cui il nome nel piano studi diverge dal nome ufficiale
# in tabella Materia, o dove c'è ambiguità.
MAPPA_ESPLICITA = {
    'lettere italiane':                       'ITA',
    'lingua e lett.italiana':                 'ITA',
    'lingua e cult.latina':                   'LAT',
    'storia e goografia':                     'STO-GEO',   # typo nel file
    'storia e geografia':                     'STO-GEO',
    'storia, cittadinanza e costituzione':    'STO-CIT',   # da creare
    'discipline sportive':                    'DISC-SP',
    'Scienze e tecnol.informatiche':          'TEC-INFO',
    'Scienze e tecnol.applicate':             'SCI-APP',   # da creare
    'Scienze integr.chimica':                 'CHI',
    'Geopedologia':                           'GEO-EST',
    'Progettaz.costruz.impianti':             'PCI',
    'Gestione cantiere':                      'CANT-SIC',
    'tecnol.e tecniche rappr.grafica':        'TTRG',
    'Fondamenti di progettazione edilizia e ambiente': 'FPED',  # da creare
    'Matematica applicata':                   'MAT-APP',   # da creare
    'Complementi di matematica':              'MAT-COMP',  # da creare
    'Relazioni internazionali':               'REL-INT',
    'Economia aziendale e geopolitica':       'EC-AZ-GEO',
    'Economia aziendale':                     'EC-AZ',
    'Diritto ed economia':                    'DIR-ECO',
    'Diritto ed economia dello sport':        'DIR-SPORT',
    'Scienze e tecnol.applicate':             'SCI-APP',
    'Lab.fisica':                             'LAB-FIS',   # da creare
    'Lab.Scienze B012':                       'LAB-CHI',   # da creare
    'Lab. Informatica B016':                  'LAB-INFO',  # da creare
    'Labortorio B014':                        'LAB-COST',  # da creare
    'Laboratorio B017':                       'LAB-MEC',   # da creare
    'religione':                              'REL',
    'Scienze umane':                          'SC-UM',
    'Scienze naturali':                       'SCI',
    'Storia dell\'arte':                      'ST-ARTE',
    'Disegno e storia dell\'arte':            'DIS-ARTE',
    'Scienze motorie e sportive':             'SC-MOT',
}

# ── MATERIE DA CREARE (sigla → nome ufficiale, collegata alla CC giusta)
# Formato: sigla → (nome_ufficiale, codice_cc)
# Formato: sigla → (nome_ufficiale, codice_cc, id_dipartimento)
NUOVE_MATERIE = {
    'STO-CIT':  ('Storia, Cittadinanza e Costituzione',      'A-12', 1),  # Linguistico-Letterario
    'SCI-APP':  ('Scienze e Tecnologie Applicate',           'A-37', 6),  # CAT
    'FPED':     ('Fondamenti di Progettazione Edilizia e Ambiente', 'A-37', 6),
    'MAT-APP':  ('Matematica Applicata',                     'A-47', 5),  # AFM-RIM
    'MAT-COMP': ('Complementi di Matematica',                'A-26', 3),  # Mat-Sci
    'LAB-FIS':  ('Laboratorio di Fisica (B-03)',             'B-03', 3),
    'LAB-CHI':  ('Laboratorio Scienze Chimiche (B-12)',      'B-12', 3),
    'LAB-INFO': ('Laboratorio Informatica (B-16)',           'B-16', 5),
    'LAB-COST': ('Laboratorio Costruzioni (B-14)',           'B-14', 6),
    'LAB-MEC':  ('Laboratorio Meccanica (B-17)',             'B-17', 6),
}

with app.app_context():
    # ── STEP 1: Crea le materie mancanti ─────────────────────────────
    cc_cache = {}
    def get_cc(codice):
        if codice not in cc_cache:
            cc_cache[codice] = ClasseConcorso.query.filter_by(codice=codice).first()
        return cc_cache[codice]

    n_create = 0
    for sigla, (nome, codice_cc, id_dip) in NUOVE_MATERIE.items():
        if not Materia.query.filter_by(sigla=sigla).first():
            cc = get_cc(codice_cc)
            m = Materia(sigla=sigla, nome=nome,
                       id_dipartimento=id_dip,
                       id_classe_concorso=cc.id if cc else None,
                       attiva=True)
            db.session.add(m)
            n_create += 1
            print(f'  Creata: {sigla} — {nome}')
    db.session.commit()
    print(f'Materie create: {n_create}')

    # ── STEP 2: Costruisce la mappa sigla → Materia ──────────────────
    materia_cache = {m.sigla: m for m in Materia.query.all()}

    # ── STEP 3: Collega PianoStudi.id_materia ────────────────────────
    nomi_locali = db.session.execute(
        db.select(PianoStudi.nome_materia_locale).distinct()
    ).scalars().all()

    n_collegati = 0
    n_non_trovati = []

    for nome_loc in nomi_locali:
        if not nome_loc:
            continue

        # Cerca nella mappa esplicita prima
        sigla = MAPPA_ESPLICITA.get(nome_loc)

        # Fallback: confronto case-insensitive sul nome ufficiale
        if not sigla:
            nome_lower = nome_loc.strip().lower()
            for m in materia_cache.values():
                if m.nome.lower() == nome_lower:
                    sigla = m.sigla
                    break

        if not sigla or sigla not in materia_cache:
            n_non_trovati.append(nome_loc)
            continue

        materia = materia_cache[sigla]
        righe = PianoStudi.query.filter_by(
            anno_scol=ANNO, nome_materia_locale=nome_loc).all()
        for r in righe:
            r.id_materia = materia.id
            n_collegati += 1

    db.session.commit()
    print(f'Righe PianoStudi collegate: {n_collegati}')

    if n_non_trovati:
        print(f'NON TROVATI ({len(n_non_trovati)}):')
        for n in n_non_trovati:
            print(f'  "{n}"')

    # ── STEP 4: Verifica finale ───────────────────────────────────────
    tot = PianoStudi.query.filter_by(anno_scol=ANNO).count()
    coll = PianoStudi.query.filter_by(anno_scol=ANNO).filter(
        PianoStudi.id_materia.isnot(None)).count()
    print(f'\nRisultato: {coll}/{tot} righe collegate ({100*coll//tot}%)')
