"""
modules/parser_orario.py
Logica di parsing e importazione orario.
Usata sia da import_orario.py che dalla route /sincronizzazione.

Il software di orario usato dalla scuola esporta due varianti dello
stesso foglio "a griglia" (giorni in colonna, un blocco di righe per
docente):

1. Formato "a tag" (il primo mai visto, foglio chiamato esattamente
   '7_ORARIO DEFINITIVO_teachers_ti'): colonna A marca ogni riga con
   CLASSE/MATERIE/COMPRESENZA, il cognome del docente sta in colonna B
   sulla riga CLASSE.
2. Formato "orizzontale" (visto per la prima volta il 2026-09-11, es.
   "ORARIO SETTIMANA 1B_teachers_ti"): niente colonna A di servizio, il
   cognome sta nella prima colonna prima delle ore, e classe/materia
   sono semplicemente la riga del nome e quella subito sotto -- senza
   etichette. Le compresenze (due docenti sulla stessa ora) si
   riconoscono da una nota testuale "COGNOME1, COGNOME2" al posto della
   classe, con classe/materia comunque presenti su quella stessa riga
   del docente (non serve incrociare le righe dell'altro docente: ogni
   blocco e' autosufficiente, verificato sui casi reali MAY/STRAMBINI e
   MAY/FUMAGALLI in "ORARIO SETTIMANA 1B_teachers_ti").

parse_file() riconosce da solo quale dei due formati ha davanti e
restituisce sempre la stessa struttura, cosi' applica_importazione()
non deve sapere quale dei due e' stato usato.
"""
import re, datetime, os, json
from openpyxl import load_workbook

SHEET_ORARIO  = '7_ORARIO DEFINITIVO_teachers_ti'
SUFFISSO_FOGLIO_ORARIO = '_teachers_ti'
SHEET_DOCENTI = 'Docenti'
GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
LIBERO = {'---', '-x-', '', 'none'}

def clean(v):
    return str(v).strip() if v is not None else ''

def is_libero(v):
    return clean(v).lower() in LIBERO

def is_classe(s):
    return bool(re.match(r'^\d[A-Z]', s.strip()))

def build_col_map(ws):
    giorno_map = {}
    for c in range(1, ws.max_column + 1):
        v = clean(ws.cell(2, c).value).lower()
        if not v:
            continue
        for i, g in enumerate(GIORNI):
            gl = g.lower()
            # Il nome del giorno in riga 2 puo' essere per esteso
            # ("Lunedì", il formato "a tag") o abbreviato ("LUN", il
            # formato "orizzontale" del 2026-09-11): un controllo nei due
            # sensi copre entrambi senza dover sapere quale dei due e'.
            if gl in v or v in gl:
                giorno_map[c] = i
                break
    col_map = {}
    ora_counter = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(3, c).value
        if not isinstance(v, datetime.time):
            continue
        g_num = None
        for gc in sorted(giorno_map.keys(), reverse=True):
            if gc <= c:
                g_num = giorno_map[gc]
                break
        if g_num is None:
            continue
        ora_counter[g_num] = ora_counter.get(g_num, 0) + 1
        col_map[c] = (g_num, ora_counter[g_num])
    return col_map


def _trova_foglio_orario(wb):
    """Il foglio orario si chiama sempre '<qualcosa>_teachers_ti' --
    esattamente '7_ORARIO DEFINITIVO_teachers_ti' nel primo export mai
    visto, ma il software lo rinomina secondo il periodo esportato (es.
    'ORARIO SETTIMANA 1B_teachers_ti'). Si prova prima il nome esatto
    storico, poi si cerca per suffisso invece di richiedere sempre lo
    stesso nome letterale."""
    if SHEET_ORARIO in wb.sheetnames:
        return wb[SHEET_ORARIO]
    for nome in wb.sheetnames:
        if nome.endswith(SUFFISSO_FOGLIO_ORARIO):
            return wb[nome]
    raise KeyError(
        f"Nessun foglio orario trovato (cercato '{SHEET_ORARIO}' o un foglio "
        f"che termina per '{SUFFISSO_FOGLIO_ORARIO}'). Fogli presenti: {wb.sheetnames}"
    )


def _e_formato_a_tag(ws, val):
    """Il formato 'a tag' ha la colonna A che marca ogni riga con
    CLASSE/MATERIE/COMPRESENZA; il formato 'orizzontale' non ha quella
    colonna di servizio. Basta cercare almeno un 'CLASSE' in colonna A."""
    for r in range(4, ws.max_row + 1):
        if clean(val(r, 1)).upper() == 'CLASSE':
            return True
    return False


def _classifica_classe(cs):
    if is_classe(cs):
        return 'lezione'
    if 'POTENZ' in cs.upper():
        return 'potenziamento'
    if 'DISPOS' in cs.upper():
        return 'disposizione'
    return 'altro'


def _sembra_nota_compresenza(testo):
    """Testo tipo 'STRAMBINI, MAY': due cognomi separati da virgola,
    nessuna cifra -- non e' una classe, e' solo l'annotazione di chi
    altro e' presente allo stesso'ora (vedi il modulo docstring)."""
    t = testo.strip()
    if not t or is_classe(t):
        return False
    return ',' in t and not any(ch.isdigit() for ch in t)


def _parse_formato_a_tag(ws, val, col_map):
    slots = []
    docente_corrente = None

    for r in range(4, ws.max_row + 1):
        tipo_riga = clean(val(r, 1)).upper()
        if tipo_riga not in ('CLASSE', 'MATERIE', 'COMPRESENZA'):
            continue

        if tipo_riga == 'CLASSE':
            nd = clean(val(r, 2)).upper()
            if nd:
                docente_corrente = nd
            if not docente_corrente:
                continue
            riga_mat = r + 1
            for c, (giorno, ora) in col_map.items():
                cs = clean(val(r, c))
                ms = clean(val(riga_mat, c))
                if is_libero(cs):
                    continue
                slots.append({'cognome_file': docente_corrente,
                               'giorno': giorno, 'ora': ora,
                               'classe': cs, 'materia': ms,
                               'tipo_ora': _classifica_classe(cs)})

        elif tipo_riga == 'COMPRESENZA' and docente_corrente:
            riga_ref = None
            for rr in range(r - 1, 3, -1):
                if clean(val(rr, 1)).upper() == 'CLASSE':
                    riga_ref = rr
                    break
            for c, (giorno, ora) in col_map.items():
                cs = clean(val(r, c))
                if is_libero(cs) or '|' not in cs:
                    continue
                cognomi = [x.strip().upper() for x in cs.split('|')]
                cr = clean(val(riga_ref, c)) if riga_ref else ''
                mc = clean(val(riga_ref + 1, c)) if riga_ref else ''
                for cog in cognomi:
                    slots.append({'cognome_file': cog, 'giorno': giorno,
                                  'ora': ora, 'classe': cr, 'materia': mc,
                                  'tipo_ora': 'compresenza'})
    return slots


def _parse_formato_orizzontale(ws, val, col_map):
    """Un blocco per docente: la riga del cognome porta gia' la classe
    (o e' vuota/'---'), la riga sotto la materia. Le compresenze
    aggiungono una terza riga (la nota "COGNOME1, COGNOME2" sostituisce
    la classe su quella singola colonna, classe/materia restano sulle
    due righe successive) -- gestito leggendo, per ciascuna colonna, le
    righe non vuote del blocco nell'ordine in cui compaiono invece di
    assumere sempre esattamente due righe fisse."""
    prima_colonna_orario = min(col_map.keys()) if col_map else ws.max_column + 1

    def colonna_nome(r):
        for c in range(1, prima_colonna_orario):
            v = clean(val(r, c))
            if v:
                return v
        return ''

    blocchi = []
    riga_inizio = None
    cognome = None
    for r in range(4, ws.max_row + 2):
        nome = colonna_nome(r) if r <= ws.max_row else None
        if nome:
            if riga_inizio is not None:
                blocchi.append((riga_inizio, r - 1, cognome))
            riga_inizio, cognome = r, nome.upper()
    if riga_inizio is not None:
        blocchi.append((riga_inizio, ws.max_row, cognome))

    slots = []
    for r_inizio, r_fine, cognome in blocchi:
        for c, (giorno, ora) in col_map.items():
            righe = [clean(val(rr, c)) for rr in range(r_inizio, r_fine + 1)]
            righe = [x for x in righe if x]
            if not righe or righe[0] == '---':
                continue
            if _sembra_nota_compresenza(righe[0]):
                # riga[0] e' solo l'annotazione di compresenza: classe e
                # materia sono le righe successive del blocco, non serve
                # andare a leggere il blocco dell'altro docente.
                classe = righe[1] if len(righe) > 1 else ''
                materia = righe[2] if len(righe) > 2 else ''
                if not classe or classe == '---':
                    continue
                slots.append({'cognome_file': cognome, 'giorno': giorno,
                               'ora': ora, 'classe': classe, 'materia': materia,
                               'tipo_ora': 'compresenza'})
                continue
            classe = righe[0]
            materia = righe[1] if len(righe) > 1 else ''
            slots.append({'cognome_file': cognome, 'giorno': giorno,
                           'ora': ora, 'classe': classe, 'materia': materia,
                           'tipo_ora': _classifica_classe(classe)})
    return slots


def parse_file(excel_path):
    wb = load_workbook(excel_path, data_only=True)
    ws_or = _trova_foglio_orario(wb)

    merged = {}
    for merge in ws_or.merged_cells.ranges:
        mr, mc = merge.min_row, merge.min_col
        for r in range(merge.min_row, merge.max_row + 1):
            for c in range(merge.min_col, merge.max_col + 1):
                merged[(r, c)] = (mr, mc)

    def val(r, c):
        mr, mc = merged.get((r, c), (r, c))
        return ws_or.cell(mr, mc).value

    col_map = build_col_map(ws_or)

    anagrafica = []
    if SHEET_DOCENTI in wb.sheetnames:
        ws_doc = wb[SHEET_DOCENTI]
        for r in range(3, ws_doc.max_row + 1):
            cv = ws_doc.cell(r, 1).value
            if not cv:
                continue
            attivo_s = clean(ws_doc.cell(r, 6).value).upper()
            anagrafica.append({
                'cognome':       clean(cv).upper(),
                'nome':          clean(ws_doc.cell(r, 2).value),
                'materia':       clean(ws_doc.cell(r, 3).value),
                'ore_contratto': int(ws_doc.cell(r, 4).value or 0),
                'attivo':        attivo_s in ('SÌ','SI','S','1','TRUE'),
            })

    if _e_formato_a_tag(ws_or, val):
        slots = _parse_formato_a_tag(ws_or, val, col_map)
    else:
        slots = _parse_formato_orizzontale(ws_or, val, col_map)

    return {'docenti_anagrafica': anagrafica, 'slots': slots}


def applica_importazione(excel_path, db_session):
    from models.docente import Docente
    from models.orario_docente import OrarioDocente
    from models.sync_orario import AliasDocente, LogImportazione

    parsed = parse_file(excel_path)

    alias_map  = {a.nome_file.upper(): a.id_docente for a in AliasDocente.query.all()}
    docenti_db = {d.cognome.upper(): d for d in Docente.query.all()}

    def risolvi(cognome_file):
        cog = cognome_file.upper().strip()
        if cog in alias_map:
            from models import db
            return db.session.get(Docente, alias_map[cog])
        return docenti_db.get(cog)

    stats = {'slot_totali': 0, 'docenti_nuovi': 0,
             'aggiornati': 0, 'non_riconosciuti': set()}

    # Aggiorna/crea docenti
    for ana in parsed['docenti_anagrafica']:
        doc = risolvi(ana['cognome'])
        if doc is None:
            doc = Docente(
                cognome=ana['cognome'], nome=ana['nome'],
                nome_display=ana['cognome'],
                materia=ana['materia'] or None,
                ore_contratto=ana['ore_contratto'],
                attivo=ana['attivo'],
            )
            db_session.add(doc)
            db_session.flush()
            docenti_db[ana['cognome']] = doc
            stats['docenti_nuovi'] += 1
        else:
            changed = False
            if not doc.materia and ana['materia']:
                doc.materia = ana['materia']; changed = True
            if not doc.nome and ana['nome']:
                doc.nome = ana['nome']; changed = True
            if changed:
                stats['aggiornati'] += 1

    # Ricrea orario
    OrarioDocente.query.delete()
    db_session.flush()

    seen = set()
    for slot in parsed['slots']:
        doc = risolvi(slot['cognome_file'])
        if doc is None:
            stats['non_riconosciuti'].add(slot['cognome_file'])
            continue
        key = (doc.id, slot['giorno'], slot['ora'],
               'comp' if slot['tipo_ora'] == 'compresenza' else 'norm')
        if key in seen:
            continue
        seen.add(key)
        db_session.add(OrarioDocente(
            id_docente=doc.id, giorno=slot['giorno'], ora=slot['ora'],
            classe=slot['classe'], materia=slot['materia'],
            tipo_ora=slot['tipo_ora'],
        ))
        stats['slot_totali'] += 1

    # Salva log
    nr_list = list(stats['non_riconosciuti'])
    log = LogImportazione(
        file_nome=os.path.basename(excel_path),
        slot_totali=stats['slot_totali'],
        docenti_nuovi=stats['docenti_nuovi'],
        non_riconosciuti=json.dumps(nr_list),
        esito='warning' if nr_list else 'ok',
    )
    db_session.add(log)
    db_session.commit()

    stats['non_riconosciuti'] = nr_list
    return stats
