from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from models import db
from models.recupero import RecuperoDocente, RecuperoGruppo, RecuperoLezione, RecuperoAlunno, RecuperoVincolo
from models.docente import Docente
from models.materia import Materia, DocenteMateria
from datetime import date, timedelta

recupero_bp = Blueprint('recupero', __name__)

ANNO = '2025-2026'
DATA_INIZIO = date(2026, 6, 18)
DATA_FINE   = date(2026, 7, 1)


# ── INDICE ────────────────────────────────────────────────────────────
@recupero_bp.route('/recupero')
def index():
    docenti_disp = (RecuperoDocente.query
                    .filter_by(anno_scol=ANNO)
                    .join(Docente)
                    .order_by(Docente.cognome)
                    .all())
    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO)
              .order_by(RecuperoGruppo.materia)
              .all())
    # Statistiche
    tot_ore = sum(g.ore_pianificate for g in gruppi)
    tot_alunni = sum(g.n_alunni or 0 for g in gruppi)

    return render_template('recupero/index.html',
        docenti_disp=docenti_disp,
        gruppi=gruppi,
        tot_ore=tot_ore,
        tot_alunni=tot_alunni,
        anno=ANNO,
    )


# ── DOCENTI DISPONIBILI ───────────────────────────────────────────────
@recupero_bp.route('/recupero/docenti', methods=['GET', 'POST'])
def docenti():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_doc = int(request.form['id_docente'])
            note   = request.form.get('note', '').strip() or None
            exists = RecuperoDocente.query.filter_by(
                id_docente=id_doc, anno_scol=ANNO).first()
            if not exists:
                db.session.add(RecuperoDocente(
                    id_docente=id_doc, anno_scol=ANNO, note=note))
                db.session.commit()
                d = Docente.query.get(id_doc)
                flash(f'{d.cognome} aggiunto ai disponibili.', 'success')
            else:
                flash('Docente già presente.', 'warning')

        elif azione == 'rimuovi':
            rid = int(request.form['id'])
            rd  = RecuperoDocente.query.get_or_404(rid)
            db.session.delete(rd)
            db.session.commit()
            flash('Docente rimosso.', 'warning')

        return redirect(url_for('recupero.docenti'))

    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())
    disp_ids = {rd.id_docente for rd in disponibili}
    tutti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    non_ancora = [d for d in tutti if d.id not in disp_ids]

    return render_template('recupero/docenti.html',
        disponibili=disponibili,
        non_ancora=non_ancora,
        anno=ANNO,
    )


# ── GRUPPI ────────────────────────────────────────────────────────────
@recupero_bp.route('/recupero/gruppi', methods=['GET', 'POST'])
def gruppi():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_recdoc   = int(request.form['id_rec_docente'])
            materia     = request.form.get('materia', '').strip()
            sigla       = request.form.get('sigla_materia', '').strip() or None
            classi      = request.form.get('classi', '').strip()
            n_alunni    = request.form.get('n_alunni', '').strip()
            note        = request.form.get('note', '').strip() or None
            max_ore       = request.form.get('max_ore', '10').strip()
            max_ore_giorno= request.form.get('max_ore_giorno', '2').strip()
            db.session.add(RecuperoGruppo(
                id_rec_docente=id_recdoc,
                materia=materia,
                sigla_materia=sigla,
                classi=classi,
                n_alunni=int(n_alunni) if n_alunni.isdigit() else None,
                max_ore=int(max_ore) if max_ore.isdigit() else 10,
                max_ore_giorno=int(max_ore_giorno) if max_ore_giorno.isdigit() else 2,
                note=note,
            ))
            db.session.commit()
            flash('Gruppo aggiunto.', 'success')

        elif azione == 'elimina':
            gid = int(request.form['id'])
            g   = RecuperoGruppo.query.get_or_404(gid)
            db.session.delete(g)
            db.session.commit()
            flash('Gruppo eliminato.', 'warning')

        return redirect(url_for('recupero.gruppi'))

    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())
    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .join(Docente, Docente.id == RecuperoDocente.id_docente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())
    materie = Materia.query.order_by(Materia.nome).all()

    return render_template('recupero/gruppi.html',
        disponibili=disponibili,
        gruppi=gruppi_list,
        materie=materie,
    )


# ── CALENDARIO ────────────────────────────────────────────────────────
@recupero_bp.route('/recupero/calendario', methods=['GET', 'POST'])
def calendario():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_gruppo  = int(request.form['id_gruppo'])
            data_str   = request.form.get('data', '')
            ora_inizio = request.form.get('ora_inizio', '')
            ora_fine   = request.form.get('ora_fine', '')
            aula       = request.form.get('aula', '').strip() or None
            note       = request.form.get('note', '').strip() or None

            g = RecuperoGruppo.query.get_or_404(id_gruppo)

            # Verifica limite ore per gruppo (configurabile)
            max_ore = g.max_ore or 10
            if g.ore_pianificate >= max_ore:
                flash(f'Gruppo {g.materia} ha già raggiunto le {max_ore} ore massime.', 'warning')
                return redirect(url_for('recupero.calendario'))

            # Verifica max 2h in un giorno per questo gruppo
            lezioni_giorno = [l for l in g.lezioni
                              if l.data == date.fromisoformat(data_str)]
            ore_giorno = sum(l.durata_ore for l in lezioni_giorno)
            try:
                h1, m1 = map(int, ora_inizio.split(':'))
                h2, m2 = map(int, ora_fine.split(':'))
                durata = (h2 * 60 + m2 - h1 * 60 - m1) / 60
            except Exception:
                durata = 0

            max_ore_giorno = g.max_ore_giorno or 2
            if ore_giorno + durata > max_ore_giorno:
                flash(f'Massimo {max_ore_giorno} ore al giorno per gruppo.', 'warning')
                return redirect(url_for('recupero.calendario'))

            # Controllo sovrapposizione alunni
            data_d = date.fromisoformat(data_str)
            def _t(s):
                try: h,m = map(int,s.split(':')); return h*60+m
                except: return 0
            ini_m, fin_m = _t(ora_inizio), _t(ora_fine)

            alunni_g = g.alunni
            conflitti_al = []
            for al in alunni_g:
                # Cerca lezioni dello stesso alunno (stesso nome+classe) in altri gruppi
                altri_gruppi_ids = [
                    ag.id for ag in RecuperoGruppo.query
                    .join(RecuperoDocente)
                    .filter(RecuperoDocente.anno_scol == ANNO)
                    .all() if ag.id != id_gruppo
                ]
                for agid in altri_gruppi_ids:
                    al2_list = RecuperoAlunno.query.filter_by(
                        id_gruppo=agid, cognome=al.cognome,
                        nome=al.nome, classe=al.classe).all()
                    if not al2_list:
                        continue
                    lezioni_ag = RecuperoLezione.query.filter_by(
                        id_gruppo=agid, data=data_d).all()
                    for ll in lezioni_ag:
                        if _t(ll.ora_inizio) < fin_m and _t(ll.ora_fine) > ini_m:
                            conflitti_al.append(
                                f'{al.cognome} {al.nome} ({al.classe}) — '
                                f'ha già lezione {ll.ora_inizio}–{ll.ora_fine}')

            if conflitti_al:
                flash('⚠ Conflitto alunni — lezione NON salvata: ' +
                      '; '.join(conflitti_al[:5]), 'danger')
                return redirect(url_for('recupero.calendario'))

            db.session.add(RecuperoLezione(
                id_gruppo=id_gruppo,
                data=data_d,
                ora_inizio=ora_inizio,
                ora_fine=ora_fine,
                aula=aula,
                note=note,
            ))
            db.session.commit()
            flash('Lezione aggiunta.', 'success')

        elif azione == 'elimina':
            lid = int(request.form['id'])
            l   = RecuperoLezione.query.get_or_404(lid)
            db.session.delete(l)
            db.session.commit()
            flash('Lezione eliminata.', 'warning')

        return redirect(url_for('recupero.calendario'))

    # Genera lista date lavorative 18/6-1/7
    date_disponibili = []
    cur = DATA_INIZIO
    while cur <= DATA_FINE:
        if cur.weekday() < 5:  # lun-ven
            date_disponibili.append(cur)
        cur += timedelta(days=1)

    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    # Organizza lezioni per data
    lezioni_per_data = {}
    for g in gruppi_list:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    return render_template('recupero/calendario.html',
        gruppi=gruppi_list,
        date_disponibili=date_disponibili,
        lezioni_per_data=lezioni_per_data,
    )


# ── CIRCOLARE ─────────────────────────────────────────────────────────
@recupero_bp.route('/recupero/circolare')
def circolare():
    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    # Organizza per data
    lezioni_per_data = {}
    for g in gruppi_list:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    date_ordinate = sorted(lezioni_per_data.keys())
    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']

    return render_template('recupero/circolare.html',
        lezioni_per_data=lezioni_per_data,
        date_ordinate=date_ordinate,
        gruppi=gruppi_list,
        GIORNI=GIORNI, MESI=MESI,
    )


# ── API: classi di un docente ─────────────────────────────────────────
@recupero_bp.route('/recupero/api/classi-docente/<int:id_docente>')
def api_classi_docente(id_docente):
    from flask import jsonify
    from models.orario_docente import OrarioDocente
    classi = sorted(set(
        r.classe for r in OrarioDocente.query.filter_by(id_docente=id_docente).all()
        if r.classe and r.classe not in ('---', '-x-', 'POTENZIAMENTO')
    ))
    return jsonify(classi)


# ── EXPORT XLSX ───────────────────────────────────────────────────────
@recupero_bp.route('/recupero/export-xlsx')
def export_xlsx():
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']

    def fmt_data(d):
        return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month]}"

    # Stili
    BLU   = PatternFill('solid', start_color='1e3a5f')
    AZZUR = PatternFill('solid', start_color='dbeafe')
    VERDE = PatternFill('solid', start_color='dcfce7')
    GRAY  = PatternFill('solid', start_color='f3f4f6')
    BOLD  = Font(bold=True)
    BOLD_W= Font(bold=True, color='FFFFFF')
    THIN  = Border(
        left=Side(style='thin', color='d1d5db'),
        right=Side(style='thin', color='d1d5db'),
        top=Side(style='thin', color='d1d5db'),
        bottom=Side(style='thin', color='d1d5db'),
    )
    CENTER = Alignment(horizontal='center', vertical='center')
    WRAP   = Alignment(wrap_text=True, vertical='center')

    wb = Workbook()

    # ── FOGLIO FAMIGLIE ───────────────────────────────────────────────
    wsF = wb.active
    wsF.title = 'Famiglie'

    wsF.append([])
    wsF['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
    wsF['A1'].font = Font(bold=True, size=13)
    wsF['A2'] = f'CALENDARIO CORSI DI RECUPERO — A.S. {ANNO}'
    wsF['A2'].font = Font(bold=True, size=11)
    wsF['A3'] = 'Periodo: 18 giugno – 1 luglio 2026'
    wsF['A3'].font = Font(italic=True, color='6b7280')
    wsF.append([])

    # Raggruppa lezioni per materia
    from collections import defaultdict
    per_materia = defaultdict(list)
    for g in gruppi_list:
        for l in g.lezioni:
            per_materia[g.materia].append((l, g))

    row = 5
    for materia in sorted(per_materia.keys()):
        lezioni = sorted(per_materia[materia], key=lambda x: (x[0].data, x[0].ora_inizio))

        # Header materia
        wsF.merge_cells(f'A{row}:E{row}')
        wsF[f'A{row}'] = materia.upper()
        wsF[f'A{row}'].font = BOLD_W
        wsF[f'A{row}'].fill = BLU
        wsF[f'A{row}'].alignment = CENTER
        row += 1

        # Header colonne
        for col, h in enumerate(['Giorno', 'Data', 'Orario', 'Durata', 'Classi'], 1):
            cell = wsF.cell(row=row, column=col, value=h)
            cell.font = BOLD
            cell.fill = AZZUR
            cell.alignment = CENTER
            cell.border = THIN
        row += 1

        for l, g in lezioni:
            vals = [
                GIORNI[l.data.weekday()],
                l.data.strftime('%d/%m/%Y'),
                f'{l.ora_inizio}–{l.ora_fine}',
                f'{l.durata_ore}h',
                g.classi,
            ]
            for col, v in enumerate(vals, 1):
                cell = wsF.cell(row=row, column=col, value=v)
                cell.border = THIN
                cell.alignment = WRAP
            row += 1

        row += 1  # spazio tra materie

    # Larghezze famiglie
    for i, w in enumerate([14, 14, 14, 8, 30], 1):
        wsF.column_dimensions[get_column_letter(i)].width = w

    # ── FOGLIO DOCENTI ────────────────────────────────────────────────
    wsD = wb.create_sheet('Docenti')

    wsD['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
    wsD['A1'].font = Font(bold=True, size=13)
    wsD['A2'] = f'CALENDARIO CORSI DI RECUPERO — A.S. {ANNO} — USO INTERNO'
    wsD['A2'].font = Font(bold=True, size=11, color='dc2626')
    wsD.append([])
    wsD.append([])

    row = 5
    for materia in sorted(per_materia.keys()):
        lezioni = sorted(per_materia[materia], key=lambda x: (x[0].data, x[0].ora_inizio))

        wsD.merge_cells(f'A{row}:G{row}')
        wsD[f'A{row}'] = materia.upper()
        wsD[f'A{row}'].font = BOLD_W
        wsD[f'A{row}'].fill = BLU
        wsD[f'A{row}'].alignment = CENTER
        row += 1

        for col, h in enumerate(['Giorno','Data','Orario','Docente','Classe','Cognome','Nome','Aula'], 1):
            cell = wsD.cell(row=row, column=col, value=h)
            cell.font = BOLD
            cell.fill = VERDE
            cell.alignment = CENTER
            cell.border = THIN
        row += 1

        for l, g in lezioni:
            doc = g.docente
            nome_doc = f'{doc.cognome} {doc.nome or ""}'.strip() if doc else '—'
            alunni_g = sorted(g.alunni, key=lambda a: (a.classe, a.cognome))
            if alunni_g:
                for i_al, al in enumerate(alunni_g):
                    # Prima riga dell'alunno: riporta tutti i dati lezione
                    # Righe successive: ripete giorno/data/orario per leggibilità
                    vals = [
                        GIORNI[l.data.weekday()],
                        l.data.strftime('%d/%m/%Y'),
                        f'{l.ora_inizio}–{l.ora_fine}',
                        nome_doc,
                        al.classe,
                        al.cognome,
                        al.nome,
                        l.aula or '—',
                    ]
                    for col, v in enumerate(vals, 1):
                        cell = wsD.cell(row=row, column=col, value=v)
                        cell.border = THIN
                        cell.alignment = WRAP
                        # Righe pari con sfondo leggero per leggibilità
                        if i_al % 2 == 1:
                            cell.fill = PatternFill('solid', start_color='f8fafc')
                    row += 1
            else:
                # Nessun alunno iscritto — mostra comunque la lezione
                vals = [
                    GIORNI[l.data.weekday()],
                    l.data.strftime('%d/%m/%Y'),
                    f'{l.ora_inizio}–{l.ora_fine}',
                    nome_doc, g.classi, '—', '—', l.aula or '—',
                ]
                for col, v in enumerate(vals, 1):
                    cell = wsD.cell(row=row, column=col, value=v)
                    cell.border = THIN
                row += 1

        row += 1

    for i, w in enumerate([12, 12, 12, 22, 10, 18, 16, 8], 1):
        wsD.column_dimensions[get_column_letter(i)].width = w

    # Salva in memoria e invia
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'corsi_recupero_{ANNO}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ── VINCOLI DOCENTE ───────────────────────────────────────────────────
@recupero_bp.route('/recupero/vincoli', methods=['GET', 'POST'])
def vincoli():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_recdoc = int(request.form['id_rec_docente'])
            giorno    = int(request.form['giorno'])
            ora_ini   = request.form.get('ora_inizio','08:00').strip()
            ora_fin   = request.form.get('ora_fine','13:00').strip()
            note      = request.form.get('note','').strip() or None
            db.session.add(RecuperoVincolo(
                id_rec_docente=id_recdoc, anno_scol=ANNO,
                giorno=giorno, ora_inizio=ora_ini,
                ora_fine=ora_fin, note=note,
            ))
            db.session.commit()
            flash('Fascia aggiunta.', 'success')

        elif azione == 'elimina':
            vid = int(request.form['id'])
            v = RecuperoVincolo.query.get_or_404(vid)
            db.session.delete(v)
            db.session.commit()
            flash('Fascia eliminata.', 'warning')

        elif azione == 'elimina_tutti':
            id_recdoc = int(request.form['id_rec_docente'])
            RecuperoVincolo.query.filter_by(id_rec_docente=id_recdoc).delete()
            db.session.commit()
            flash('Disponibilità azzerata — il sistema userà il default (tutti i giorni 08:00–13:00).', 'info')

        return redirect(url_for('recupero.vincoli'))

    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())
    GIORNI_NOMI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì']
    return render_template('recupero/vincoli.html',
        disponibili=disponibili, GIORNI=GIORNI_NOMI, enumerate=enumerate)


# ── ALUNNI: import XLSX ───────────────────────────────────────────────
@recupero_bp.route('/recupero/alunni', methods=['GET', 'POST'])
def alunni():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'import':
            f = request.files.get('file_xlsx')
            if not f:
                flash('Nessun file selezionato.', 'warning')
                return redirect(url_for('recupero.alunni'))

            import pandas as pd, io
            from models.recupero import RecuperoImport

            df = pd.read_excel(io.BytesIO(f.read()))
            df = df[df['recupero'].str.strip().str.lower() == 'corso di recupero']

            # Svuota staging precedente
            RecuperoImport.query.filter_by(anno_scol=ANNO).delete()
            db.session.commit()

            def _primo_cognome(s):
                # "MARAFFIO MANUELA CARLA" → "MARAFFIO"
                # "ATTARDO GIUSEPPE,PALERMO" → "ATTARDO"
                s = str(s).strip().upper()
                s = s.split(',')[0].strip()
                return s.split()[0] if s else ''

            def _norm_materia(s):
                # Normalizza: tronca a 100 char, uppercase
                return str(s).strip().upper()[:100]

            inseriti = 0
            for _, row in df.iterrows():
                classe   = str(row['classe']).strip().upper()
                cognome  = str(row['cognome']).strip().upper()
                nome     = str(row['nome']).strip()
                materia  = _norm_materia(row['materia'])
                doc_raw  = str(row.get('docente','')).strip()
                cogn_doc = _primo_cognome(doc_raw)
                cf       = str(row.get('codice_fisc','')).strip() or None
                email    = str(row.get('email','')).strip() or None
                if email and '@' not in email: email = None

                db.session.add(RecuperoImport(
                    anno_scol=ANNO, classe=classe,
                    cognome=cognome, nome=nome,
                    codice_fisc=cf, email=email,
                    materia_raw=str(row['materia']).strip(),
                    materia_norm=materia,
                    docente_raw=doc_raw,
                    cognome_docente=cogn_doc,
                ))
                inseriti += 1

            db.session.commit()
            flash(f'Importati {inseriti} alunni nello staging. Ora vai in "Proposte gruppi" per abbinare i docenti.', 'success')

        elif azione == 'elimina_tutti':
            from models.recupero import RecuperoImport
            RecuperoImport.query.filter_by(anno_scol=ANNO).delete()
            anno_ids = [rd.id for rd in RecuperoDocente.query.filter_by(anno_scol=ANNO).all()]
            gruppi_ids = [g.id for g in RecuperoGruppo.query.filter(RecuperoGruppo.id_rec_docente.in_(anno_ids)).all()]
            n = RecuperoAlunno.query.filter(RecuperoAlunno.id_gruppo.in_(gruppi_ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f'Eliminati {n} alunni e staging pulito.', 'warning')

        elif azione == 'elimina':
            aid = int(request.form['id'])
            a   = RecuperoAlunno.query.get_or_404(aid)
            db.session.delete(a)
            db.session.commit()

        return redirect(url_for('recupero.alunni'))

    # GET: lista alunni per gruppo
    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO)
              .order_by(RecuperoGruppo.materia)
              .all())
    tot = sum(len(g.alunni) for g in gruppi)
    return render_template('recupero/alunni.html', gruppi=gruppi, tot=tot)


# ── GENERA BOZZA CALENDARIO ───────────────────────────────────────────
@recupero_bp.route('/recupero/genera-bozza', methods=['POST'])
def genera_bozza():
    """
    Genera automaticamente una bozza di calendario che:
    - Rispetta i vincoli di disponibilità di ogni docente
    - Garantisce che nessun alunno abbia due lezioni sovrapposte
    - Rispetta max 2h/giorno per gruppo e max ore totali per gruppo
    """
    import json
    from datetime import timedelta

    # Elimina lezioni esistenti (solo bozza)
    conferma = request.form.get('conferma_elimina') == '1'
    if not conferma:
        flash('Seleziona la casella di conferma prima di generare la bozza.', 'warning')
        return redirect(url_for('recupero.calendario'))

    # Elimina tutte le lezioni dell'anno
    anno_ids = [rd.id for rd in RecuperoDocente.query.filter_by(anno_scol=ANNO).all()]
    gruppi_ids = [g.id for g in RecuperoGruppo.query.filter(
        RecuperoGruppo.id_rec_docente.in_(anno_ids)).all()]
    RecuperoLezione.query.filter(
        RecuperoLezione.id_gruppo.in_(gruppi_ids)).delete(synchronize_session=False)
    db.session.commit()

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO)
              .all())

    # Date disponibili (lun-ven, 18/6-1/7)
    date_disp = []
    cur = DATA_INIZIO
    while cur <= DATA_FINE:
        if cur.weekday() < 5:
            date_disp.append(cur)
        cur += timedelta(days=1)

    # Slot già occupati per alunno: {(cf o nome_classe): set di (data, ora_ini, ora_fine)}
    slot_alunni = {}  # chiave: (cognome, nome, classe) → set di (data, ini_min, fin_min)

    def _t(s):
        try:
            h, m = map(int, s.split(':'))
            return h * 60 + m
        except Exception:
            return 0

    def _sovrappone(d, ini, fin, occupied):
        ini_m, fin_m = _t(ini), _t(fin)
        for od, oi, of in occupied:
            if od == d and oi < fin_m and of > ini_m:
                return True
        return False

    inserite = 0
    for g in gruppi:
        # Vincoli del docente: lista di (giorno, ora_ini, ora_fine)
        vincoli_doc = g.docente_rec.vincoli  # ordinati per giorno, ora_inizio
        # Costruisci mappa giorno → [(ini, fin), ...]
        if vincoli_doc:
            slot_disponibili = {}
            for v in vincoli_doc:
                slot_disponibili.setdefault(v.giorno, []).append(
                    (v.ora_inizio, v.ora_fine))
        else:
            # Default: tutti i giorni lun-ven, 08:00-13:00
            slot_disponibili = {g: [('08:00','13:00')] for g in range(5)}

        max_ore_tot  = g.max_ore or 10
        max_ore_g    = g.max_ore_giorno or 2
        ore_pian     = 0
        ore_per_data = {}

        alunni_g = g.alunni

        for data in date_disp:
            if ore_pian >= max_ore_tot:
                break
            wd = data.weekday()
            if wd not in slot_disponibili:
                continue

            ore_oggi = ore_per_data.get(data, 0)
            if ore_oggi >= max_ore_g:
                continue

            # Prova ogni fascia disponibile per questo giorno
            for fascia_ini, fascia_fin in slot_disponibili[wd]:
                fascia_durata = (_t(fascia_fin) - _t(fascia_ini)) / 60
                if fascia_durata <= 0:
                    continue

                durata_h = min(fascia_durata, max_ore_g - ore_oggi,
                               max_ore_tot - ore_pian, 2)
                if durata_h <= 0:
                    continue

                ini = fascia_ini
                fin_m = _t(fascia_ini) + int(durata_h * 60)
                fin = f'{fin_m // 60:02d}:{fin_m % 60:02d}'

                # Verifica no sovrapposizione alunni
                conflitto = False
                for al in alunni_g:
                    key = (al.cognome, al.nome, al.classe)
                    if _sovrappone(data, ini, fin, slot_alunni.get(key, set())):
                        conflitto = True
                        break

                if conflitto:
                    continue

                db.session.add(RecuperoLezione(
                    id_gruppo=g.id, data=data,
                    ora_inizio=ini, ora_fine=fin,
                ))
                ore_pian += durata_h
                ore_per_data[data] = ore_per_data.get(data, 0) + durata_h
                inserite += 1

                for al in alunni_g:
                    key = (al.cognome, al.nome, al.classe)
                    slot_alunni.setdefault(key, set()).add((data, _t(ini), _t(fin)))
                break  # una fascia per giorno per questo gruppo

    db.session.commit()
    flash(f'Bozza generata: {inserite} lezioni inserite.', 'success')
    return redirect(url_for('recupero.calendario'))


# ── TABELLA STAGING IMPORT ────────────────────────────────────────────
# (usata da proposte e import alunni)

# ── PROPOSTE GRUPPI DA RECUPERI IMPORTATI ────────────────────────────
@recupero_bp.route('/recupero/proposte')
def proposte():
    from collections import defaultdict
    from models.recupero import RecuperoImport

    imports = RecuperoImport.query.filter_by(anno_scol=ANNO).all()
    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())

    if not imports:
        return render_template('recupero/proposte.html',
            proposte=[], disponibili=disponibili, anno=ANNO)

    per_gruppo = defaultdict(lambda: {'classi': set(), 'alunni': [], 'docente_raw': ''})
    for imp in imports:
        key = (imp.materia_norm, imp.cognome_docente)
        per_gruppo[key]['classi'].add(imp.classe)
        per_gruppo[key]['alunni'].append(imp)
        per_gruppo[key]['docente_raw'] = imp.docente_raw

    def trova_disponibile(cognome_doc):
        for rd in disponibili:
            if rd.docente.cognome.upper() in cognome_doc.upper():
                return rd
        return None

    gruppi_esistenti = {}
    for g in (RecuperoGruppo.query.join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO).all()):
        gruppi_esistenti[(g.materia.upper(), g.id_rec_docente)] = g

    proposte_list = []
    for (materia, cogn_doc), dati in sorted(per_gruppo.items()):
        rd_sug = trova_disponibile(cogn_doc)
        proposte_list.append({
            'materia':          materia,
            'docente_raw':      dati['docente_raw'],
            'cognome_doc':      cogn_doc,
            'classi':           ', '.join(sorted(dati['classi'])),
            'n_alunni':         len(dati['alunni']),
            'rd_suggerito':     rd_sug,
            'gruppo_esistente': gruppi_esistenti.get(
                (materia.upper(), rd_sug.id)) if rd_sug else None,
        })

    return render_template('recupero/proposte.html',
        proposte=proposte_list, disponibili=disponibili, anno=ANNO)


@recupero_bp.route('/recupero/proposte/crea', methods=['POST'])
def crea_da_proposta():
    from models.recupero import RecuperoImport

    materia     = request.form.get('materia','').strip()
    cognome_doc = request.form.get('cognome_doc','').strip()
    classi      = request.form.get('classi','').strip()
    id_recdoc   = int(request.form['id_rec_docente'])
    max_ore     = int(request.form.get('max_ore', 10) or 10)
    max_ore_g   = int(request.form.get('max_ore_giorno', 2) or 2)

    esistente = RecuperoGruppo.query.filter_by(
        id_rec_docente=id_recdoc, materia=materia).first()
    if esistente:
        esistente.classi = classi
        g = esistente
        flash(f'Gruppo aggiornato: {materia}.', 'info')
    else:
        g = RecuperoGruppo(
            id_rec_docente=id_recdoc, materia=materia,
            classi=classi, max_ore=max_ore, max_ore_giorno=max_ore_g,
        )
        db.session.add(g)
        db.session.flush()
        flash(f'Gruppo creato: {materia}.', 'success')

    imports = RecuperoImport.query.filter_by(
        anno_scol=ANNO, materia_norm=materia,
        cognome_docente=cognome_doc).all()

    for imp in imports:
        exists = RecuperoAlunno.query.filter_by(
            id_gruppo=g.id, cognome=imp.cognome,
            nome=imp.nome, classe=imp.classe).first()
        if not exists:
            db.session.add(RecuperoAlunno(
                id_gruppo=g.id, classe=imp.classe,
                cognome=imp.cognome, nome=imp.nome,
                codice_fisc=imp.codice_fisc, email=imp.email,
            ))

    db.session.commit()
    return redirect(url_for('recupero.proposte'))


# ── VERIFICA COPERTURA ────────────────────────────────────────────────
@recupero_bp.route('/recupero/copertura')
def copertura():
    from models.recupero import RecuperoImport
    from collections import defaultdict

    # Tutti gli alunni importati
    imports = RecuperoImport.query.filter_by(anno_scol=ANNO).order_by(
        RecuperoImport.cognome, RecuperoImport.nome,
        RecuperoImport.materia_norm).all()

    if not imports:
        return render_template('recupero/copertura.html',
            righe=[], n_ok=0, n_no=0, n_no_gruppo=0)

    # Mappa alunno+materia → gruppo → lezioni
    righe = []
    n_ok = n_no = n_no_gruppo = 0

    for imp in imports:
        # Cerca il gruppo abbinato a questa materia
        gruppo = None
        for g in (RecuperoGruppo.query.join(RecuperoDocente)
                  .filter(RecuperoDocente.anno_scol == ANNO).all()):
            if g.materia.upper() == imp.materia_norm.upper():
                classi_g = [c.strip().upper() for c in g.classi.split(',')]
                if imp.classe.upper() in classi_g:
                    gruppo = g
                    break
            # Match parziale
            if (g.materia.upper() in imp.materia_norm.upper() or
                    imp.materia_norm.upper() in g.materia.upper()):
                classi_g = [c.strip().upper() for c in g.classi.split(',')]
                if imp.classe.upper() in classi_g:
                    gruppo = g
                    break

        if not gruppo:
            stato = 'no_gruppo'
            n_no_gruppo += 1
            n_lezioni = 0
        else:
            # Verifica se l'alunno è iscritto al gruppo
            al = RecuperoAlunno.query.filter_by(
                id_gruppo=gruppo.id,
                cognome=imp.cognome, nome=imp.nome,
                classe=imp.classe).first()
            n_lezioni = len(gruppo.lezioni)
            if not al:
                stato = 'no_iscritto'
                n_no += 1
            elif n_lezioni == 0:
                stato = 'no_lezioni'
                n_no += 1
            else:
                stato = 'ok'
                n_ok += 1

        righe.append({
            'imp':      imp,
            'gruppo':   gruppo,
            'stato':    stato,
            'n_lezioni': n_lezioni,
        })

    return render_template('recupero/copertura.html',
        righe=righe, n_ok=n_ok, n_no=n_no, n_no_gruppo=n_no_gruppo)


# ══════════════════════════════════════════════════════════════════════
# PROVE DI AGOSTO
# ══════════════════════════════════════════════════════════════════════

ANNO_AGO     = '2025-2026'
PERIODO_AGO  = 'prove_agosto'
CONTRATTI_OK = ('TI', 'TD_annuale')  # contratti validi per agosto

TIPO_PROVA_LABEL = {
    'scritto':       '✏️ Scritto',
    'orale':         '🗣 Orale',
    'pratico':       '🔧 Pratico',
    'scritto_orale': '✏️🗣 Scritto + Orale',
}


def _parse_tipo_prova(s):
    """Normalizza il tipo prova dal file registro."""
    s = str(s).strip().lower()
    if 'orale' in s and 'scritt' in s:
        return 'scritto_orale'
    if 'orale' in s:
        return 'orale'
    if 'pratico' in s or 'pratica' in s:
        return 'pratico'
    return 'scritto'


@recupero_bp.route('/recupero/agosto')
def agosto_index():
    from models.recupero import RecuperoPeriodo
    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO)
              .order_by(RecuperoGruppo.materia)
              .all())

    tot_alunni  = sum(len(g.alunni) for g in gruppi)
    tot_lezioni = sum(len(g.lezioni) for g in gruppi)

    return render_template('recupero/agosto_index.html',
        periodo=periodo, gruppi=gruppi,
        tot_alunni=tot_alunni, tot_lezioni=tot_lezioni,
        anno=ANNO_AGO)


@recupero_bp.route('/recupero/agosto/proposte')
def agosto_proposte():
    """Proposte gruppi prove da recuperi importati (tutti, non solo corsi)."""
    from collections import defaultdict
    from models.recupero import RecuperoImport

    imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).all()
    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO_AGO)
                   .join(Docente).order_by(Docente.cognome).all())

    if not imports:
        return render_template('recupero/agosto_proposte.html',
            proposte=[], disponibili=[], anno=ANNO_AGO)

    per_gruppo = defaultdict(lambda: {
        'classi': set(), 'alunni': [], 'docente_raw': '',
        'tipo_prova': 'scritto'
    })
    for imp in imports:
        key = (imp.materia_norm, imp.cognome_docente)
        per_gruppo[key]['classi'].add(imp.classe)
        per_gruppo[key]['alunni'].append(imp)
        per_gruppo[key]['docente_raw'] = imp.docente_raw
        # tipo prova dal file
        if hasattr(imp, 'tipo_prova_raw') and imp.tipo_prova_raw:
            per_gruppo[key]['tipo_prova'] = _parse_tipo_prova(imp.tipo_prova_raw)

    def trova_disponibile(cognome_doc):
        for rd in disponibili:
            if rd.docente.cognome.upper() in cognome_doc.upper():
                return rd
        return None

    gruppi_esistenti = {
        (g.materia.upper(), g.id_rec_docente): g
        for g in RecuperoGruppo.query
            .join(RecuperoDocente)
            .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                    RecuperoGruppo.periodo_codice == PERIODO_AGO).all()
    }

    proposte_list = []
    for (materia, cogn_doc), dati in sorted(per_gruppo.items()):
        rd_sug = trova_disponibile(cogn_doc)
        proposte_list.append({
            'materia':          materia,
            'docente_raw':      dati['docente_raw'],
            'cognome_doc':      cogn_doc,
            'classi':           ', '.join(sorted(dati['classi'])),
            'n_alunni':         len(dati['alunni']),
            'tipo_prova':       dati['tipo_prova'],
            'rd_suggerito':     rd_sug,
            'gruppo_esistente': gruppi_esistenti.get(
                (materia.upper(), rd_sug.id)) if rd_sug else None,
        })

    return render_template('recupero/agosto_proposte.html',
        proposte=proposte_list, disponibili=disponibili,
        TIPO_PROVA_LABEL=TIPO_PROVA_LABEL, anno=ANNO_AGO)


@recupero_bp.route('/recupero/agosto/proposte/crea', methods=['POST'])
def agosto_crea_da_proposta():
    from models.recupero import RecuperoImport

    materia     = request.form.get('materia', '').strip()
    cognome_doc = request.form.get('cognome_doc', '').strip()
    classi      = request.form.get('classi', '').strip()
    id_recdoc   = int(request.form['id_rec_docente'])
    tipo_prova  = request.form.get('tipo_prova', 'scritto')
    durata_ore  = float(request.form.get('durata_ore', 2.0) or 2.0)

    esistente = RecuperoGruppo.query.filter_by(
        id_rec_docente=id_recdoc, materia=materia,
        periodo_codice=PERIODO_AGO).first()

    if esistente:
        esistente.classi     = classi
        esistente.tipo_prova = tipo_prova
        esistente.durata_ore = durata_ore
        g = esistente
        flash(f'Gruppo aggiornato: {materia}.', 'info')
    else:
        g = RecuperoGruppo(
            id_rec_docente=id_recdoc, materia=materia,
            classi=classi, periodo_codice=PERIODO_AGO,
            tipo_prova=tipo_prova, durata_ore=durata_ore,
            max_ore=durata_ore, max_ore_giorno=durata_ore,
        )
        db.session.add(g)
        db.session.flush()
        flash(f'Gruppo creato: {materia}.', 'success')

    # Collega alunni — tutti (non solo corso di recupero)
    imports = RecuperoImport.query.filter_by(
        anno_scol=ANNO_AGO, materia_norm=materia,
        cognome_docente=cognome_doc).all()

    for imp in imports:
        exists = RecuperoAlunno.query.filter_by(
            id_gruppo=g.id, cognome=imp.cognome,
            nome=imp.nome, classe=imp.classe).first()
        if not exists:
            db.session.add(RecuperoAlunno(
                id_gruppo=g.id, classe=imp.classe,
                cognome=imp.cognome, nome=imp.nome,
                codice_fisc=imp.codice_fisc, email=imp.email,
            ))

    db.session.commit()
    return redirect(url_for('recupero.agosto_proposte'))


@recupero_bp.route('/recupero/agosto/calendario', methods=['GET', 'POST'])
def agosto_calendario():
    from models.recupero import RecuperoPeriodo
    from datetime import timedelta

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_gruppo  = int(request.form['id_gruppo'])
            data_str   = request.form.get('data', '')
            ora_inizio = request.form.get('ora_inizio', '08:00')
            ora_fine   = request.form.get('ora_fine', '10:00')
            id_comm    = request.form.get('id_commissario') or None
            aula       = request.form.get('aula', '').strip() or None

            g = RecuperoGruppo.query.get_or_404(id_gruppo)
            data_d = date.fromisoformat(data_str)

            def _t(s):
                try: h,m = map(int,s.split(':')); return h*60+m
                except: return 0

            ini_m, fin_m = _t(ora_inizio), _t(ora_fine)

            # Controllo sovrapposizione alunni
            conflitti_al = []
            altri_ids = [ag.id for ag in RecuperoGruppo.query
                .join(RecuperoDocente)
                .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                        RecuperoGruppo.periodo_codice == PERIODO_AGO)
                .all() if ag.id != id_gruppo]
            for agid in altri_ids:
                lezioni_ag = RecuperoLezione.query.filter_by(
                    id_gruppo=agid, data=data_d).all()
                for ll in lezioni_ag:
                    if _t(ll.ora_inizio) < fin_m and _t(ll.ora_fine) > ini_m:
                        alunni_comuni = RecuperoAlunno.query.filter_by(id_gruppo=id_gruppo).filter(
                            RecuperoAlunno.cognome.in_(
                                [a.cognome for a in RecuperoAlunno.query.filter_by(id_gruppo=agid).all()]
                            )).all()
                        for al in alunni_comuni:
                            conflitti_al.append(f'{al.cognome} {al.nome}')

            if conflitti_al:
                flash(f'⚠ Conflitto alunni: ' + '; '.join(set(conflitti_al[:5])), 'danger')
                return redirect(url_for('recupero.agosto_calendario'))

            # Aggiorna commissario sul gruppo
            if id_comm:
                g.id_commissario = int(id_comm)

            db.session.add(RecuperoLezione(
                id_gruppo=id_gruppo, data=data_d,
                ora_inizio=ora_inizio, ora_fine=ora_fine, aula=aula,
            ))
            db.session.commit()
            flash('Prova aggiunta.', 'success')

        elif azione == 'elimina':
            lid = int(request.form['id'])
            l = RecuperoLezione.query.get_or_404(lid)
            db.session.delete(l)
            db.session.commit()

        elif azione == 'genera_bozza':
            if request.form.get('conferma_elimina') != '1':
                flash('Seleziona la casella di conferma.', 'warning')
                return redirect(url_for('recupero.agosto_calendario'))
            _genera_bozza_agosto()
            flash('Bozza prove agosto generata.', 'success')

        return redirect(url_for('recupero.agosto_calendario'))

    # Date disponibili
    date_disp = []
    if periodo:
        cur = periodo.data_inizio
        while cur <= periodo.data_fine:
            if cur.weekday() < 5:
                date_disp.append(cur)
            cur += timedelta(days=1)

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO)
              .order_by(RecuperoGruppo.materia).all())

    lezioni_per_data = {}
    for g in gruppi:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    # Docenti validi per commissario
    commissari_validi = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK)
    ).order_by(Docente.cognome).all()

    return render_template('recupero/agosto_calendario.html',
        periodo=periodo, gruppi=gruppi,
        date_disponibili=date_disp,
        lezioni_per_data=lezioni_per_data,
        commissari_validi=commissari_validi,
        TIPO_PROVA_LABEL=TIPO_PROVA_LABEL)


def _genera_bozza_agosto():
    """Genera bozza calendario prove agosto."""
    from datetime import timedelta
    from models.recupero import RecuperoPeriodo

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()
    if not periodo:
        return

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO).all())

    # Elimina lezioni esistenti
    for g in gruppi:
        RecuperoLezione.query.filter_by(id_gruppo=g.id).delete()
    db.session.commit()

    # Date: 24-27 agosto per scritti, 28 per orali
    date_scritti = []
    date_orali   = []
    cur = periodo.data_inizio
    while cur <= periodo.data_fine:
        if cur.weekday() < 5:
            if cur == periodo.data_fine:
                date_orali.append(cur)
            else:
                date_scritti.append(cur)
        cur += timedelta(days=1)

    def _t(s):
        try: h,m = map(int,s.split(':')); return h*60+m
        except: return 0

    # Slot occupati: {data: [(ini_min, fin_min, id_gruppo)]}
    slot_per_data = {}
    # Slot alunni: {(cogn, nome, classe): set di (data, ini, fin)}
    slot_alunni = {}

    def _libero_per_alunni(data, ini, fin, g):
        ini_m, fin_m = _t(ini), _t(fin)
        for al in g.alunni:
            key = (al.cognome, al.nome, al.classe)
            for od, oi, of in slot_alunni.get(key, set()):
                if od == data and oi < fin_m and of > ini_m:
                    return False
        return True

    for g in sorted(gruppi, key=lambda x: x.materia):
        tipo = g.tipo_prova or 'scritto'
        durata_h = g.durata_ore or 2.0
        durata_m = int(durata_h * 60)

        # Scegli pool date
        date_pool = date_orali if tipo == 'orale' else date_scritti

        # Ora di inizio: parto da 08:00 e cerco slot libero
        ora_ini_base_m = _t(periodo.ora_inizio)
        ora_fin_max_m  = _t(periodo.ora_fine)

        assegnata = False
        for data in date_pool:
            # Cerca primo slot libero nella giornata
            occupati = slot_per_data.get(data, [])
            occupati_sorted = sorted(occupati, key=lambda x: x[0])

            ini_m = ora_ini_base_m
            while ini_m + durata_m <= ora_fin_max_m:
                fin_m = ini_m + durata_m
                # Conflitto con altri gruppi stessa data?
                sovr = any(oi < fin_m and of > ini_m
                           for oi, of, _ in occupati_sorted)
                if sovr:
                    ini_m = max(of for oi, of, _ in occupati_sorted if of > ini_m)
                    continue
                # Conflitto alunni?
                ini_s = f'{ini_m//60:02d}:{ini_m%60:02d}'
                fin_s = f'{fin_m//60:02d}:{fin_m%60:02d}'
                if not _libero_per_alunni(data, ini_s, fin_s, g):
                    ini_m += 30
                    continue

                # Slot trovato
                db.session.add(RecuperoLezione(
                    id_gruppo=g.id, data=data,
                    ora_inizio=ini_s, ora_fine=fin_s,
                ))
                slot_per_data.setdefault(data, []).append((ini_m, fin_m, g.id))
                for al in g.alunni:
                    key = (al.cognome, al.nome, al.classe)
                    slot_alunni.setdefault(key, set()).add((data, ini_m, fin_m))

                # Proponi commissario: docente TI/TD_annuale libero in quel slot
                commissario = _suggerisci_commissario(g, data, ini_s, fin_s)
                if commissario:
                    g.id_commissario = commissario.id

                assegnata = True
                break

            if assegnata:
                break

    db.session.commit()


def _suggerisci_commissario(gruppo, data, ora_ini, ora_fine):
    """Propone un commissario libero (TI/TD_annuale) per la prova."""
    titolare_id = gruppo.docente_rec.id_docente if gruppo.docente_rec else None

    candidati = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK),
        Docente.id != titolare_id,
    ).all()

    def _t(s):
        try: h,m = map(int,s.split(':')); return h*60+m
        except: return 0

    ini_m, fin_m = _t(ora_ini), _t(ora_fine)

    for d in candidati:
        # Non già impegnato come commissario in quel giorno/ora
        impegnato = False
        for g2 in (RecuperoGruppo.query
                   .filter_by(id_commissario=d.id,
                               periodo_codice=PERIODO_AGO).all()):
            for l in g2.lezioni:
                if l.data == data and _t(l.ora_inizio) < fin_m and _t(l.ora_fine) > ini_m:
                    impegnato = True
                    break
        if not impegnato:
            return d
    return None


@recupero_bp.route('/recupero/agosto/commissario', methods=['POST'])
def agosto_set_commissario():
    """Aggiorna il commissario di un gruppo."""
    id_gruppo    = int(request.form['id_gruppo'])
    id_comm      = request.form.get('id_commissario') or None
    g = RecuperoGruppo.query.get_or_404(id_gruppo)
    g.id_commissario = int(id_comm) if id_comm else None
    db.session.commit()
    flash('Commissario aggiornato.', 'success')
    return redirect(url_for('recupero.agosto_calendario'))


# ── COPERTURA AGOSTO ──────────────────────────────────────────────────
@recupero_bp.route('/recupero/agosto/copertura')
def agosto_copertura():
    from models.recupero import RecuperoImport
    from collections import defaultdict

    # Tutti gli alunni importati (non filtrati per tipo recupero)
    imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).all()
    gruppi  = (RecuperoGruppo.query.join(RecuperoDocente)
               .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                       RecuperoGruppo.periodo_codice == PERIODO_AGO).all())

    # Mappa materia+classe → gruppo
    mappa_gruppi = {}
    for g in gruppi:
        for cls in [c.strip().upper() for c in g.classi.split(',')]:
            mappa_gruppi[(g.materia.upper(), cls)] = g

    righe = []
    n_ok = n_no = n_no_gruppo = 0

    for imp in imports:
        gruppo = mappa_gruppi.get((imp.materia_norm.upper(), imp.classe.upper()))
        if not gruppo:
            # match parziale materia
            for (mat, cls), g in mappa_gruppi.items():
                if (mat in imp.materia_norm.upper() or imp.materia_norm.upper() in mat) \
                        and cls == imp.classe.upper():
                    gruppo = g
                    break

        if not gruppo:
            stato = 'no_gruppo'; n_no_gruppo += 1; n_lezioni = 0
        else:
            n_lezioni = len(gruppo.lezioni)
            al = RecuperoAlunno.query.filter_by(
                id_gruppo=gruppo.id, cognome=imp.cognome,
                nome=imp.nome, classe=imp.classe).first()
            if not al:
                stato = 'no_iscritto'; n_no += 1
            elif n_lezioni == 0:
                stato = 'no_lezioni'; n_no += 1
            else:
                stato = 'ok'; n_ok += 1

        righe.append({'imp': imp, 'gruppo': gruppo,
                      'stato': stato, 'n_lezioni': n_lezioni})

    return render_template('recupero/copertura.html',
        righe=righe, n_ok=n_ok, n_no=n_no, n_no_gruppo=n_no_gruppo,
        titolo='Verifica copertura prove agosto',
        back_url=url_for('recupero.agosto_index'))


# ── EXPORT XLSX AGOSTO ────────────────────────────────────────────────
@recupero_bp.route('/recupero/agosto/export-xlsx')
def agosto_export_xlsx():
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    gruppi = (RecuperoGruppo.query.join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO)
              .order_by(RecuperoGruppo.materia).all())

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
    TIPO_LABEL = {'scritto':'Scritto','orale':'Orale',
                  'pratico':'Pratico','scritto_orale':'Scritto+Orale'}

    BLU   = PatternFill('solid', start_color='1e3a5f')
    AZZUR = PatternFill('solid', start_color='dbeafe')
    VERDE = PatternFill('solid', start_color='dcfce7')
    BOLD  = Font(bold=True)
    BOLD_W= Font(bold=True, color='FFFFFF')
    THIN  = Border(left=Side(style='thin',color='d1d5db'),
                   right=Side(style='thin',color='d1d5db'),
                   top=Side(style='thin',color='d1d5db'),
                   bottom=Side(style='thin',color='d1d5db'))
    CENTER = Alignment(horizontal='center', vertical='center')
    WRAP   = Alignment(wrap_text=True, vertical='center')

    wb = Workbook()
    ws_fam = wb.active
    ws_fam.title = 'Famiglie'
    ws_doc = wb.create_sheet('Docenti')

    def sheet_header(ws, titolo, interno=False):
        ws['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
        ws['A1'].font = Font(bold=True, size=13)
        ws['A2'] = f'CALENDARIO PROVE DI RECUPERO — A.S. {ANNO_AGO}'
        ws['A2'].font = Font(bold=True, size=11,
                             color='dc2626' if interno else '000000')
        ws.append([])
        ws.append([])

    sheet_header(ws_fam)
    sheet_header(ws_doc, interno=True)

    for g in gruppi:
        lezioni = sorted(g.lezioni, key=lambda l: (l.data, l.ora_inizio))
        if not lezioni:
            continue

        doc = g.docente
        nome_doc = f'{doc.cognome} {doc.nome or ""}'.strip() if doc else '—'
        comm = g.commissario
        nome_comm = f'{comm.cognome} {comm.nome or ""}'.strip() if comm else '—'
        tipo_str = TIPO_LABEL.get(g.tipo_prova or 'scritto', '—')

        # ── Foglio Famiglie: una riga per prova ──────────────────────
        # Header materia
        row_f = ws_fam.max_row + 1
        ws_fam.merge_cells(f'A{row_f}:E{row_f}')
        ws_fam[f'A{row_f}'] = f'{g.materia.upper()} — {tipo_str}'
        ws_fam[f'A{row_f}'].font = BOLD_W
        ws_fam[f'A{row_f}'].fill = BLU
        ws_fam[f'A{row_f}'].alignment = CENTER
        row_f += 1
        for col, h in enumerate(['Giorno','Data','Orario','Durata','Classi'], 1):
            c = ws_fam.cell(row=row_f, column=col, value=h)
            c.font = BOLD; c.fill = AZZUR; c.alignment = CENTER; c.border = THIN
        row_f += 1
        for l in lezioni:
            vals = [GIORNI[l.data.weekday()], l.data.strftime('%d/%m/%Y'),
                    f'{l.ora_inizio}–{l.ora_fine}', f'{l.durata_ore}h', g.classi]
            for col, v in enumerate(vals, 1):
                c = ws_fam.cell(row=row_f, column=col, value=v)
                c.border = THIN; c.alignment = WRAP
            row_f += 1
        ws_fam.append([])  # spazio

        # ── Foglio Docenti: una riga per alunno per prova ────────────
        row_d = ws_doc.max_row + 1
        ws_doc.merge_cells(f'A{row_d}:H{row_d}')
        ws_doc[f'A{row_d}'] = f'{g.materia.upper()} — {tipo_str} — Titolare: {nome_doc} — Commissario: {nome_comm}'
        ws_doc[f'A{row_d}'].font = BOLD_W
        ws_doc[f'A{row_d}'].fill = BLU
        ws_doc[f'A{row_d}'].alignment = CENTER
        row_d += 1
        for col, h in enumerate(['Giorno','Data','Orario','Titolare','Commissario','Classe','Cognome','Nome'], 1):
            c = ws_doc.cell(row=row_d, column=col, value=h)
            c.font = BOLD; c.fill = VERDE; c.alignment = CENTER; c.border = THIN
        row_d += 1
        for l in lezioni:
            alunni_g = sorted(g.alunni, key=lambda a: (a.classe, a.cognome))
            for i_al, al in enumerate(alunni_g):
                vals = [GIORNI[l.data.weekday()], l.data.strftime('%d/%m/%Y'),
                        f'{l.ora_inizio}–{l.ora_fine}', nome_doc, nome_comm,
                        al.classe, al.cognome, al.nome]
                for col, v in enumerate(vals, 1):
                    c = ws_doc.cell(row=row_d, column=col, value=v)
                    c.border = THIN; c.alignment = WRAP
                    if i_al % 2 == 1:
                        c.fill = PatternFill('solid', start_color='f8fafc')
                row_d += 1
        ws_doc.append([])

    # Larghezze
    for i, w in enumerate([12,12,12,28,12], 1):
        ws_fam.column_dimensions[get_column_letter(i)].width = w
    for i, w in enumerate([12,12,12,22,22,10,18,16], 1):
        ws_doc.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'prove_recupero_agosto_{ANNO_AGO}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
