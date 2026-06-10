import os, io
from flask import Blueprint, render_template, request, send_file, abort, flash, redirect, url_for
from models import db
from models.docente import Docente
from models.movimento_banca_ore import MovimentoBancaOre
from models.supplenza import Supplenza
from models.assenza import Assenza
from sqlalchemy import func
from datetime import date


def get_ore_ist_docente(id_docente, anno=None):
    """
    Calcola ore bucket A e B per un docente nell'a.s. (solo presenze=presente).
    Usato per contatore CCNL art.44.
    """
    from models.attivita_ist import AttivitaIst, AttivitaIstPresenza, TIPI_ATTIVITA
    if anno is None:
        oggi = date.today()
        anno_ini = date(oggi.year if oggi.month >= 9 else oggi.year - 1, 9, 1)
        anno_fin = date(anno_ini.year + 1, 8, 31)
    else:
        anno_ini = date(int(anno[:4]), 9, 1)
        anno_fin = date(int(anno[:4]) + 1, 8, 31)

    try:
        presenze = (AttivitaIstPresenza.query
                    .join(AttivitaIst,
                          AttivitaIst.id == AttivitaIstPresenza.id_attivita)
                    .filter(AttivitaIstPresenza.id_docente == id_docente,
                            AttivitaIstPresenza.stato == 'presente',
                            AttivitaIst.data >= anno_ini,
                            AttivitaIst.data <= anno_fin)
                    .all())
    except Exception:
        return {'A': 0.0, 'B': 0.0, 'limite': 40}

    ore_a = round(sum(p.ore_effettive for p in presenze
                      if TIPI_ATTIVITA.get(p.attivita.tipo, {}).get('bucket') == 'A'), 1)
    ore_b = round(sum(p.ore_effettive for p in presenze
                      if TIPI_ATTIVITA.get(p.attivita.tipo, {}).get('bucket') == 'B'), 1)

    # Dettaglio per il prospetto: lista presenze ordinate per data
    dettaglio = sorted(presenze, key=lambda p: p.attivita.data)

    return {'A': ore_a, 'B': ore_b, 'limite': 40, 'dettaglio': dettaglio}

report_bp = Blueprint('report', __name__)

# ── Costanti ──────────────────────────────────────────────────
TIPI_SUPPLENZA = ('supplenza_recupero', 'supplenza_completamento',
                   'supplenza_potenziamento', 'supplenza_disposizione')
TIPI_PERMESSO  = ('permesso', 'assenza', 'permesso_orario')
TIPI_PERM_IST  = ('permesso_ist',)   # permesso orario su att. istituzionali
TIPI_CIVICA    = ('civica', 'ed_civica')
TIPI_PAGAMENTO = ('supplenza_pagamento',)


def get_saldi_docente(id_docente):
    """
    Calcola saldi per un docente separando effettivo (<=oggi) e previsto (>oggi).
    Ritorna dict con chiavi:
      supplenze, permessi, civica, pagamento  — tutto (effettivo + previsto)
      sup_svolte, perm_svolte, civ_svolte     — solo fino a oggi
      sup_prev, perm_prev, civ_prev           — solo future
    """
    oggi = date.today()
    movimenti = MovimentoBancaOre.query.filter_by(id_docente=id_docente).all()

    def somma(movs, tipi, abs_val=False):
        vals = [abs(m.minuti) if abs_val else m.minuti
                for m in movs if m.tipo in tipi]
        return sum(vals) // 60

    svolti  = [m for m in movimenti if m.data and m.data <= oggi]
    previsti = [m for m in movimenti if m.data and m.data > oggi]

    return {
        # Totale (per retrocompatibilità)
        'supplenze':   somma(movimenti, TIPI_SUPPLENZA),
        'permessi':    somma(movimenti, TIPI_PERMESSO, abs_val=True),
        'perm_ist':    somma(movimenti, TIPI_PERM_IST, abs_val=True),
        'civica':      somma(movimenti, TIPI_CIVICA,   abs_val=True),
        'pagamento':   somma(movimenti, TIPI_PAGAMENTO, abs_val=True),
        # Effettivo (svolto — <= oggi)
        'sup_svolte':  somma(svolti,  TIPI_SUPPLENZA),
        'perm_svolte': somma(svolti,  TIPI_PERMESSO, abs_val=True),
        'civ_svolte':  somma(svolti,  TIPI_CIVICA,   abs_val=True),
        # Previsto (futuro — > oggi)
        'sup_prev':  somma(previsti, TIPI_SUPPLENZA),
        'perm_prev': somma(previsti, TIPI_PERMESSO, abs_val=True),
        'civ_prev':  somma(previsti, TIPI_CIVICA,   abs_val=True),
    }


def get_storico_settimanale(id_docente):
    """
    Raggruppa i movimenti per settimana (data).
    Ritorna lista di dict ordinata per data.
    """
    movimenti = (MovimentoBancaOre.query
                 .filter_by(id_docente=id_docente)
                 .order_by(MovimentoBancaOre.data)
                 .all())

    # Raggruppa per data
    from collections import defaultdict
    per_data = defaultdict(lambda: {
        'supplenze': 0, 'permessi': 0, 'civica': 0, 'pagamento': 0, 'altro': 0
    })
    for m in movimenti:
        d = m.data
        if m.tipo in TIPI_SUPPLENZA:
            per_data[d]['supplenze'] += m.minuti // 60
        elif m.tipo in TIPI_PERMESSO:
            per_data[d]['permessi'] += abs(m.minuti) // 60
        elif m.tipo in TIPI_CIVICA:
            per_data[d]['civica'] += abs(m.minuti) // 60
        elif m.tipo in TIPI_PAGAMENTO:
            per_data[d]['pagamento'] += abs(m.minuti) // 60
        else:
            per_data[d]['altro'] += m.minuti // 60

    return [{'data': d, **v} for d, v in sorted(per_data.items())]


# ── INDICE REPORT ────────────────────────────────────────────
@report_bp.route('/report')
def index():
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    # Calcola saldi per tutti
    saldi = {}
    for d in docenti:
        s = get_saldi_docente(d.id)
        lordo_eff   = s['sup_svolte'] - s['perm_svolte'] - s['civ_svolte']
        netto_eff   = lordo_eff - s['pagamento']
        lordo_prev  = s['sup_prev'] - s['perm_prev'] - s['civ_prev']
        saldo_lordo = s['supplenze'] - s['permessi'] - s['civica']
        saldo_netto = saldo_lordo - s['pagamento']
        saldi[d.id] = {**s,
            'lordo': saldo_lordo, 'netto': saldo_netto,
            'netto_eff': netto_eff, 'lordo_eff': lordo_eff,
            'netto_prev': lordo_prev,
        }

    # Costo ora supplenza (configurabile — default 29.08€ lordi)
    COSTO_ORA = 29.08

    # Ore istituzionali per tutti (solo ruoli interni)
    from flask import session as _sess2
    ruolo_idx = _sess2.get('ruolo', 'collaboratore')
    ore_ist_idx = {}
    if ruolo_idx in ('ds', 'dsga', 'segreteria'):
        for d in docenti:
            ore_ist_idx[d.id] = get_ore_ist_docente(d.id)

    return render_template('report/index.html',
        docenti=docenti, saldi=saldi, oggi=date.today(),
        costo_ora=COSTO_ORA,
        ore_ist_idx=ore_ist_idx,
        ruolo_utente=ruolo_idx)


# ── REPORT SINGOLO DOCENTE ───────────────────────────────────
@report_bp.route('/report/docente/<int:id>')
def singolo(id):
    d = Docente.query.get_or_404(id)
    saldi   = get_saldi_docente(id)
    storico = get_storico_settimanale(id)

    # Saldo effettivo (ore già svolte, <= oggi)
    saldo_lordo_eff  = saldi['sup_svolte'] - saldi['perm_svolte'] - saldi['civ_svolte']
    saldo_netto_eff  = saldo_lordo_eff - saldi['pagamento']

    # Saldo previsto (include anche ore future)
    saldo_lordo_prev = saldi['sup_prev'] - saldi['perm_prev'] - saldi['civ_prev']
    saldo_netto_prev = saldo_lordo_prev  # pagamento non si applica al futuro

    # Totale complessivo (retrocompatibilità)
    saldo_lordo   = saldi['supplenze'] - saldi['permessi'] - saldi.get('perm_ist',0) - saldi['civica']
    saldo_netto   = saldo_lordo - saldi['pagamento']

    # Supplenze dettaglio
    supplenze = (Supplenza.query
                 .filter_by(id_sostituto=id)
                 .filter(Supplenza.stato == 'assegnata')
                 .order_by(Supplenza.data)
                 .all())

    # Orario settimanale del docente
    from models.orario_docente import OrarioDocente
    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
    slots = OrarioDocente.query.filter_by(id_docente=id).order_by(
        OrarioDocente.giorno, OrarioDocente.ora).all()
    # Struttura: {giorno: {ora: slot}}
    orario = {}
    ore_usate = set()
    for s in slots:
        if s.classe and s.classe not in ('---', '-x-', ''):
            orario.setdefault(s.giorno, {})[s.ora] = s
            ore_usate.add(s.ora)
    ore_list = sorted(ore_usate) if ore_usate else list(range(1, 6))
    giorni_usati = sorted(set(s.giorno for s in slots))

    # Ore CCNL istituzionali (solo per ruoli interni)
    from flask import session as _sess
    ruolo_utente = _sess.get('ruolo', 'collaboratore')
    ore_ist = None
    if ruolo_utente in ('ds', 'dsga', 'segreteria'):
        ore_ist = get_ore_ist_docente(id)

    return render_template('report/singolo.html',
        docente=d,
        saldi=saldi,
        saldo_lordo=saldo_lordo,
        saldo_netto=saldo_netto,
        saldo_lordo_eff=saldo_lordo_eff,
        saldo_netto_eff=saldo_netto_eff,
        saldo_lordo_prev=saldo_lordo_prev,
        saldo_netto_prev=saldo_netto_prev,
        storico=storico,
        supplenze=supplenze,
        orario=orario,
        ore_list=ore_list,
        giorni_usati=giorni_usati,
        giorni_nomi=GIORNI,
        oggi=date.today(),
        ore_ist=ore_ist,
        ruolo_utente=ruolo_utente,
    )


# ── REPORT SINGOLO — EXPORT PDF ──────────────────────────────
@report_bp.route('/report/docente/<int:id>/pdf')
def singolo_pdf(id):
    """Genera PDF del report singolo via WeasyPrint o fallback HTML."""
    d = Docente.query.get_or_404(id)
    saldi   = get_saldi_docente(id)
    storico = get_storico_settimanale(id)

    saldo_lordo     = saldi['supplenze'] - saldi['permessi'] - saldi['civica']
    saldo_netto     = saldo_lordo - saldi['pagamento']

    supplenze = (Supplenza.query
                 .filter_by(id_sostituto=id)
                 .filter(Supplenza.stato == 'assegnata')
                 .order_by(Supplenza.data)
                 .all())

    html_content = render_template('report/singolo_print.html',
        docente=d, saldi=saldi,
        saldo_lordo=saldo_lordo, saldo_netto=saldo_netto,
        storico=storico, supplenze=supplenze,
        oggi=date.today(),
    )

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'report_{d.cognome}_{date.today().isoformat()}.pdf'
        )
    except ImportError:
        # WeasyPrint non installato — ritorna HTML con print CSS
        return html_content


# ── REPORT SINGOLO — EXPORT XLSX ────────────────────────────
@report_bp.route('/report/docente/<int:id>/xlsx')
def singolo_xlsx(id):
    from modules.xlsx_report import _build_xlsx_singolo
    d        = Docente.query.get_or_404(id)
    saldi    = get_saldi_docente(id)
    storico  = get_storico_settimanale(id)
    saldo_lordo = saldi['supplenze'] - saldi['permessi'] - saldi['civica']
    netto    = saldo_lordo - saldi['pagamento']
    effettivo= netto
    supplenze= (Supplenza.query.filter_by(id_sostituto=id)
                .filter(Supplenza.stato=='assegnata')
                .order_by(Supplenza.data).all())

    wb = _build_xlsx_singolo(d, saldi, storico, supplenze, netto, effettivo, date.today())
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'DOC_{d.cognome}_{date.today().isoformat()}.xlsx'
    )


# ── REPORT GLOBALE XLSX ──────────────────────────────────────
@report_bp.route('/report/globale/xlsx')
def globale_xlsx():
    """Export XLSX con foglio indice + un foglio per docente."""
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    except ImportError:
        return "openpyxl non disponibile", 500

    wb = openpyxl.Workbook()

    BLU   = PatternFill("solid", fgColor="1F3864")
    VERDE = PatternFill("solid", fgColor="D4F0E0")
    ROSSO = PatternFill("solid", fgColor="FDE8E8")
    GIALL = PatternFill("solid", fgColor="FFF3CD")
    GREY  = PatternFill("solid", fgColor="F0F4F8")

    def hdr(cell, text, fill=BLU):
        cell.value = text
        cell.fill  = fill
        cell.font  = Font(bold=True,
                          color="FFFFFF" if fill == BLU else "000000",
                          size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                    wrap_text=True)

    def thin():
        s = Side(style="thin", color="AAAAAA")
        return Border(left=s, right=s, top=s, bottom=s)

    # ── Foglio Indice ─────────────────────────────────────────
    ws_idx = wb.active
    ws_idx.title = "Indice"

    ws_idx.merge_cells("A1:H1")
    ws_idx["A1"].value = f"BANCA ORE DOCENTI — IIS Da Vinci Chiavenna — {date.today().strftime('%d/%m/%Y')}"
    ws_idx["A1"].font  = Font(bold=True, size=14, color="1F3864")
    ws_idx.row_dimensions[1].height = 28

    headers = ["Docente", "H/sett", "Supplenze\nsvolte",
               "Permessi\norari", "Ed. Civica\nlibero",
               "Ore a\npagamento", "Saldo\nnetto", "Situazione"]
    for c, h in enumerate(headers, 1):
        hdr(ws_idx.cell(3, c), h)
    ws_idx.row_dimensions[3].height = 32

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    for row_n, d in enumerate(docenti, 4):
        s = get_saldi_docente(d.id)
        lordo = s['supplenze'] - s['permessi'] - s['civica']
        netto = lordo - s['pagamento']

        ws_idx.cell(row_n, 1).value = d.cognome + (f" {d.nome}" if d.nome else "")
        ws_idx.cell(row_n, 2).value = d.ore_contratto
        ws_idx.cell(row_n, 3).value = s['supplenze']
        ws_idx.cell(row_n, 4).value = s['permessi']
        ws_idx.cell(row_n, 5).value = s['civica']
        ws_idx.cell(row_n, 6).value = s['pagamento'] if s['pagamento'] else None
        ws_idx.cell(row_n, 7).value = netto

        if netto > 0:
            sit, fill = "CREDITO", VERDE
        elif netto < 0:
            sit, fill = "RECUPERO", ROSSO
        else:
            sit, fill = "OK", GREY
        ws_idx.cell(row_n, 8).value = sit
        ws_idx.cell(row_n, 8).fill  = fill

        # Colora saldo
        ws_idx.cell(row_n, 7).fill = VERDE if netto > 0 else (ROSSO if netto < 0 else GREY)
        ws_idx.cell(row_n, 3).fill = VERDE if s['supplenze'] > 0 else GREY
        ws_idx.cell(row_n, 4).fill = ROSSO if s['permessi'] > 0 else GREY
        ws_idx.cell(row_n, 5).fill = ROSSO if s['civica']   > 0 else GREY

        for c in range(1, 9):
            ws_idx.cell(row_n, c).border = thin()
            ws_idx.cell(row_n, c).alignment = Alignment(horizontal="center",
                                                          vertical="center")
        ws_idx.cell(row_n, 1).alignment = Alignment(horizontal="left",
                                                      vertical="center")

    # Larghezze colonne indice
    for col, w in zip("ABCDEFGH", [28, 8, 12, 12, 12, 12, 10, 12]):
        ws_idx.column_dimensions[col].width = w

    # ── Foglio per ogni docente ───────────────────────────────
    for d in docenti:
        s       = get_saldi_docente(d.id)
        storico = get_storico_settimanale(d.id)
        lordo     = s['supplenze'] - s['permessi'] - s['civica']
        netto     = lordo - s['pagamento']
        effettivo = netto

        safe_name = d.cognome[:28].replace('/', '_').replace('\\', '_')
        try:
            ws = wb.create_sheet(title=f"DOC_{safe_name}")
        except Exception:
            ws = wb.create_sheet(title=f"DOC_{d.id}")

        # Testata
        ws.merge_cells("A1:G1")
        ws["A1"].value = f"Report banca ore — {d.cognome}{' ' + d.nome if d.nome else ''}"
        ws["A1"].font  = Font(bold=True, size=13, color="1F3864")
        ws.row_dimensions[1].height = 24

        ws["A3"].value = "Saldo netto"
        ws["B3"].value = netto
        ws["A4"].value = "Saldo effettivo (dopo pagamento)"
        ws["B4"].value = effettivo
        ws["A5"].value = "Aggiornamento"
        ws["B5"].value = date.today().strftime('%d/%m/%Y')
        for r in [3,4,5]:
            ws.cell(r,1).font = Font(bold=True, size=10)

        for row_v in [(3, netto), (4, effettivo)]:
            fill = VERDE if row_v[1] > 0 else (ROSSO if row_v[1] < 0 else GREY)
            ws.cell(row_v[0], 2).fill = fill

        # Intestazioni storico
        hdrs_s = ["Data", "Supplenze\n+h", "Permessi\n-h",
                  "Ed. Civica\n-h", "Pagamento\nh", "Delta\ngiornata"]
        for c, h in enumerate(hdrs_s, 1):
            hdr(ws.cell(7, c), h)
        ws.row_dimensions[7].height = 30

        for r_n, riga in enumerate(storico, 8):
            delta = riga['supplenze'] - riga['permessi'] - riga['civica']
            ws.cell(r_n, 1).value = riga['data'].strftime('%d/%m/%Y') if riga['data'] else ''
            ws.cell(r_n, 2).value = riga['supplenze'] or None
            ws.cell(r_n, 3).value = riga['permessi']  or None
            ws.cell(r_n, 4).value = riga['civica']    or None
            ws.cell(r_n, 5).value = riga['pagamento'] or None
            ws.cell(r_n, 6).value = delta             if delta != 0 else None

            ws.cell(r_n, 2).fill = VERDE if riga['supplenze'] > 0 else GREY
            ws.cell(r_n, 3).fill = ROSSO if riga['permessi']  > 0 else GREY
            ws.cell(r_n, 4).fill = ROSSO if riga['civica']    > 0 else GREY
            ws.cell(r_n, 6).fill = VERDE if delta > 0 else (ROSSO if delta < 0 else GREY)

            for c in range(1, 7):
                ws.cell(r_n, c).border = thin()
                ws.cell(r_n, c).alignment = Alignment(horizontal="center")

        # Totali
        last = 8 + len(storico)
        ws.cell(last, 1).value = "TOTALI"
        ws.cell(last, 1).font  = Font(bold=True)
        ws.cell(last, 2).value = s['supplenze']
        ws.cell(last, 3).value = s['permessi']
        ws.cell(last, 4).value = s['civica']
        ws.cell(last, 5).value = s['pagamento']
        ws.cell(last, 6).value = netto
        for c in range(1, 7):
            ws.cell(last, c).font   = Font(bold=True)
            ws.cell(last, c).border = thin()

        for col, w in zip("ABCDEF", [14, 10, 10, 10, 10, 10]):
            ws.column_dimensions[col].width = w

    # ── Salva in buffer ───────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'BancaOre_completa_{date.today().isoformat()}.xlsx'
    )


# ── PROSPETTO SUPPLENZE GIORNALIERO ─────────────────────────
@report_bp.route('/prospetto')
@report_bp.route('/prospetto/<string:data_str>')
def prospetto(data_str=None):
    import os
    from modules.prospetto_supplenze import genera_prospetto

    if data_str is None:
        data_str = date.today().isoformat()
    try:
        data_sel = date.fromisoformat(data_str)
    except ValueError:
        data_sel = date.today()

    template_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'prospetto_template.xlsx'
    )
    if not os.path.exists(template_path):
        return 'Template prospetto non trovato in data/prospetto_template.xlsx', 404

    supplenze = (Supplenza.query
                 .filter_by(data=data_sel)
                 .filter(Supplenza.stato != 'annullata')
                 .order_by(Supplenza.ora)
                 .all())

    # Attività istituzionali del giorno per il prospetto
    try:
        from models.attivita_ist import AttivitaIst
        attivita_ist_giorno = (AttivitaIst.query
                               .filter_by(data=data_sel)
                               .order_by(AttivitaIst.ora_inizio)
                               .all())
    except Exception:
        attivita_ist_giorno = []

    save_dir   = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              'data', 'prospetti')
    xlsx_bytes = genera_prospetto(data_sel, supplenze, template_path,
                                  save_dir=save_dir,
                                  attivita_ist=attivita_ist_giorno)

    nome_file = f'Prospetto_supplenze_{data_sel.strftime("%d%m%Y")}.xlsx'
    return send_file(
        io.BytesIO(xlsx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome_file
    )



# ── ESPORTA TUTTI PDF ────────────────────────────────────────
@report_bp.route('/report/esporta-tutti-pdf')
def esporta_tutti_pdf():
    """Genera un PDF per ogni docente e li restituisce in uno ZIP."""
    import zipfile
    try:
        from weasyprint import HTML
    except ImportError:
        return 'WeasyPrint non installato — impossibile generare PDF', 500

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    oggi_str = date.today().isoformat()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d in docenti:
            try:
                saldi   = get_saldi_docente(d.id)
                storico = get_storico_settimanale(d.id)
                saldo_lordo = saldi['supplenze'] - saldi['permessi'] - saldi['civica']
                saldo_netto = saldo_lordo - saldi['pagamento']
                supplenze = (Supplenza.query
                             .filter_by(id_sostituto=d.id)
                             .filter(Supplenza.stato == 'assegnata')
                             .order_by(Supplenza.data)
                             .all())
                html_content = render_template('report/singolo_print.html',
                    docente=d, saldi=saldi,
                    saldo_lordo=saldo_lordo, saldo_netto=saldo_netto,
                    storico=storico, supplenze=supplenze,
                    oggi=date.today(),
                )
                pdf_bytes = HTML(string=html_content).write_pdf()
                fname = f'DOC_{d.cognome}.pdf'
                zf.writestr(fname, pdf_bytes)
            except Exception as e:
                # Aggiungi file di errore invece di fallire tutto
                zf.writestr(f'ERRORE_{d.cognome}.txt', str(e))

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'BancaOre_PDF_{oggi_str}.zip'
    )

# ── EXPORT EXCEL SETTIMANA ──────────────────────────────────
@report_bp.route('/export/excel', methods=['GET', 'POST'])
def export_excel():
    from modules.export_excel_sett import aggiorna_sett_excel, aggiorna_riepilogo_excel
    from models.movimento_banca_ore import MovimentoBancaOre
    from modules.import_banca_ore import leggi_movimenti_file
    import glob

    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'data', 'Banca_Ore_Docenti_v3.xlsm')

    # Settimane disponibili dal file
    from openpyxl import load_workbook as _lw
    wb = _lw(file_path, data_only=True)
    from modules.import_banca_ore import _parse_data_settimana
    # Rileva TUTTE le settimane presenti nel file (anche se aggiunte dopo)
    settimane = []
    import re as _re
    for nome in wb.sheetnames:
        m = _re.match(r'^sett\.(\d+)$', nome)
        if not m:
            continue
        sn = int(m.group(1))
        titolo = wb[nome].cell(1,1).value
        data   = _parse_data_settimana(str(titolo) if titolo else None)
        settimane.append({'n': sn, 'titolo': str(titolo) if titolo else nome, 'data': data})
    settimane.sort(key=lambda x: x['n'])

    msg = None
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'sett':
            sett_n = int(request.form.get('sett_n', 30))

            # Determina le date della settimana dal titolo del foglio Excel
            from openpyxl import load_workbook as _lw2
            from modules.import_banca_ore import _parse_data_settimana
            from datetime import timedelta
            _wb2 = _lw2(file_path, data_only=True)
            if f'sett.{sett_n}' not in _wb2.sheetnames:
                flash(f'Foglio sett.{sett_n} non trovato.', 'error')
                return redirect(url_for('report.export_excel'))
            _titolo = _wb2[f'sett.{sett_n}'].cell(1,1).value
            data_inizio = _parse_data_settimana(str(_titolo) if _titolo else None)
            if not data_inizio:
                flash(f'Impossibile determinare la data della sett.{sett_n}', 'error')
                return redirect(url_for('report.export_excel'))
            data_fine = data_inizio + timedelta(days=6)

            # Raccoglie movimenti DB per quella settimana per DATE
            movs = MovimentoBancaOre.query.filter(
                MovimentoBancaOre.data.between(data_inizio, data_fine)
            ).all()

            from models.docente import Docente as _D
            dati = {}
            for m in movs:
                d = db.session.get(_D, m.id_docente)
                if not d:
                    continue
                cog = d.cognome.upper().replace('’', "'").replace('‘', "'")
                if cog not in dati:
                    dati[cog] = {'sup': 0, 'perm': 0, 'civ': 0}
                if m.tipo == 'supplenza_recupero':
                    dati[cog]['sup'] += abs(m.minuti) // 60
                elif m.tipo in ('permesso_orario', 'permesso'):
                    dati[cog]['perm'] += abs(m.minuti) // 60
                elif m.tipo in ('civica', 'ed_civica'):
                    dati[cog]['civ'] += abs(m.minuti) // 60

            ok, msg = aggiorna_sett_excel(sett_n, dati, file_path)
            flash(
                msg + f' | {data_inizio.strftime("%d/%m")}–{data_fine.strftime("%d/%m/%Y")} | {len(movs)} movimenti',
                'success' if ok else 'error'
            )

        elif azione == 'riepilogo':
            # Aggiorna riepilogo completo
            from models.docente import Docente as _D
            from models.movimento_banca_ore import MovimentoBancaOre as _M
            all_movs = _M.query.all()
            saldi = {}
            pagamenti = {}
            for m in all_movs:
                d = _D.query.get(m.id_docente)
                if not d:
                    continue
                cog = d.cognome.upper().replace('’', "'")
                if cog not in saldi:
                    saldi[cog] = {'sup': 0, 'perm': 0, 'civ': 0}
                if m.tipo == 'supplenza_recupero':
                    saldi[cog]['sup'] += abs(m.minuti) // 60
                elif m.tipo in ('permesso_orario', 'permesso'):
                    saldi[cog]['perm'] += abs(m.minuti) // 60
                elif m.tipo in ('civica', 'ed_civica'):
                    saldi[cog]['civ'] += abs(m.minuti) // 60
                elif m.tipo == 'supplenza_pagamento':
                    pagamenti[cog] = pagamenti.get(cog, 0) + abs(m.minuti) // 60

            ok, msg = aggiorna_riepilogo_excel(saldi, pagamenti, file_path)
            flash(msg, 'success' if ok else 'error')

        return redirect(url_for('report.export_excel'))

    return render_template('report/export_excel.html',
        settimane=settimane, oggi=date.today())


# ── OTTIMIZZAZIONE SIMULAZIONI ────────────────────────────────
@report_bp.route('/ottimizzazione-simulazioni')
def ottimizzazione_simulazioni():
    """
    Prospetto ottimizzato per i giorni di simulazione:
    - Per ogni supplenza scoperta, suggerisce il sostituto ideale in base al saldo banca ore
    - Privilegia debitori, libera creditori con permessi
    """
    from models.supplenza import Supplenza
    from models.indisponibilita import Indisponibilita
    from models.orario_docente import OrarioDocente
    from models.assenza import Assenza
    from models.attivita_fuori_aula import AttivitaFuoriAula
    from collections import defaultdict

    oggi = date.today()

    # Date simulazioni (escludi festivi lun/mar 1-2 giugno)
    att_sim_all = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.tipo == 'simulazione',
        AttivitaFuoriAula.data_fine >= oggi,
        AttivitaFuoriAula.stato == 'attiva'
    ).all()
    date_sim_set = set()
    for a in att_sim_all:
        cur = a.data_inizio
        from datetime import timedelta
        while cur <= a.data_fine:
            if cur >= oggi and cur.weekday() < 6:
                date_sim_set.add(cur)
            cur += timedelta(days=1)
    date_sim_ordered = sorted(date_sim_set)

    # Saldi effettivi attuali per tutti i docenti
    docenti_attivi = Docente.query.filter_by(attivo=True).all()
    saldi_att = {}
    for d in docenti_attivi:
        movs = MovimentoBancaOre.query.filter(
            MovimentoBancaOre.id_docente == d.id,
            MovimentoBancaOre.data <= oggi
        ).all()
        sup  = sum(m.minuti for m in movs if m.tipo == 'supplenza_recupero') // 60
        perm = sum(abs(m.minuti) for m in movs if m.tipo in ('permesso_orario','permesso')) // 60
        civ  = sum(abs(m.minuti) for m in movs if m.tipo in ('civica','ed_civica')) // 60
        pag  = sum(abs(m.minuti) for m in movs if m.tipo == 'supplenza_pagamento') // 60
        saldi_att[d.id] = sup - perm - civ - pag

    # Sorveglianza già accreditata nel periodo simulazioni
    if date_sim_ordered:
        movs_sorv = MovimentoBancaOre.query.filter(
            MovimentoBancaOre.data.between(date_sim_ordered[0], date_sim_ordered[-1]),
            MovimentoBancaOre.descrizione.like('Sorveglianza%')
        ).all()
    else:
        movs_sorv = []
    sorv_per_doc = defaultdict(int)
    for m in movs_sorv:
        sorv_per_doc[m.id_docente] += m.minuti // 60

    # Proiezione = saldo attuale + sorveglianza
    saldi_proj = {d.id: saldi_att.get(d.id, 0) + sorv_per_doc.get(d.id, 0)
                  for d in docenti_attivi}

    # Date simulazioni future
    att_sim = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.tipo == 'simulazione',
        AttivitaFuoriAula.data_fine >= oggi,
        AttivitaFuoriAula.stato == 'attiva'
    ).all()
    date_sim = sorted(set(
        d for a in att_sim
        for d in (a.data_inizio,) if a.data_inizio >= oggi
    ))

    # Saldi effettivi per tutti i docenti attivi
    docenti_attivi = Docente.query.filter_by(attivo=True).all()
    saldi = {}
    for d in docenti_attivi:
        movs = MovimentoBancaOre.query.filter(
            MovimentoBancaOre.id_docente == d.id,
            MovimentoBancaOre.data <= oggi
        ).all()
        sup  = sum(m.minuti for m in movs if m.tipo == 'supplenza_recupero') // 60
        perm = sum(abs(m.minuti) for m in movs if m.tipo in ('permesso_orario','permesso')) // 60
        civ  = sum(abs(m.minuti) for m in movs if m.tipo in ('civica','ed_civica')) // 60
        pag  = sum(abs(m.minuti) for m in movs if m.tipo == 'supplenza_pagamento') // 60
        saldi[d.id] = sup - perm - civ - pag

    # Per ogni giorno di simulazione, calcola il prospetto
    prospetto = {}
    for data_sim in date_sim:
        giorno = data_sim.weekday()

        # Supplenze scoperte
        sups_scoperte = Supplenza.query.filter_by(
            data=data_sim, stato='scoperta'
        ).order_by(Supplenza.ora).all()

        # Indisponibili e assenti
        indisp_ids_per_ora = defaultdict(set)
        for i in Indisponibilita.query.filter_by(data=data_sim).all():
            indisp_ids_per_ora[i.ora].add(i.id_docente)
        assenti_ids = {a.id_docente for a in Assenza.query.filter_by(data=data_sim).all()}

        # Per ogni supplenza scoperta, trova i migliori sostituti
        righe = []
        for s in sups_scoperte:
            d_ass = db.session.get(Docente, s.id_assente) if s.id_assente else None

            # Docenti disponibili in quell'ora
            occupati = set()
            # Chi è a scuola in quell'ora (ha lezione)
            for slot in OrarioDocente.query.filter_by(giorno=giorno, ora=s.ora).all():
                if slot.tipo_ora == 'lezione' and slot.classe not in ('POTENZIAMENTO','---','-x-',''):
                    if slot.id_docente != (s.id_assente or -1):
                        occupati.add(slot.id_docente)

            disponibili = []
            for d in docenti_attivi:
                if d.id in assenti_ids: continue
                if d.id in indisp_ids_per_ora.get(s.ora, set()): continue
                if d.id in occupati: continue
                if d.id == (s.id_assente or -1): continue
                disponibili.append(d)

            # Calcola giorni liberi per ogni candidato (nessuna lezione in tutto il giorno)
            def giorni_liberi_docente(doc_id, escludi_giorno=None):
                GIORNI_NOMI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
                liberi = []
                for g in range(6):
                    if g == escludi_giorno:
                        continue
                    slots = OrarioDocente.query.filter_by(id_docente=doc_id, giorno=g).filter(
                        OrarioDocente.tipo_ora.in_(['lezione','potenziamento'])
                    ).count()
                    if slots == 0:
                        liberi.append(GIORNI_NOMI[g])
                return liberi

            # Controlla se il giorno della supplenza è libero per il candidato
            giorno_supplenza = data_sim.weekday()

            # Ordina per proiezione (saldo attuale + sorveglianza già accreditata)
            disponibili.sort(key=lambda d: saldi_proj.get(d.id, 0))

            # Top 3
            top3 = []
            for d in disponibili[:3]:
                sal_att = saldi_att.get(d.id, 0)
                sal_pro = saldi_proj.get(d.id, 0)
                # Verifica se quel giorno è libero per questo docente
                ha_lezioni_quel_giorno = OrarioDocente.query.filter_by(
                    id_docente=d.id, giorno=giorno_supplenza
                ).filter(
                    OrarioDocente.tipo_ora.in_(['lezione','potenziamento'])
                ).count() > 0
                gg_recupero = giorni_liberi_docente(d.id, escludi_giorno=giorno_supplenza) if not ha_lezioni_quel_giorno else []

                top3.append({
                    'id': d.id,
                    'cognome': d.cognome,
                    'nome': d.nome or '',
                    'saldo': sal_att,
                    'saldo_proj': sal_pro,
                    'tipo': 'debitore' if sal_pro < 0 else ('creditore' if sal_pro > 0 else 'pari'),
                    'giorno_libero': not ha_lezioni_quel_giorno,
                    'giorni_recupero': gg_recupero,
                })

            righe.append({
                'supplenza': s,
                'assente': d_ass,
                'candidati': top3,
            })

        # Creditori da liberare con permesso in quel giorno
        creditori_liberabili = []
        for d in docenti_attivi:
            sal = saldi_proj.get(d.id, 0)  # usa proiezione con sorveglianza
            if sal <= 0: continue
            if d.id in assenti_ids: continue
            # Ha lezione quel giorno?
            slots = OrarioDocente.query.filter_by(id_docente=d.id, giorno=giorno).filter(
                OrarioDocente.tipo_ora == 'lezione'
            ).all()
            if not slots: continue
            # Non è accompagnatore simulazione
            is_acc = any(d in a.accompagnatori for a in att_sim if a.data_inizio == data_sim)
            if is_acc: continue
            creditori_liberabili.append({
                'docente': d,
                'saldo_att': saldi_att.get(d.id, 0),
                'saldo': sal,  # proiezione
                'ore': sorted(set(s.ora for s in slots)),
            })
        creditori_liberabili.sort(key=lambda x: -x['saldo'])

        prospetto[data_sim] = {
            'righe': righe,
            'creditori': creditori_liberabili[:8],
        }

    return render_template('report/ottimizzazione_simulazioni.html',
        prospetto=prospetto,
        oggi=oggi,
    )


# ── PIANIFICAZIONE PERMESSI ──────────────────────────────────
@report_bp.route('/report/pianifica-permessi')
def pianifica_permessi():
    from models.orario_docente import OrarioDocente
    from models.assenza import Assenza
    from models.indisponibilita import Indisponibilita
    from collections import defaultdict
    from datetime import timedelta

    oggi = date.today()
    fine_anno = date(2026, 6, 6)

    # Saldi proiettati
    saldi_eff_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        db.func.sum(MovimentoBancaOre.minuti)
    ).filter(MovimentoBancaOre.data <= oggi).group_by(MovimentoBancaOre.id_docente).all()
    saldi_prev_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        db.func.sum(MovimentoBancaOre.minuti)
    ).filter(MovimentoBancaOre.data > oggi).group_by(MovimentoBancaOre.id_docente).all()

    saldi_eff  = {r[0]: (r[1] or 0)//60 for r in saldi_eff_raw}
    saldi_prev = {r[0]: (r[1] or 0)//60 for r in saldi_prev_raw}

    GIORNI_NOMI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']

    # Date future lavorative (esclusi festivi 1-2 giugno)
    FESTIVI = {date(2026,6,1), date(2026,6,2)}
    date_future = []
    cur = oggi + timedelta(days=1)
    while cur <= fine_anno:
        if cur.weekday() < 6 and cur not in FESTIVI:
            date_future.append(cur)
        cur += timedelta(days=1)

    # Assenze e indisponibilità future per docente+data (cache)
    ass_future = defaultdict(set)   # doc_id -> set di date con assenza
    for a in Assenza.query.filter(Assenza.data > oggi).all():
        ass_future[a.id_docente].add(a.data)
    indisp_future = defaultdict(lambda: defaultdict(set))  # doc_id -> data -> set ore
    for i in Indisponibilita.query.filter(Indisponibilita.data > oggi).all():
        indisp_future[i.id_docente][i.data].add(i.ora)
    # Supplenze già assegnate come sostituto — bloccano l'ora
    for s in Supplenza.query.filter(
        Supplenza.data > oggi,
        Supplenza.stato == 'assegnata',
        Supplenza.id_sostituto != None
    ).all():
        indisp_future[s.id_sostituto][s.data].add(s.ora)

    risultati = []
    for doc in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all():
        sal_eff  = saldi_eff.get(doc.id, 0)
        sal_prev = saldi_prev.get(doc.id, 0)
        sal_fin  = sal_eff + sal_prev
        if sal_fin < 1:
            continue

        # Orario per giorno — tutte le ore di servizio (lezione + potenziamento)
        orario = defaultdict(list)
        for s in OrarioDocente.query.filter_by(id_docente=doc.id).all():
            if (s.tipo_ora in ('lezione','potenziamento')
                    and s.classe not in ('---','-x-','',None)):
                orario[s.giorno].append(s.ora)

        opzioni = []
        for data in date_future:
            giorno = data.weekday()
            ore_base = sorted(set(orario.get(giorno, [])))
            if not ore_base:
                continue
            # Già totalmente assente quel giorno (assenza manuale)?
            if data in ass_future[doc.id]:
                continue
            # Ore bloccate = indisponibilità (simulazioni, BIM, ecc.)
            # In quelle ore NON può chiedere permesso
            ore_bloccate = indisp_future[doc.id].get(data, set())
            # Il 6 giugno le lezioni finiscono dopo la 3ª ora
            ora_max_giorno = 3 if data == date(2026, 6, 6) else 9
            # Ore richiedibili = ore di servizio NON bloccate e nei limiti della giornata
            ore_permesso = [o for o in ore_base
                            if o not in ore_bloccate and o <= ora_max_giorno]
            if not ore_permesso:
                continue

            # Sequenza finale consecutiva (per liberare fine giornata)
            seq_fine = [ore_permesso[-1]]
            for i in range(len(ore_permesso)-2, -1, -1):
                if ore_permesso[i] == ore_permesso[i+1] - 1:
                    seq_fine.insert(0, ore_permesso[i])
                else:
                    break

            # Sequenza iniziale consecutiva
            seq_inizio = [ore_permesso[0]]
            for i in range(1, len(ore_permesso)):
                if ore_permesso[i] == ore_permesso[i-1] + 1:
                    seq_inizio.append(ore_permesso[i])
                else:
                    break

            # "Valore" dell'opzione: quante ore usa vs quante ne libera
            # Fine giornata: usa N ore di permesso, libera la coda
            # Inizio giornata: usa N ore, libera la testa
            opzioni.append({
                'data':          data,
                'giorno_nome':   GIORNI_NOMI[giorno],
                'ore_totali':    [o for o in ore_base if o <= ora_max_giorno],
                'ore_permesso':  ore_permesso,
                'ore_bloccate':  [o for o in ore_bloccate if o <= ora_max_giorno],
                'fine': {
                    'da': seq_fine[0], 'a': seq_fine[-1], 'n': len(seq_fine),
                    'label': f'{seq_fine[0]}ª–{seq_fine[-1]}ª' if len(seq_fine)>1 else f'{seq_fine[0]}ª'
                },
                'inizio': {
                    'da': seq_inizio[0], 'a': seq_inizio[-1], 'n': len(seq_inizio),
                    'label': f'{seq_inizio[0]}ª–{seq_inizio[-1]}ª' if len(seq_inizio)>1 else f'{seq_inizio[0]}ª'
                },
            })

        if opzioni:
            risultati.append({
                'doc':      doc,
                'sal_fin':  sal_fin,
                'sal_eff':  sal_eff,
                'sal_prev': sal_prev,
                'opzioni':  opzioni,
            })

    risultati.sort(key=lambda x: -x['sal_fin'])

    return render_template('report/pianifica_permessi.html',
        risultati=risultati, oggi=oggi)


# ── STORICO PROSPETTI ────────────────────────────────────────
@report_bp.route('/prospetti')
def lista_prospetti():
    import glob
    prospetti_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data', 'prospetti'
    )
    os.makedirs(prospetti_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(prospetti_dir, '*.xlsx')), reverse=True)
    prospetti = []
    for f in files:
        nome = os.path.basename(f)
        size = os.path.getsize(f)
        mtime = date.fromtimestamp(os.path.getmtime(f))
        prospetti.append({'nome': nome, 'size': size, 'data': mtime})
    return render_template('report/prospetti.html',
        prospetti=prospetti, oggi=date.today())


@report_bp.route('/prospetti/scarica/<string:nome>')
def scarica_prospetto(nome):
    prospetti_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data', 'prospetti'
    )
    path = os.path.join(prospetti_dir, nome)
    if not os.path.exists(path):
        return 'File non trovato', 404
    with open(path, 'rb') as f:
        data_bytes = f.read()
    return send_file(
        io.BytesIO(data_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome
    )


@report_bp.route('/prospetti/elimina/<string:nome>', methods=['POST'])
def elimina_prospetto(nome):
    from flask import flash, redirect, url_for
    prospetti_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data', 'prospetti'
    )
    path = os.path.join(prospetti_dir, nome)
    if os.path.exists(path):
        os.remove(path)
        flash(f'Prospetto {nome} eliminato.', 'warning')
    return redirect(url_for('report.lista_prospetti'))


# ── REPORT DIRIGENTE ─────────────────────────────────────────
@report_bp.route('/report/dirigente')
def dirigente():
    docenti = Docente.query.filter_by(attivo=True).all()

    equilibrio = credito = debito = critico = 0
    tot_supplenze = tot_permessi = tot_civica = tot_pagamento = 0

    casi_critici   = []  # debito > 5h
    crediti_alti   = []  # credito > 8h

    for d in docenti:
        s = get_saldi_docente(d.id)
        lordo = s['supplenze'] - s['permessi'] - s['civica']
        netto = lordo - s['pagamento']

        tot_supplenze += s['supplenze']
        tot_permessi  += s['permessi']
        tot_civica    += s['civica']
        tot_pagamento += s['pagamento']

        if netto > 0:
            credito += 1
            if netto >= 8:
                crediti_alti.append({'docente': d, 'saldo': netto})
        elif netto < 0:
            debito += 1
            if netto <= -5:
                critico += 1
                casi_critici.append({'docente': d, 'saldo': netto})
        else:
            equilibrio += 1

    # Situazione complessiva
    perc_ok = round(equilibrio / len(docenti) * 100) if docenti else 0
    if perc_ok >= 75:
        situazione = ('EQUILIBRATA', 'verde')
    elif perc_ok >= 50:
        situazione = ('SOTTO PRESSIONE', 'giallo')
    else:
        situazione = ('CRITICA', 'rosso')

    casi_critici.sort(key=lambda x: x['saldo'])
    crediti_alti.sort(key=lambda x: -x['saldo'])

    return render_template('report/dirigente.html',
        n_docenti    = len(docenti),
        equilibrio   = equilibrio,
        credito      = credito,
        debito       = debito,
        critico      = critico,
        perc_ok      = perc_ok,
        situazione   = situazione,
        tot_supplenze= tot_supplenze,
        tot_permessi = tot_permessi,
        tot_civica   = tot_civica,
        tot_pagamento= tot_pagamento,
        casi_critici = casi_critici,
        crediti_alti = crediti_alti,
        oggi         = date.today(),
    )


# ── PROSPETTO WEB GIORNALIERO ─────────────────────────────────
@report_bp.route('/prospetto-web')
@report_bp.route('/prospetto-web/<string:data_str>')
def prospetto_web(data_str=None):
    """Prospetto HTML giornaliero con supplenze + attività istituzionali."""
    if data_str is None:
        data_str = date.today().isoformat()
    try:
        data_sel = date.fromisoformat(data_str)
    except ValueError:
        data_sel = date.today()

    supplenze = (Supplenza.query
                 .filter_by(data=data_sel)
                 .filter(Supplenza.stato != 'annullata')
                 .order_by(Supplenza.ora)
                 .all())

    try:
        from models.attivita_ist import AttivitaIst
        eventi_ist = (AttivitaIst.query
                      .filter_by(data=data_sel)
                      .order_by(AttivitaIst.ora_inizio)
                      .all())
    except Exception:
        eventi_ist = []

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
    from datetime import timedelta
    return render_template('report/prospetto_web.html',
        data_sel=data_sel,
        supplenze=supplenze,
        eventi_ist=eventi_ist,
        oggi=date.today(),
        timedelta=timedelta,
        giorno_it=GIORNI[data_sel.weekday()],
        mese_it=MESI[data_sel.month],
    )

