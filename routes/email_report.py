from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.docente import Docente
from models.movimento_banca_ore import MovimentoBancaOre
from models.supplenza import Supplenza
from routes.report import get_saldi_docente, get_storico_settimanale
from modules.xlsx_report import _build_xlsx_singolo
from modules.email_sender import invia_report_docente, test_connessione
from datetime import date
import io, os, json

email_bp = Blueprint('email', __name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'data', 'smtp_config.json')


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        'smtp_user':     'roberto.daltoe@davincichiavenna.edu.it',
        'smtp_password': '',
        'smtp_from':     'Roberto Dal Toe <roberto.daltoe@davincichiavenna.edu.it>',
    }


def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def _genera_xlsx_bytes(docente):
    """Genera i bytes del file XLSX per un docente."""
    saldi    = get_saldi_docente(docente.id)
    storico  = get_storico_settimanale(docente.id)
    netto    = saldi['supplenze'] - saldi['permessi'] - saldi['civica']
    effettivo= netto - saldi['pagamento']
    supplenze= (Supplenza.query.filter_by(id_sostituto=docente.id)
                .filter(Supplenza.stato == 'assegnata')
                .order_by(Supplenza.data).all())
    wb = _build_xlsx_singolo(docente, saldi, storico, supplenze,
                              netto, effettivo, date.today())
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PAGINA CONFIGURAZIONE EMAIL ───────────────────────────────
@email_bp.route('/email/config', methods=['GET', 'POST'])
def config():
    cfg = load_config()

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'salva':
            cfg['smtp_user']     = request.form.get('smtp_user', '').strip()
            cfg['smtp_password'] = request.form.get('smtp_password', '').strip()
            cfg['smtp_from']     = request.form.get('smtp_from', '').strip()
            save_config(cfg)
            flash('Configurazione salvata.', 'success')

        elif azione == 'test':
            cfg['smtp_user']     = request.form.get('smtp_user', '').strip()
            cfg['smtp_password'] = request.form.get('smtp_password', '').strip()
            cfg['smtp_from']     = request.form.get('smtp_from', '').strip()
            save_config(cfg)
            ok, err = test_connessione(cfg)
            if ok:
                flash('✓ Connessione riuscita — le credenziali funzionano.', 'success')
            else:
                flash(f'✗ Connessione fallita: {err}', 'error')

        return redirect(url_for('email.config'))

    # Maschera la password per la visualizzazione
    cfg_display = dict(cfg)
    if cfg_display.get('smtp_password'):
        cfg_display['smtp_password_masked'] = '●' * 16
    else:
        cfg_display['smtp_password_masked'] = ''

    return render_template('email_config.html', cfg=cfg, cfg_display=cfg_display)


# ── INVIO SINGOLO ─────────────────────────────────────────────
@email_bp.route('/email/invia/<int:id_docente>', methods=['POST'])
def invia_singolo(id_docente):
    docente = Docente.query.get_or_404(id_docente)
    cfg     = load_config()

    if not cfg.get('smtp_password'):
        flash('Configura prima le credenziali email.', 'warning')
        return redirect(url_for('email.config'))

    if not docente.email:
        flash(f'Email mancante per {docente.cognome} — aggiornala in anagrafica.', 'warning')
        return redirect(url_for('report.index'))

    xlsx_bytes = _genera_xlsx_bytes(docente)
    ok, err    = invia_report_docente(docente, xlsx_bytes, cfg)

    if ok:
        flash(f'✓ Report inviato a {docente.cognome} ({docente.email}).', 'success')
    else:
        flash(f'✗ Errore invio a {docente.cognome}: {err}', 'error')

    return redirect(url_for('report.index'))


# ── INVIO CUMULATIVO ──────────────────────────────────────────
@email_bp.route('/email/invia-tutti', methods=['POST'])
def invia_tutti():
    cfg = load_config()

    if not cfg.get('smtp_password'):
        flash('Configura prima le credenziali email.', 'warning')
        return redirect(url_for('email.config'))

    docenti = (Docente.query
               .filter_by(attivo=True)
               .filter(Docente.email.isnot(None))
               .filter(Docente.email != '')
               .order_by(Docente.cognome).all())

    inviati  = 0
    errori   = []
    senza_email = (Docente.query
                   .filter_by(attivo=True)
                   .filter(
                       (Docente.email.is_(None)) | (Docente.email == '')
                   ).count())

    for docente in docenti:
        xlsx_bytes = _genera_xlsx_bytes(docente)
        ok, err    = invia_report_docente(docente, xlsx_bytes, cfg)
        if ok:
            inviati += 1
        else:
            errori.append(f"{docente.cognome}: {err}")

    msg = f'Invio completato: {inviati} email inviate.'
    if senza_email:
        msg += f' {senza_email} docenti senza email (saltati).'
    flash(msg, 'success' if not errori else 'warning')

    if errori:
        flash('Errori: ' + ' | '.join(errori[:5]), 'error')

    return redirect(url_for('report.index'))
