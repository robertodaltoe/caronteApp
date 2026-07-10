"""
Export XLSX per ogni passo dell'hub impostazione anno + export per classe.
Route: /export/<passo>?anno=2026-2027
       /export/classe/<label>?anno=2026-2027
"""
import io
from flask import Blueprint, request, send_file
from openpyxl import Workbook
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side,
                              GradientFill)
from openpyxl.utils import get_column_letter

export_bp = Blueprint('export_xlsx', __name__)

# ── Stili comuni ────────────────────────────────────────────────────
BLU   = '1e3a5f'
BLU_L = 'dbe9f6'
GRIG  = 'f3f4f6'
VERD  = '166534'
VERD_L= 'dcfce7'
ROSS  = 'dc2626'
GIAL  = 'fef9c3'

def _hdr(ws, row, cols, color=BLU, font_color='FFFFFF', bold=True, size=10):
    fill = PatternFill('solid', fgColor=color)
    font = Font(bold=bold, color=font_color, size=size, name='Arial')
    for c, val in enumerate(cols, 1):
        cell = ws.cell(row, c, val)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal='center', vertical='center',
                                    wrap_text=True)
    return row + 1

def _row(ws, row, vals, bold=False, bg=None, num_fmt=None):
    fill = PatternFill('solid', fgColor=bg) if bg else None
    for c, val in enumerate(vals, 1):
        cell = ws.cell(row, c, val)
        cell.font = Font(bold=bold, size=10, name='Arial')
        if fill:
            cell.fill = fill
        cell.alignment = Alignment(vertical='center')
        if num_fmt:
            cell.number_format = num_fmt
    return row + 1

def _border_all(ws, min_row, max_row, min_col, max_col):
    thin = Side(style='thin', color='D1D5DB')
    for r in range(min_row, max_row+1):
        for c in range(min_col, max_col+1):
            cell = ws.cell(r, c)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

def _title(ws, testo, anno):
    ws.cell(1, 1, testo).font = Font(bold=True, size=13, color=BLU, name='Arial')
    ws.cell(2, 1, f'Anno scolastico: {anno}').font = Font(size=10, color='6B7280', name='Arial')
    ws.row_dimensions[1].height = 20
    return 4  # prima riga dati

def _wb():
    wb = Workbook()
    wb.remove(wb.active)
    return wb

def _send(wb, nome):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=nome,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ══ PASSO 1 — Classi di concorso ════════════════════════════════════
def _export_p1(anno):
    from models.classe_concorso import ClasseConcorso
    wb = _wb()
    ws = wb.create_sheet('Classi di concorso')
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 45
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 10

    r = _title(ws, 'Classi di concorso', anno)
    r = _hdr(ws, r, ['Codice', 'Nome', 'Tipo', 'Attiva'])
    for cc in ClasseConcorso.query.order_by(ClasseConcorso.codice).all():
        tipo = 'ITP (B)' if cc.codice.startswith('B-') else 'Titolare (A)'
        bg = GRIG if not cc.attiva else None
        r = _row(ws, r, [cc.codice, cc.nome, tipo, 'Sì' if cc.attiva else 'No'],
                 bg=bg)
    _border_all(ws, 4, r-1, 1, 4)
    return wb


# ══ PASSO 2 — Piano di studi ════════════════════════════════════════
def _export_p2(anno, indirizzo=None):
    from models.piano_studi import PianoStudi, ClasseSezione
    from models.classe_concorso import ClasseConcorso
    from config_anno import get_anno_corrente

    wb = _wb()
    indirizzi = [indirizzo] if indirizzo else sorted({
        p.indirizzo for p in PianoStudi.query.filter_by(anno_scol=anno).all()})

    for ind in indirizzi:
        ws = wb.create_sheet(ind)
        anni_attivi = sorted({
            s.anno_corso for s in ClasseSezione.query.filter_by(
                anno_scol=anno, indirizzo=ind, attiva=True).all()})
        if not anni_attivi:
            anni_attivi = list(range(1, 6))

        # Intestazione
        r = _title(ws, f'Piano di studi — {ind}', anno)
        hdrs = ['CC', 'Materia'] + [f'{ac}° anno\n(h/sett)' for ac in anni_attivi] + \
               [f'{ac}° anno\n(h/anno×33)' for ac in anni_attivi]
        r = _hdr(ws, r, hdrs, size=9)

        # Raggruppamento per CC
        cc_ids = sorted({p.id_classe_concorso for p in
                         PianoStudi.query.filter_by(anno_scol=anno, indirizzo=ind).all()})
        for cc_id in cc_ids:
            cc = ClasseConcorso.query.get(cc_id)
            righe = PianoStudi.query.filter_by(
                anno_scol=anno, indirizzo=ind,
                id_classe_concorso=cc_id).all()
            for p in righe:
                ore_sett = [p.ore_settimanali if p.anno_corso == ac else '' for ac in anni_attivi]
                ore_ann  = [p.ore_settimanali * 33 if p.anno_corso == ac else '' for ac in anni_attivi]
                bg = GIAL if p.compresenza else None
                r = _row(ws, r,
                         [cc.codice, p.nome_materia_locale] + ore_sett + ore_ann,
                         bg=bg)

        # Totali per anno
        ws.cell(r, 2, 'TOTALE ORE SETTIMANALI').font = Font(bold=True, name='Arial', size=10)
        ws.cell(r, 2).fill = PatternFill('solid', fgColor=BLU_L)
        for i, ac in enumerate(anni_attivi):
            col = 3 + i
            righe_ac = PianoStudi.query.filter_by(
                anno_scol=anno, indirizzo=ind, anno_corso=ac, compresenza=False).all()
            tot = sum(p.ore_settimanali for p in righe_ac)
            ws.cell(r, col, tot).font = Font(bold=True, name='Arial')
            ws.cell(r, col).fill = PatternFill('solid', fgColor=BLU_L)
            ws.cell(r, 3 + len(anni_attivi) + i, tot * 33).font = Font(bold=True, name='Arial')
            ws.cell(r, 3 + len(anni_attivi) + i).fill = PatternFill('solid', fgColor=BLU_L)

        # Larghezze colonne
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 35
        for i in range(len(anni_attivi) * 2):
            ws.column_dimensions[get_column_letter(3 + i)].width = 11
        _border_all(ws, 4, r, 1, 2 + len(anni_attivi) * 2)
    return wb


# ══ PASSO 3 — Materie ↔ CC ══════════════════════════════════════════
def _export_p3(anno):
    from models.materia import Materia, Dipartimento
    from models.classe_concorso import MateriaClasseConcorso
    wb = _wb()
    ws = wb.create_sheet('Materie e CC')
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 25

    r = _title(ws, 'Materie ↔ Classi di concorso', anno)
    r = _hdr(ws, r, ['Sigla', 'Nome ministeriale', 'Nome breve', 'Alias', 'Classi di concorso'])
    for dip in Dipartimento.query.filter(Dipartimento.sigla != '—').order_by(Dipartimento.ordine).all():
        # Riga dipartimento
        ws.cell(r, 1, dip.nome).font = Font(bold=True, color='FFFFFF', name='Arial', size=10)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        ws.cell(r, 1).fill = PatternFill('solid', fgColor='374151')
        r += 1
        for m in Materia.query.filter_by(id_dipartimento=dip.id).order_by(Materia.sigla).all():
            ccs = ', '.join(mcc.classe_concorso.codice for mcc in
                           MateriaClasseConcorso.query.filter_by(id_materia=m.id).all())
            r = _row(ws, r, [m.sigla, m.nome, m.nome_breve or '', m.alias or '', ccs])
    _border_all(ws, 4, r-1, 1, 5)
    return wb


# ══ PASSO 4 — Classi attive ═════════════════════════════════════════
def _export_p4(anno):
    from models.piano_studi import ClasseSezione
    from models.aula import Aula
    wb = _wb()
    ws = wb.create_sheet('Classi attive')
    for w, col in zip([12, 10, 8, 10, 25], 'ABCDE'):
        ws.column_dimensions[col].width = w

    r = _title(ws, 'Classi attive', anno)
    r = _hdr(ws, r, ['Indirizzo', 'Anno', 'Sezione', 'Classe', 'Aula'])
    sezioni = ClasseSezione.query.filter_by(anno_scol=anno, attiva=True).order_by(
        ClasseSezione.indirizzo, ClasseSezione.anno_corso, ClasseSezione.sezione).all()
    for s in sezioni:
        lbl = f'{s.anno_corso}{s.sezione} {s.indirizzo}'
        aula = Aula.query.filter_by(anno_scol=anno, classe=lbl).first()
        r = _row(ws, r, [s.indirizzo, s.anno_corso, s.sezione, lbl,
                          f'{aula.aula} — {aula.sede}' if aula else ''])
    _border_all(ws, 4, r-1, 1, 5)
    return wb


# ══ PASSO 5 — Calcolo organico ══════════════════════════════════════
def _export_p5(anno):
    from models.piano_studi import CalcoloOrganico
    from models.classe_concorso import ClasseConcorso
    wb = _wb()
    ws = wb.create_sheet('Calcolo organico')
    for w, col in zip([14, 40, 14, 12, 12, 12], 'ABCDEF'):
        ws.column_dimensions[col].width = w

    r = _title(ws, 'Calcolo organico richiesto', anno)
    r = _hdr(ws, r, ['CC', 'Nome', 'Tipo', 'Ore tot.', 'N. docenti', 'Ore residue'])
    for calc in CalcoloOrganico.query.filter_by(anno_scol=anno).join(
            ClasseConcorso, CalcoloOrganico.id_classe_concorso == ClasseConcorso.id).order_by(
            ClasseConcorso.codice).all():
        r = _row(ws, r, [calc.classe_concorso.codice, calc.classe_concorso.nome,
                          calc.tipo_calcolato or '', calc.ore_totali_calcolate or 0,
                          calc.n_coi_calcolato or 0, calc.ore_resto_calcolato or 0])
    _border_all(ws, 4, r-1, 1, 6)
    return wb


# ══ PASSO 6 — Organico USR ══════════════════════════════════════════
def _export_p6(anno):
    from models.classe_concorso import ClasseConcorso, CattedraOrganico
    wb = _wb()
    for tipo, label in [('diritto', 'Organico di diritto'), ('fatto', 'Organico di fatto')]:
        ws = wb.create_sheet(label)
        for w, col in zip([14, 35, 8, 8, 12, 8, 12], 'ABCDEFG'):
            ws.column_dimensions[col].width = w
        r = _title(ws, label, anno)
        r = _hdr(ws, r, ['CC', 'Nome', 'COI', 'COE', 'Ore residue', 'DOC', 'Note'])
        for cat in CattedraOrganico.query.filter_by(anno_scol=anno, tipo=tipo).join(
                ClasseConcorso, CattedraOrganico.id_classe_concorso==ClasseConcorso.id).order_by(
                ClasseConcorso.codice).all():
            r = _row(ws, r, [cat.classe_concorso.codice, cat.classe_concorso.nome,
                              cat.n_coi or 0, cat.n_coe or 0, cat.ore_residue or 0,
                              cat.n_docenti or 0, cat.note or ''])
        _border_all(ws, 4, r-1, 1, 7)
    return wb


# ══ PASSO 7 — Docenti per anno ══════════════════════════════════════
def _export_p7(anno):
    from routes.impostazione_anno import _docenti_per_anno
    wb = _wb()
    ws = wb.create_sheet('Docenti')
    for w, col in zip([18, 14, 14, 12, 8, 12, 14], 'ABCDEFG'):
        ws.column_dimensions[col].width = w

    r = _title(ws, 'Docenti per anno scolastico', anno)
    r = _hdr(ws, r, ['Cognome', 'Nome', 'Tipo contratto', 'Status',
                      'Ore max', 'CC principale', 'Scuola AP'])
    for d in _docenti_per_anno(anno):
        from models.classe_concorso import ClasseConcorso
        cc = ClasseConcorso.query.get(d.id_classe_concorso) if d.id_classe_concorso else None
        status_map = {'presente': 'Presente', 'ap_entrante': 'AP Entrante',
                      'ap_uscente': 'AP Uscente', 'aspettativa': 'Aspettativa'}
        bg = GIAL if d.status_presenza in ('ap_uscente', 'aspettativa') else None
        r = _row(ws, r, [d.cognome, d.nome, d.tipo_contratto or '',
                          status_map.get(d.status_presenza or 'presente', ''),
                          d.ore_max_effettive, cc.codice if cc else '', d.scuola_ap or ''],
                 bg=bg)
    _border_all(ws, 4, r-1, 1, 7)
    return wb


# ══ PASSO 8 — Docenti ↔ CC (con confronto USR) ══════════════════════
def _export_p8(anno):
    from models.docente import Docente
    from models.classe_concorso import (ClasseConcorso, DocenteClasseConcorso,
                                         CattedraOrganico)
    wb = _wb()
    ws = wb.create_sheet('Docenti CC')
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 8
    ws.column_dimensions['D'].width = 8
    ws.column_dimensions['E'].width = 8

    r = _title(ws, 'Docenti ↔ Classi di concorso', anno)
    r = _hdr(ws, r, ['Docente', 'CC', 'TI in app', 'DOC USR', 'Scarto'])
    for cc in ClasseConcorso.query.filter_by(attiva=True).order_by(ClasseConcorso.codice).all():
        docenti_cc = (Docente.query.join(DocenteClasseConcorso,
                       DocenteClasseConcorso.id_docente == Docente.id)
                      .filter(DocenteClasseConcorso.id_classe_concorso == cc.id,
                              Docente.attivo == True)
                      .order_by(Docente.cognome).all())
        if not docenti_cc:
            continue
        cat = CattedraOrganico.query.filter_by(
            anno_scol=anno, id_classe_concorso=cc.id, tipo='fatto').first() or \
              CattedraOrganico.query.filter_by(
            anno_scol=anno, id_classe_concorso=cc.id, tipo='diritto').first()
        n_usr = cat.n_docenti if cat else 0
        n_ti  = sum(1 for d in docenti_cc if d.tipo_contratto == 'TI')
        scarto = n_ti - n_usr
        bg = VERD_L if scarto == 0 else GIAL if abs(scarto) == 1 else 'fde8e8'
        for i, d in enumerate(docenti_cc):
            r = _row(ws, r,
                     [f'{d.cognome} {d.nome}', cc.codice,
                      n_ti if i == 0 else '', n_usr if i == 0 else '',
                      scarto if i == 0 else ''],
                     bg=bg)
    _border_all(ws, 4, r-1, 1, 5)
    return wb


# ══ PASSO 9 — Assegnazioni classi ═══════════════════════════════════
def _export_p9(anno):
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
    from models.classe_concorso import ClasseConcorso
    from routes.assegnazioni import AREE
    wb = _wb()

    for area in AREE:
        ws = wb.create_sheet(area['nome'][:31].replace('/', '-').replace('*','').replace('?',''))
        r = _title(ws, f'Assegnazioni — {area["nome"]}', anno)

        for codice in area['cc']:
            from models.classe_concorso import ClasseConcorso as CC2
            cc = CC2.query.filter_by(codice=codice).first()
            if not cc:
                continue
            assegnazioni = AssegnazioneDocente.query.filter_by(
                anno_scol=anno, id_classe_concorso=cc.id).all()
            if not assegnazioni:
                continue

            # Classi con ore per questa CC
            from models.piano_studi import PianoStudi, ClasseSezione
            classi = []
            for p in PianoStudi.query.filter_by(anno_scol=anno, id_classe_concorso=cc.id,
                                                  compresenza=False).all():
                for s in ClasseSezione.query.filter_by(
                        anno_scol=anno, indirizzo=p.indirizzo,
                        anno_corso=p.anno_corso, attiva=True).all():
                    lbl = f'{p.anno_corso}{s.sezione} {p.indirizzo}'
                    if lbl not in classi:
                        classi.append(lbl)
            classi = sorted(classi)
            if not classi:
                continue

            # Header CC
            ws.cell(r, 1, f'{cc.codice} — {cc.nome}').font = Font(
                bold=True, color='FFFFFF', name='Arial', size=10)
            ws.cell(r, 1).fill = PatternFill('solid', fgColor=BLU)
            ws.merge_cells(start_row=r, start_column=1,
                            end_row=r, end_column=2+len(classi)+2)
            r += 1
            r = _hdr(ws, r, ['Docente', 'Tipo'] + classi + ['Tot.', 'Max'])

            # Piano studi
            piano = {c: 0 for c in classi}
            for p in PianoStudi.query.filter_by(anno_scol=anno, id_classe_concorso=cc.id,
                                                  compresenza=False).all():
                for s in ClasseSezione.query.filter_by(
                        anno_scol=anno, indirizzo=p.indirizzo,
                        anno_corso=p.anno_corso, attiva=True).all():
                    lbl = f'{p.anno_corso}{s.sezione} {p.indirizzo}'
                    if lbl in piano:
                        piano[lbl] += p.ore_settimanali
            r = _row(ws, r, ['Piano studi', ''] +
                     [piano.get(c, '') for c in classi] +
                     [sum(piano.values()), ''], bg=GRIG, bold=True)

            # Docenti
            for a in assegnazioni:
                ore_cl = {}
                for ac in a.classi:
                    lbl = ac.label_classe
                    ore_cl[lbl] = ore_cl.get(lbl, 0) + ac.ore
                tot = sum(ore_cl.values())
                max_ore = a.docente.ore_max_effettive if a.docente else '—'
                nome = a.display_name
                r = _row(ws, r, [nome, a.tipo or ''] +
                         [ore_cl.get(c, '') for c in classi] + [tot, max_ore])
            r += 1

        ws.column_dimensions['A'].width = 22
        ws.column_dimensions['B'].width = 10
        for i in range(30):
            ws.column_dimensions[get_column_letter(3+i)].width = 9
    return wb


# ══ PASSO 10 — Docenti ↔ Materie ════════════════════════════════════
def _export_p10(anno):
    from models.materia import DocenteMateria
    from models.docente import Docente
    from models.materia import Materia
    wb = _wb()
    ws = wb.create_sheet('Docenti Materie')
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 35

    r = _title(ws, 'Docenti ↔ Materie', anno)
    r = _hdr(ws, r, ['Docente', 'Tipo contratto', 'Materie assegnate'])
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    for d in docenti:
        materie = DocenteMateria.query.filter_by(
            id_docente=d.id, anno_scol=anno).all()
        if not materie:
            continue
        nomi = ', '.join(m.materia.nome_breve or m.materia.nome for m in materie)
        r = _row(ws, r, [f'{d.cognome} {d.nome}', d.tipo_contratto or '', nomi])
    _border_all(ws, 4, r-1, 1, 3)
    return wb


# ══ EXPORT CLASSE — docenti + materie + incarichi ═══════════════════
def _export_classe(anno, label_classe):
    """
    Per una classe (es. '1A AFM'): elenco docenti con materie e incarichi.
    """
    import re
    m = re.match(r'(\d+)([AB]?)\s+(.+)', label_classe)
    if not m:
        from flask import abort
        abort(400)
    anno_corso = int(m.group(1))
    sezione    = m.group(2) or 'A'
    indirizzo  = m.group(3).strip()

    from models.piano_studi import PianoStudi, ClasseSezione
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
    from models.incarico import IncaricaDocente, TipoIncarico
    from models.materia import Materia

    wb = _wb()
    ws = wb.create_sheet(f'{anno_corso}{sezione} {indirizzo}')
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 22

    r = _title(ws, f'Classe {anno_corso}{sezione} {indirizzo}', anno)
    r = _hdr(ws, r, ['Docente', 'Materia', 'Ore', 'Incarico nella classe'])

    # Assegnazioni docenti per questa classe
    assegnazioni_classe = AssegnazioneClasse.query.filter_by(
        indirizzo=indirizzo, anno_corso=anno_corso, sezione=sezione).join(
        AssegnazioneDocente, AssegnazioneClasse.id_assegnazione == AssegnazioneDocente.id).filter(
        AssegnazioneDocente.anno_scol == anno).all()

    # Raggruppa per docente
    from collections import defaultdict
    doc_map = defaultdict(list)
    for ac in assegnazioni_classe:
        a = ac.assegnazione
        mat = Materia.query.get(ac.id_materia) if ac.id_materia else None
        nome_mat = mat.nome_breve or mat.nome if mat else a.tipo.nome if hasattr(a, 'tipo') else '—'
        doc_map[a].append((nome_mat, ac.ore))

    # Incarichi per questa classe
    incarichi_classe = IncaricaDocente.query.filter_by(
        anno_scol=anno,
        indirizzo=indirizzo,
        anno_corso=anno_corso,
        sezione=sezione).all()
    incarichi_map = {inc.id_docente: inc.tipo.nome for inc in incarichi_classe}

    if doc_map:
        for a, materie_ore in sorted(doc_map.items(),
                                      key=lambda x: x[0].docente.cognome if x[0].docente else 'zzz'):
            nome_doc = a.display_name
            incarico = incarichi_map.get(a.id_docente, '')
            for i, (mat, ore) in enumerate(materie_ore):
                r = _row(ws, r, [nome_doc if i == 0 else '', mat, ore,
                                  incarico if i == 0 else ''])
    else:
        ws.cell(r, 1, 'Nessuna assegnazione presente per questa classe.').font = \
            Font(italic=True, color='9CA3AF', name='Arial')
        r += 1

    # Incarichi senza docente assegnato (es. coordinatore non ancora inserito)
    if incarichi_classe:
        r += 1
        ws.cell(r, 1, 'Incarichi di classe').font = Font(bold=True, color=BLU, name='Arial', size=10)
        r += 1
        r = _hdr(ws, r, ['Tipo incarico', 'Docente', '', ''], color='374151')
        for inc in incarichi_classe:
            r = _row(ws, r, [inc.tipo.nome,
                              f'{inc.docente.cognome} {inc.docente.nome}', '', ''])
    _border_all(ws, 4, r-1, 1, 4)
    return wb


# ══ ROUTE DISPATCHER ════════════════════════════════════════════════
@export_bp.route('/export/<passo>')
def export_passo(passo):
    from config_anno import get_anno_corrente
    anno = request.args.get('anno', get_anno_corrente())
    ind  = request.args.get('indirizzo')

    mapping = {
        'p1': (_export_p1,  f'classi_concorso_{anno}.xlsx',      lambda: _export_p1(anno)),
        'p2': (_export_p2,  f'piano_studi_{anno}.xlsx',           lambda: _export_p2(anno, ind)),
        'p3': (_export_p3,  f'materie_cc_{anno}.xlsx',            lambda: _export_p3(anno)),
        'p4': (_export_p4,  f'classi_attive_{anno}.xlsx',         lambda: _export_p4(anno)),
        'p5': (_export_p5,  f'calcolo_organico_{anno}.xlsx',      lambda: _export_p5(anno)),
        'p6': (_export_p6,  f'organico_usr_{anno}.xlsx',          lambda: _export_p6(anno)),
        'p7': (_export_p7,  f'docenti_{anno}.xlsx',               lambda: _export_p7(anno)),
        'p8': (_export_p8,  f'docenti_cc_{anno}.xlsx',            lambda: _export_p8(anno)),
        'p9': (_export_p9,  f'assegnazioni_{anno}.xlsx',          lambda: _export_p9(anno)),
        'p10':(_export_p10, f'docenti_materie_{anno}.xlsx',       lambda: _export_p10(anno)),
    }
    if passo not in mapping:
        from flask import abort
        abort(404)
    _, nome, fn = mapping[passo]
    wb = fn()
    return _send(wb, nome)


@export_bp.route('/export/classe/<path:label>')
def export_classe(label):
    from config_anno import get_anno_corrente
    anno = request.args.get('anno', get_anno_corrente())
    wb = _export_classe(anno, label)
    nome = f'classe_{label.replace(" ", "_")}_{anno}.xlsx'
    return _send(wb, nome)
