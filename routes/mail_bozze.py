from flask import Blueprint, render_template, request, jsonify, send_file
from models import db
from models.docente import Docente
from models.supplenza import Supplenza
from routes.report import get_saldi_docente, get_storico_settimanale
from datetime import date
import os, subprocess, io, zipfile, email.mime.multipart, email.mime.text, email.mime.base
from email import encoders

mail_bozze_bp = Blueprint('mail_bozze', __name__)

MITTENTE   = 'roberto.daltoe@davincichiavenna.edu.it'
PDF_CACHE  = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'pdf_cache')


def _genera_pdf_bytes(docente):
    from flask import render_template as rt
    from weasyprint import HTML
    saldi       = get_saldi_docente(docente.id)
    storico     = get_storico_settimanale(docente.id)
    saldo_lordo = saldi['supplenze'] - saldi['permessi'] - saldi['civica']
    saldo_netto = saldo_lordo - saldi['pagamento']
    supplenze   = (Supplenza.query.filter_by(id_sostituto=docente.id)
                   .filter(Supplenza.stato == 'assegnata')
                   .order_by(Supplenza.data).all())
    from modules.pdf_fonts import contesto_open_sans
    html = rt('report/singolo_print.html',
        docente=docente, saldi=saldi,
        saldo_lordo=saldo_lordo, saldo_netto=saldo_netto,
        storico=storico, supplenze=supplenze, oggi=date.today(),
        **contesto_open_sans())
    return HTML(string=html).write_pdf()


def _personalizza(testo, doc):
    return (testo
        .replace('{COGNOME}', doc.cognome)
        .replace('{NOME}',    doc.nome or '')
        .replace('{EMAIL}',   doc.email or ''))


def _esc(s):
    return str(s).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')


# ── PAGINA ────────────────────────────────────────────────────
@mail_bozze_bp.route('/mail-bozze')
def index():
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    return render_template('mail_bozze.html', docenti=docenti, oggi=date.today())


# ── MAC: AppleScript + allegato ───────────────────────────────
@mail_bozze_bp.route('/mail-bozze/invia-mac', methods=['POST'])
def crea_bozze_mac():
    import sys
    if sys.platform != 'darwin':
        return {'ok': False, 'msg': 'Funzione disponibile solo su macOS (richiede Mail.app e osascript).'}, 400
    dati    = request.get_json()
    ids     = dati.get('docenti_ids', [])
    oggetto = dati.get('oggetto', '').strip()
    corpo   = dati.get('corpo', '').strip()
    if not ids:     return jsonify({'ok': False, 'msg': 'Nessun docente selezionato.'})
    if not oggetto: return jsonify({'ok': False, 'msg': 'Inserisci un oggetto.'})
    if not corpo:   return jsonify({'ok': False, 'msg': 'Inserisci il corpo del messaggio.'})

    os.makedirs(PDF_CACHE, exist_ok=True)
    risultati = []

    for doc_id in ids:
        doc = db.session.get(Docente, int(doc_id))
        if not doc:
            risultati.append({'id': doc_id, 'ok': False, 'msg': 'Non trovato'}); continue
        if not doc.email:
            risultati.append({'id': doc_id, 'ok': False, 'cognome': doc.cognome,
                               'msg': 'Email mancante'}); continue
        try:
            pdf_bytes = _genera_pdf_bytes(doc)
            pdf_path  = os.path.join(PDF_CACHE, f'DOC_{doc.cognome}.pdf')
            with open(pdf_path, 'wb') as f: f.write(pdf_bytes)

            corpo_doc = _personalizza(corpo, doc)
            e_ogg  = _esc(oggetto)
            e_corp = _esc(corpo_doc)
            e_to   = _esc(doc.email)
            e_path = _esc(pdf_path)

            args = ['osascript']
            for line in [
                'tell application "Mail"',
                'set msg to make new outgoing message',
                f'set subject of msg to "{e_ogg}"',
                f'set content of msg to "{e_corp}"',
                f'set sender of msg to "{MITTENTE}"',
                'tell msg',
                f'make new to recipient at end of to recipients with properties {{address:"{e_to}"}}',
                f'make new attachment with properties {{file name:POSIX file "{e_path}"}}',
                'end tell',
                'set visible of msg to true',
                'end tell',
            ]:
                args += ['-e', line]

            r = subprocess.run(args, capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                risultati.append({'id': doc_id, 'ok': True, 'cognome': doc.cognome, 'email': doc.email})
            else:
                risultati.append({'id': doc_id, 'ok': False, 'cognome': doc.cognome,
                                   'msg': r.stderr.strip()[:120]})
        except Exception as e:
            risultati.append({'id': doc_id, 'ok': False, 'cognome': doc.cognome, 'msg': str(e)[:120]})

    ok_n  = sum(1 for r in risultati if r.get('ok'))
    err_n = len(risultati) - ok_n
    return jsonify({'ok': True,
        'msg': f'{ok_n} bozze aperte in Mail.app.' + (f' {err_n} errori.' if err_n else ''),
        'risultati': risultati})


# ── WINDOWS/ALTRO: ZIP con .eml + PDF ─────────────────────────
@mail_bozze_bp.route('/mail-bozze/scarica-eml', methods=['POST'])
def scarica_eml():
    dati    = request.get_json()
    ids     = dati.get('docenti_ids', [])
    oggetto = dati.get('oggetto', '').strip()
    corpo   = dati.get('corpo', '').strip()
    if not ids:     return jsonify({'ok': False, 'msg': 'Nessun docente selezionato.'})
    if not oggetto: return jsonify({'ok': False, 'msg': 'Oggetto mancante.'})
    if not corpo:   return jsonify({'ok': False, 'msg': 'Corpo mancante.'})

    os.makedirs(PDF_CACHE, exist_ok=True)
    zip_buf = io.BytesIO()
    errori  = []

    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc_id in ids:
            doc = db.session.get(Docente, int(doc_id))
            if not doc or not doc.email:
                errori.append(doc.cognome if doc else str(doc_id))
                continue
            try:
                pdf_bytes = _genera_pdf_bytes(doc)
                corpo_doc = _personalizza(corpo, doc)

                # Crea .eml (MIME multipart)
                msg = email.mime.multipart.MIMEMultipart()
                msg['From']    = MITTENTE
                msg['To']      = doc.email
                msg['Subject'] = oggetto
                msg.attach(email.mime.text.MIMEText(corpo_doc, 'plain', 'utf-8'))

                # Allegato PDF
                att = email.mime.base.MIMEBase('application', 'pdf')
                att.set_payload(pdf_bytes)
                encoders.encode_base64(att)
                att.add_header('Content-Disposition', 'attachment',
                                filename=f'DOC_{doc.cognome}.pdf')
                msg.attach(att)

                zf.writestr(f'DOC_{doc.cognome}.eml', msg.as_string())
            except Exception as e:
                errori.append(f'{doc.cognome}: {str(e)[:60]}')

    zip_buf.seek(0)
    nome_zip = f'BozzeEmail_{date.today().isoformat()}.zip'
    return send_file(zip_buf, mimetype='application/zip',
                     as_attachment=True, download_name=nome_zip)


# ── WINDOWS: Genera script PowerShell ─────────────────────────
@mail_bozze_bp.route('/mail-bozze/scarica-ps1', methods=['POST'])
def scarica_ps1():
    dati    = request.get_json()
    ids     = dati.get('docenti_ids', [])
    oggetto = dati.get('oggetto', '').strip()
    corpo   = dati.get('corpo', '').strip()

    # Genera i PDF e li salva nella cache
    os.makedirs(PDF_CACHE, exist_ok=True)
    righe = [
        '# Script PowerShell — Bozze email banca ore',
        '# Esegui con: powershell -ExecutionPolicy Bypass -File questo_file.ps1',
        '# Richiede Outlook installato',
        '',
        '$Outlook = New-Object -ComObject Outlook.Application',
        '',
    ]

    for doc_id in ids:
        doc = db.session.get(Docente, int(doc_id))
        if not doc or not doc.email: continue
        try:
            pdf_bytes = _genera_pdf_bytes(doc)
            pdf_path  = os.path.join(PDF_CACHE, f'DOC_{doc.cognome}.pdf')
            with open(pdf_path, 'wb') as f: f.write(pdf_bytes)

            corpo_doc = _personalizza(corpo, doc)
            # Escape per PowerShell (apici singoli → raddoppia)
            ps_to     = doc.email.replace("'", "''")
            ps_ogg    = oggetto.replace("'", "''")
            ps_corp   = corpo_doc.replace("'", "''").replace('\n', '`n')
            ps_path   = pdf_path.replace("'", "''")

            righe += [
                f"# ── {doc.cognome} ──",
                f"$mail = $Outlook.CreateItem(0)",
                f"$mail.To = '{ps_to}'",
                f"$mail.Subject = '{ps_ogg}'",
                f"$mail.Body = '{ps_corp}'",
                f"$mail.SentOnBehalfOfName = '{MITTENTE}'",
                f"$mail.Attachments.Add('{ps_path}') | Out-Null",
                f"$mail.Display()",
                "",
            ]
        except Exception:
            continue

    script = '\n'.join(righe)
    buf = io.BytesIO(script.encode('utf-8'))
    return send_file(buf, mimetype='text/plain',
                     as_attachment=True,
                     download_name=f'BozzeEmail_{date.today().isoformat()}.ps1')
