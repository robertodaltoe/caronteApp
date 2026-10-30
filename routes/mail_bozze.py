from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, Response
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
    # l'invio del report banca ore (con testo modificabile e PDF) e' la pagina principale
    return redirect(url_for('mail_bozze.report_banca_ore'))


@mail_bozze_bp.route('/mail-bozze/bozze-locali')
def bozze_locali():
    """Vecchio metodo: bozze per Mail.app / file .eml (ripiego, non invia nulla)."""
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


# ── NOTIFICHE SUPPLENZE (email ai docenti il giorno prima) ────
@mail_bozze_bp.route('/mail-bozze/notifiche-supplenze')
def notifiche_supplenze():
    from modules import notifiche_email as ne
    try:
        giorno = date.fromisoformat(request.args.get('data', ''))
    except ValueError:
        giorno = ne.giorno_default()
    return render_template('notifiche_supplenze.html', giorno=giorno,
        proposte=ne.proposte_supplenze(giorno), modalita=ne.modalita(),
        solo_a=sorted(ne._solo_a()), risultati=None, modello=ne.modello(),
        segnaposto=ne.SEGNAPOSTO)


@mail_bozze_bp.route('/mail-bozze/notifiche-supplenze/invia', methods=['POST'])
def notifiche_supplenze_invia():
    from modules import notifiche_email as ne
    from routes.auth import log as auth_log
    try:
        giorno = date.fromisoformat(request.form.get('data', ''))
    except ValueError:
        return redirect(url_for('mail_bozze.notifiche_supplenze'))
    risultati = ne.invia_supplenze(giorno, request.form.getlist('docenti'),
                                  reinvia=request.form.get('reinvia') == '1')
    auth_log('notifiche_supplenze',
             f'{giorno.isoformat()}: ' + ', '.join(f'{n} {s}' for n, s, _ in risultati))
    return render_template('notifiche_supplenze.html', giorno=giorno,
        proposte=ne.proposte_supplenze(giorno), modalita=ne.modalita(),
        solo_a=sorted(ne._solo_a()), risultati=risultati, modello=ne.modello(),
        segnaposto=ne.SEGNAPOSTO)


@mail_bozze_bp.route('/mail-bozze/notifiche-supplenze/impostazioni', methods=['POST'])
def notifiche_supplenze_impostazioni():
    from modules import notifiche_email as ne
    from routes.auth import log as auth_log
    nuova = request.form.get('modalita', '')
    if nuova in ne.MODALITA_VALIDE:
        ne.imposta(nuova, request.form.get('solo_a', ''))
        auth_log('impostazioni_notifiche_email', f'modalita={nuova}')
    if request.form.get('torna') == 'calendario':
        return redirect(url_for('mail_bozze.calendario_docenti', mese=request.form.get('mese', '')))
    if request.form.get('torna') == 'orari':
        return redirect(url_for('mail_bozze.orari_docenti', valido_dal=request.form.get('valido_dal', '')))
    if request.form.get('torna') == 'banca_ore':
        return redirect(url_for('mail_bozze.report_banca_ore', mese=request.form.get('mese', '')))
    return redirect(url_for('mail_bozze.notifiche_supplenze',
                            data=request.form.get('data', '')))


# ── REPORT BANCA ORE via email (mensile, tutti i docenti) ─────
def _mese_da_richiesta(valore):
    from modules import notifiche_email as ne
    try:
        return date.fromisoformat((valore or '') + '-01').replace(day=1)
    except ValueError:
        return ne.primo_del_mese()


def _render_banca_ore(mese, risultati=None):
    from modules import notifiche_email as ne
    return render_template('notifiche_banca_ore.html', mese=mese,
        proposte=ne.proposte_banca_ore(mese), modalita=ne.modalita(),
        solo_a=sorted(ne._solo_a()), risultati=risultati,
        modello=ne.modello_banca_ore(), segnaposto=ne.SEGNAPOSTO_BANCA_ORE)


@mail_bozze_bp.route('/mail-bozze/report-banca-ore')
def report_banca_ore():
    return _render_banca_ore(_mese_da_richiesta(request.args.get('mese')))


@mail_bozze_bp.route('/mail-bozze/report-banca-ore/invia', methods=['POST'])
def report_banca_ore_invia():
    from modules import notifiche_email as ne
    from routes.auth import log as auth_log
    mese = _mese_da_richiesta(request.form.get('mese'))
    risultati = ne.invia_banca_ore(mese, request.form.getlist('docenti'),
                                   request.form.get('oggetto', ''), request.form.get('corpo', ''),
        reinvia=request.form.get('reinvia') == '1')
    auth_log('report_banca_ore_email',
             f'{mese.isoformat()}: ' + ', '.join(f'{n} {s}' for n, s, _ in risultati))
    return _render_banca_ore(mese, risultati)


@mail_bozze_bp.route('/mail-bozze/report-banca-ore/pdf/<int:id_docente>')
def report_banca_ore_pdf(id_docente):
    """Il PDF che verrebbe allegato alla mail del docente (per controllarlo prima di inviare)."""
    doc = Docente.query.get_or_404(id_docente)
    try:
        dati = _genera_pdf_bytes(doc)
    except Exception as e:
        return f'PDF non disponibile su questo computer ({e}).', 503
    return Response(dati, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename=Banca_ore_{doc.cognome}.pdf'})


# ── ORARIO DEI DOCENTI via email (una tantum a ogni nuova versione) ──
def _valido_dal_da_richiesta(valore):
    from modules import notifiche_email as ne
    try:
        return date.fromisoformat(valore or '')
    except ValueError:
        return ne.valido_dal_default()


def _render_orari(valido_dal, risultati=None):
    from modules import notifiche_email as ne
    return render_template('notifiche_orari.html', valido_dal=valido_dal,
        proposte=ne.proposte_orario(valido_dal), modalita=ne.modalita(),
        solo_a=sorted(ne._solo_a()), risultati=risultati,
        modello=ne.modello_orario(), segnaposto=ne.SEGNAPOSTO_ORARIO)


@mail_bozze_bp.route('/mail-bozze/orari-docenti')
def orari_docenti():
    return _render_orari(_valido_dal_da_richiesta(request.args.get('valido_dal')))


@mail_bozze_bp.route('/mail-bozze/orari-docenti/invia', methods=['POST'])
def orari_docenti_invia():
    from modules import notifiche_email as ne
    from routes.auth import log as auth_log
    valido_dal = _valido_dal_da_richiesta(request.form.get('valido_dal'))
    risultati = ne.invia_orario(valido_dal, request.form.getlist('docenti'),
                                request.form.get('oggetto', ''), request.form.get('corpo', ''),
        reinvia=request.form.get('reinvia') == '1')
    auth_log('orari_docenti_email',
             f'{valido_dal.isoformat()}: ' + ', '.join(f'{n} {s}' for n, s, _ in risultati))
    return _render_orari(valido_dal, risultati)


@mail_bozze_bp.route('/mail-bozze/orari-docenti/pdf/<int:id_docente>')
def orari_docenti_pdf(id_docente):
    """Il PDF che verrebbe allegato (per controllarlo prima di inviare)."""
    from routes.report import orario_pdf_bytes
    doc = Docente.query.get_or_404(id_docente)
    valido_dal = _valido_dal_da_richiesta(request.args.get('valido_dal'))
    try:
        dati = orario_pdf_bytes(doc, valido_dal)
    except Exception as e:
        return f'PDF non disponibile su questo computer ({e}).', 503
    return Response(dati, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename=Orario_{doc.cognome}.pdf'})


# ── CALENDARIO MENSILE DEGLI IMPEGNI via email (PDF agenda + .ics) ──
def _mese_calendario(valore):
    from modules import notifiche_email as ne
    try:
        return date.fromisoformat((valore or '') + '-01').replace(day=1)
    except ValueError:
        return ne.mese_calendario_default()


def _render_calendario(mese, risultati=None):
    from modules import notifiche_email as ne
    return render_template('notifiche_calendario.html', mese=mese,
        proposte=ne.proposte_calendario(mese), modalita=ne.modalita(),
        solo_a=sorted(ne._solo_a()), risultati=risultati,
        modello=ne.modello_calendario(), segnaposto=ne.SEGNAPOSTO_CALENDARIO)


@mail_bozze_bp.route('/mail-bozze/calendario-docenti')
def calendario_docenti():
    return _render_calendario(_mese_calendario(request.args.get('mese')))


@mail_bozze_bp.route('/mail-bozze/calendario-docenti/invia', methods=['POST'])
def calendario_docenti_invia():
    from modules import notifiche_email as ne
    from routes.auth import log as auth_log
    mese = _mese_calendario(request.form.get('mese'))
    risultati = ne.invia_calendario(mese, request.form.getlist('docenti'),
                                    request.form.get('oggetto', ''), request.form.get('corpo', ''),
        reinvia=request.form.get('reinvia') == '1')
    auth_log('calendario_docenti_email',
             f'{mese.isoformat()}: ' + ', '.join(f'{n} {s}' for n, s, _ in risultati))
    return _render_calendario(mese, risultati)


@mail_bozze_bp.route('/mail-bozze/calendario-docenti/pdf/<int:id_docente>')
def calendario_docenti_pdf(id_docente):
    """Il PDF che verrebbe allegato (per controllarlo prima di inviare)."""
    from modules.calendario_agenda import agenda_pdf_bytes
    doc = Docente.query.get_or_404(id_docente)
    mese = _mese_calendario(request.args.get('mese'))
    try:
        dati = agenda_pdf_bytes(doc, mese)
    except Exception as e:
        return f'PDF non disponibile su questo computer ({e}).', 503
    return Response(dati, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename=Impegni_{doc.cognome}.pdf'})


@mail_bozze_bp.route('/mail-bozze/calendario-docenti/ics/<int:id_docente>')
def calendario_docenti_ics(id_docente):
    from modules.calendario_agenda import ics_mese
    doc = Docente.query.get_or_404(id_docente)
    mese = _mese_calendario(request.args.get('mese'))
    return Response(ics_mese(doc, mese), mimetype='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename=Impegni_{doc.cognome}.ics'})


@mail_bozze_bp.route('/mail-bozze/notifiche-supplenze/modello', methods=['POST'])
def notifiche_supplenze_modello():
    from modules import notifiche_email as ne
    from routes.auth import log as auth_log
    ne.imposta_modello(request.form.get('saluto'), request.form.get('apertura'),
                       request.form.get('chiusura'))
    auth_log('modello_notifiche_supplenze', 'testi aggiornati')
    return redirect(url_for('mail_bozze.notifiche_supplenze', data=request.form.get('data', '')))
