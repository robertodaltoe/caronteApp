"""
modules/prospetto_supplenze.py
Genera il Prospetto Supplenze giornaliero, leggendo la struttura
(righe classi, tabella firme) direttamente dal foglio del template
invece di righe fisse in Python — vedi _scegli_foglio()/_righe_classi()
/_righe_firme() più sotto per il perché (Roberto, 15/09/2026: i nomi
non comparivano nella griglia per le classi con sezione B, perché il
codice era ancorato al foglio 'MATRICE 25_26' dell'anno scorso mentre
quelle sezioni esistono solo nel foglio 'MATRICE 26_27', già presente
nel template ma mai usato).
"""
import io, re
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font

# Mappatura ora -> (col_assente, col_sostituto) — celle merged D:E, F:G, H:I...
# Verificata identica nei fogli 'MATRICE 25_26' e 'MATRICE 26_27' del
# template reale (stessa intestazione righe 7-8): a differenza delle
# righe classi, qui non serve derivarla dal foglio.
ORA_COLS = {
    1: (4,  6),   2: (8,  10),  3: (12, 14),
    4: (16, 18),  5: (20, 22),  6: (24, 26),
    7: (28, 30),  8: (32, 34),  9: (36, 38),
}

# Firme: (col_docente, col_euro, col_c, col_r, col_p) — colonne verificate
# identiche nei due fogli del template reale, solo le righe (FIRME_START/
# END) cambiano da un anno all'altro e vengono quindi derivate dal
# foglio (vedi _righe_firme), non fissate qui.
FIRME_COLS = [
    (2,  10, 11, 12, 13),   # col1: docente=B(2), €=J(10), C=K(11), R=L(12), P=M(13)
    (14, 22, 23, 24, 25),   # col2: docente=N(14), €=V(22), C=W(23), R=X(24), P=Y(25)
    (26, 34, 35, 36, 37),   # col3: docente=Z(26), €=AH(34), C=AI(35), R=AJ(36), P=AK(37)
]

FILL_TIPO = {
    'recupero':      PatternFill('solid', fgColor='C6EFCE'),
    'pagamento':     PatternFill('solid', fgColor='FFEB9C'),
    'completamento': PatternFill('solid', fgColor='D9D9D9'),
    'potenziamento': PatternFill('solid', fgColor='DDEBF7'),
    'disposizione':  PatternFill('solid', fgColor='E2EFDA'),
}

TIPO_SIGLA = {
    'recupero': 'R', 'pagamento': '€',
    'completamento': 'C', 'potenziamento': 'P', 'disposizione': 'D',
}

GIORNI_IT = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
MESI_IT   = ['','gennaio','febbraio','marzo','aprile','maggio','giugno',
             'luglio','agosto','settembre','ottobre','novembre','dicembre']

FONT_BOLD = Font(name='Calibri', size=10, bold=True)
FONT_DATA = Font(name='Calibri', size=11, bold=True)


def _norm(c):
    return re.sub(r'\s+', ' ', str(c).strip().upper())


def _norm_compatto(c):
    """Come _norm() ma toglie anche gli spazi residui, non solo li
    normalizza — serve a recuperare le classi salvate senza lo spazio
    fra sezione e indirizzo (es. "1ACAT" invece di "1A CAT": verificato
    sui dati reali, l'importazione orario usa sistematicamente il
    formato senza spazio). La chiave "ufficiale" resta quella con lo
    spazio (come scritta nel template), qui si prova solo un secondo
    tentativo prima di arrendersi."""
    return _norm(c).replace(' ', '')


def _data_label(d):
    return f"{GIORNI_IT[d.weekday()]} {d.day} {MESI_IT[d.month]} {d.year}"


def _scegli_foglio(wb):
    """Sceglie il foglio del template corrispondente all'anno
    scolastico corrente (es. anno '2026-2027' -> foglio 'MATRICE
    26_27') invece di un nome fisso: un nome fisso è esattamente la
    causa del bug segnalato da Roberto — 'MATRICE 25_26' (anno
    scorso) non ha le righe delle sezioni B aggiunte quest'anno
    (1B CAT, 1B AFM, 1B LSU, 3B LSC, 3B RIM), presenti invece nel
    foglio aggiornato 'MATRICE 26_27' già nel template ma mai
    raggiunto dal codice. Ricade sul foglio "MATRICE ..." più recente
    per nome se quello dell'anno esatto non è ancora stato preparato,
    segnalando comunque quale ha usato (restituito come secondo
    valore: True se corrisponde esattamente all'anno corrente)."""
    from config_anno import get_anno_corrente
    nome_atteso = None
    try:
        aa, bb = get_anno_corrente().split('-')
        nome_atteso = f'MATRICE {aa[-2:]}_{bb[-2:]}'
    except ValueError:
        pass

    if nome_atteso and nome_atteso in wb.sheetnames:
        return nome_atteso, True

    fogli_matrice = sorted(s for s in wb.sheetnames if s.upper().startswith('MATRICE'))
    if fogli_matrice:
        return fogli_matrice[-1], False
    return wb.sheetnames[0], False


def _righe_classi(ws):
    """Mappa classe(normalizzata) -> riga, letta DIRETTAMENTE dal
    foglio del template (colonna B, dalla prima riga classe fino a
    "FIRMA DOCENTI INTERESSATI") invece di un dizionario fisso in
    Python — così la mappatura segue sempre il template reale, anche
    quando viene aggiunta o tolta una sezione, senza bisogno di
    aggiornare il codice ogni volta (è esattamente quello che è
    mancato con le nuove sezioni B di quest'anno)."""
    righe = {}
    for r in range(9, ws.max_row + 1):
        v = ws.cell(r, 2).value
        if v is None:
            continue
        v = str(v).strip()
        if not v:
            continue
        if v.upper().startswith('FIRMA'):
            break
        righe[_norm(v)] = r
    return righe


def _righe_firme(ws):
    """Riga di inizio/fine della tabella firme, derivate cercando
    l'intestazione "DOCENTE" nel foglio invece di righe fisse (il
    foglio più recente ha una riga di intestazione in più rispetto a
    quello vecchio, spostando tutto in basso di due righe)."""
    for r in range(1, ws.max_row + 1):
        if str(ws.cell(r, 2).value or '').strip().upper() == 'DOCENTE':
            return r + 1, ws.max_row
    return None, None


def _trova_riga(classe_raw, righe_classi, non_trovate):
    """Riga del prospetto per una classe, provando prima la forma
    "ufficiale" (con spazio, come scritta nel template) e poi quella
    compatta (senza spazio, come la salva l'importazione orario) prima
    di arrendersi. Se non trova nulla, registra la classe in
    `non_trovate` (invece di scartarla silenziosamente: un vero errore
    di dati — una classe scritta in un modo non riconosciuto, o
    davvero assente dal template — spariva senza traccia dalla
    griglia, con il supplente comunque visibile in fondo nella tabella
    firme che non dipende da questo lookup) così la route può
    segnalarlo a Roberto."""
    riga = righe_classi.get(_norm(classe_raw))
    if riga is None:
        righe_compatte = {k.replace(' ', ''): v for k, v in righe_classi.items()}
        riga = righe_compatte.get(_norm_compatto(classe_raw))
    if riga is None:
        non_trovate.add(str(classe_raw).strip())
    return riga


def genera_prospetto(data_sel, supplenze, template_path, save_dir=None, attivita_ist=None):
    wb = load_workbook(template_path)

    nome_foglio_template, foglio_anno_corrente = _scegli_foglio(wb)
    ws = wb.copy_worksheet(wb[nome_foglio_template])
    nome_foglio = data_sel.strftime('%Y%m%d') + '_Prospetto supplenze'
    ws.title = nome_foglio

    righe_classi = _righe_classi(ws)
    firme_inizio, firme_fine = _righe_firme(ws)

    # ── 1. Data ───────────────────────────────────────────────
    data_str = _data_label(data_sel)
    ws.cell(4, 5).value = data_str
    ws.cell(4, 5).font  = FONT_DATA

    # ── 2. Docenti assenti/indisponibili in riga 4 e riga 5 ──
    # Raccogli cognomi distinti di assenti + indisponibili
    assenti_set = set()
    for s in supplenze:
        if s.stato != 'annullata' and s.assente:
            assenti_set.add(s.assente.cognome)

    # Recupera anche indisponibili del giorno dal DB
    from models.indisponibilita import Indisponibilita
    indisp_list = Indisponibilita.query.filter_by(data=data_sel).all()
    for i in indisp_list:
        if i.docente:
            assenti_set.add(i.docente.cognome)

    assenti_str = ', '.join(sorted(assenti_set))

    # Riga 4: M4 (col 13) — spazio tra H4:L4 e il resto
    ws.cell(4, 13).value = assenti_str
    ws.cell(4, 13).font  = FONT_BOLD

    # Riga 5: B5 (col 2) — cella unita B5:AB5
    ws.cell(5, 2).value = assenti_str
    ws.cell(5, 2).font  = FONT_BOLD

    # ── 3. Svuota celle dati ──────────────────────────────────
    for riga in righe_classi.values():
        for ora in range(1, 10):
            ca, cs = ORA_COLS[ora]
            try:
                ws.cell(riga, ca).value = None
                ws.cell(riga, cs).value = None
                ws.cell(riga, cs).fill  = PatternFill('none')
            except Exception:
                pass

    if firme_inizio:
        for col_doc, col_euro, col_c, col_r, col_p in FIRME_COLS:
            for riga in range(firme_inizio, firme_fine + 1):
                for c in [col_doc, col_euro, col_c, col_r, col_p]:
                    try:
                        ws.cell(riga, c).value = None
                    except Exception:
                        pass

    # ── 4. Compila supplenze ──────────────────────────────────
    classi_non_trovate = set()
    for s in supplenze:
        if s.stato == 'annullata' or s.ora not in ORA_COLS:
            continue

        riga = _trova_riga(s.classe, righe_classi, classi_non_trovate)
        if riga is None:
            continue

        ca, cs = ORA_COLS[s.ora]

        nome_ass  = s.assente.cognome if s.assente else ''
        nome_sost = ''

        if s.sostituto:
            sigla = TIPO_SIGLA.get(s.tipo or '', '')
            nome_sost = s.sostituto.cognome + (f' ({sigla})' if sigla else '')
        elif s.stato == 'scoperta':
            nome_sost = ''         # lascia vuota invece di ???
        elif s.stato == 'non_assegnabile':
            nome_sost = 'N/A'
            nome_ass  = ''

        try:
            if nome_ass:
                ws.cell(riga, ca).value = nome_ass
                ws.cell(riga, ca).font  = FONT_BOLD
            if nome_sost:
                ws.cell(riga, cs).value = nome_sost
                ws.cell(riga, cs).font  = FONT_BOLD
                if s.sostituto and s.tipo in FILL_TIPO:
                    ws.cell(riga, cs).fill = FILL_TIPO[s.tipo]
        except Exception:
            pass

    # ── 5. Tabella firme ──────────────────────────────────────
    sostituti = {}
    for s in supplenze:
        if s.stato == 'annullata' or not s.sostituto:
            continue
        nome = s.sostituto.cognome
        sostituti.setdefault(nome, set())
        if s.tipo:
            sostituti[nome].add(s.tipo)

    if firme_inizio:
        idx = 0
        for col_doc, col_euro, col_c, col_r, col_p in FIRME_COLS:
            for riga in range(firme_inizio, firme_fine + 1):
                if idx >= len(sostituti):
                    break
                nome, tipi = sorted(sostituti.items())[idx]
                try:
                    ws.cell(riga, col_doc).value = nome
                    ws.cell(riga, col_doc).font  = FONT_BOLD
                    if 'pagamento'     in tipi: ws.cell(riga, col_euro).value = 'X'
                    if 'completamento' in tipi: ws.cell(riga, col_c).value    = 'X'
                    if 'recupero'      in tipi: ws.cell(riga, col_r).value    = 'X'
                    if 'potenziamento' in tipi: ws.cell(riga, col_p).value    = 'X'
                except Exception:
                    pass
                idx += 1

    # ── 6. Attività Istituzionali del giorno ────────────────
    if attivita_ist:
        from openpyxl.styles import Alignment, Border, Side
        # Aggiungi un foglio separato "Att. Istituzionali"
        ws_ist = wb.create_sheet(title='Att. Istituzionali')
        _s = Side(style='thin', color='AAAAAA')
        _border = Border(left=_s, right=_s, top=_s, bottom=_s)
        _fill_hdr = PatternFill('solid', fgColor='1F3864')
        _font_hdr = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
        _font_ist = Font(name='Calibri', size=10)

        ws_ist.cell(1, 1).value = f'Attività Istituzionali — {_data_label(data_sel)}'
        ws_ist.cell(1, 1).font  = Font(name='Calibri', size=12, bold=True, color='1F3864')

        hdrs = ['Tipo', 'Titolo', 'Orario', 'Ore', 'Classe/Dip.', 'Partecipanti']
        for c, h in enumerate(hdrs, 1):
            cell = ws_ist.cell(3, c)
            cell.value = h; cell.fill = _fill_hdr
            cell.font  = _font_hdr; cell.border = _border
            cell.alignment = Alignment(horizontal='center', vertical='center')

        for r, ev in enumerate(attivita_ist, 4):
            orario = ''
            if ev.ora_inizio:
                orario = ev.ora_inizio + ('–' + ev.ora_fine if ev.ora_fine else '')
            classe_dip = ev.classe or ''
            if ev.dipartimento:
                classe_dip = ev.dipartimento.sigla
            n_part = len(ev.partecipanti) if ev.partecipanti else 0
            n_pres = sum(1 for p in ev.presenze if p.stato == 'presente') if ev.presenze else '—'

            vals = [
                ev.tipo_label,
                ev.titolo,
                orario,
                f'{ev.durata_ore:.1f}h' if ev.durata_ore else '—',
                classe_dip,
                f'{n_pres}/{n_part}' if ev.presenze else f'{n_part} previsti',
            ]
            for c, v in enumerate(vals, 1):
                cell = ws_ist.cell(r, c)
                cell.value = v; cell.font = _font_ist; cell.border = _border

        ws_ist.column_dimensions['A'].width = 22
        ws_ist.column_dimensions['B'].width = 40
        ws_ist.column_dimensions['C'].width = 12
        ws_ist.column_dimensions['D'].width = 8
        ws_ist.column_dimensions['E'].width = 14
        ws_ist.column_dimensions['F'].width = 18

    # ── 7. Rimuovi altri fogli e salva ────────────────────────
    fogli_da_tenere = {nome_foglio}
    if attivita_ist:
        fogli_da_tenere.add('Att. Istituzionali')
    for nome in [s for s in wb.sheetnames if s not in fogli_da_tenere]:
        del wb[nome]

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    xlsx_bytes = buf.getvalue()

    if save_dir:
        import os
        os.makedirs(save_dir, exist_ok=True)
        nome_file = nome_foglio.replace(' ', '_') + '.xlsx'
        with open(os.path.join(save_dir, nome_file), 'wb') as f:
            f.write(xlsx_bytes)

    avviso_foglio = None if foglio_anno_corrente else (
        f'usato il foglio "{nome_foglio_template}" del template perché non ne ho trovato uno per '
        f'l\'anno scolastico corrente — verifica che sia quello giusto, o aggiungi il foglio aggiornato '
        f'al template.')

    return xlsx_bytes, sorted(classi_non_trovate), avviso_foglio
