from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, g)
from functools import wraps
from datetime import datetime, timedelta
from models import db
from models.utente import Utente, RUOLI, PERMESSI
from models.log_accesso import LogAccesso

auth_bp = Blueprint('auth', __name__)


# ── Rate limiting login (in memoria, per processo) ──────────────
# Blocca temporaneamente i tentativi di login dopo troppi fallimenti
# consecutivi sulla stessa coppia IP+username. Protezione semplice
# contro bruteforce sul PIN, senza dipendenze esterne.
_LOGIN_ATTEMPTS = {}          # {(ip, username): [timestamp, ...]}
LOGIN_MAX_TENTATIVI = 5
LOGIN_FINESTRA_SECONDI = 15 * 60   # 15 minuti
LOGIN_BLOCCO_SECONDI = 15 * 60     # 15 minuti di blocco una volta superata la soglia


def _login_chiave(ip, username):
    return (ip or '?', username or '')


def _login_bloccato(ip, username):
    """Ritorna i secondi residui di blocco, o 0 se non bloccato."""
    from time import time
    chiave = _login_chiave(ip, username)
    tentativi = _LOGIN_ATTEMPTS.get(chiave, [])
    ora = time()
    tentativi = [t for t in tentativi if ora - t < LOGIN_FINESTRA_SECONDI]
    _LOGIN_ATTEMPTS[chiave] = tentativi
    if len(tentativi) >= LOGIN_MAX_TENTATIVI:
        residuo = LOGIN_BLOCCO_SECONDI - (ora - tentativi[-1])
        if residuo > 0:
            return int(residuo)
    return 0


def _login_registra_fallimento(ip, username):
    from time import time
    chiave = _login_chiave(ip, username)
    _LOGIN_ATTEMPTS.setdefault(chiave, []).append(time())


def _login_reset(ip, username):
    _LOGIN_ATTEMPTS.pop(_login_chiave(ip, username), None)


# ── Helpers ──────────────────────────────────────────────────

def get_utente_corrente():
    uid = session.get('utente_id')
    if uid:
        return db.session.get(Utente, uid)
    return None


def log(azione, dettaglio='', esito='ok'):
    """Registra un'azione nel log accessi."""
    u = get_utente_corrente()
    entry = LogAccesso(
        id_utente     = u.id if u else None,
        username      = u.username if u else 'anonimo',
        nome_completo = u.nome_completo if u else '',
        ruolo         = u.ruolo if u else '—',
        azione        = azione,
        dettaglio     = dettaglio[:300] if dettaglio else '',
        ip            = request.remote_addr,
        esito         = esito,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def login_required(permesso=None):
    """Decorator: richiede login e opzionalmente un permesso specifico."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            u = get_utente_corrente()
            if not u or not u.attivo:
                session.clear()
                return redirect(url_for('auth.login', next=request.url))
            if permesso and not u.ha_permesso(permesso):
                log('accesso_negato', f'{request.endpoint} — {permesso}', esito='denied')
                flash('Non hai i permessi per accedere a questa sezione.', 'error')
                return redirect(url_for('dashboard.index'))
            g.utente = u
            return f(*args, **kwargs)
        return wrapper
    return decorator


def _init_utenti_default():
    """Crea gli utenti di default se non esistono."""
    if Utente.query.count() == 0:
        default = [
            ('ds',           'Dirigente Scolastico', 'ds',           '1234'),
            ('dsga',         'DSGA',                 'dsga',         '5678'),
            ('collaboratore','Collaboratore DS',      'collaboratore','2468'),
            ('segreteria',   'Segreteria Personale',  'segreteria',   '0000'),
        ]
        for username, nome, ruolo, pin in default:
            u = Utente(username=username, nome=nome, ruolo=ruolo)
            u.set_pin(pin)
            db.session.add(u)
        db.session.commit()


# ── Routes ───────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    _init_utenti_default()
    next_url = request.args.get('next') or url_for('dashboard.index')
    error = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        pin      = request.form.get('pin', '').strip()
        ip       = request.remote_addr

        residuo = _login_bloccato(ip, username)
        if residuo:
            minuti = max(1, residuo // 60)
            log('login_bloccato', f'username={username}', esito='denied')
            error = f'Troppi tentativi falliti. Riprova tra circa {minuti} minuti.'
            return render_template('login.html', error=error, next=next_url)

        u = Utente.query.filter_by(username=username, attivo=True).first()

        if u and u.check_pin(pin):
            _login_reset(ip, username)
            session.clear()
            session['utente_id'] = u.id
            session['ruolo']     = u.ruolo
            session.permanent    = True
            u.ultimo_accesso     = datetime.utcnow()
            db.session.commit()
            log('login', f'{u.nome_completo} ({u.username}) da {request.remote_addr}')
            # GDPR: pulisci log vecchi ad ogni login
            try: pulisci_log_vecchi()
            except Exception: pass
            return redirect(next_url)
        else:
            _login_registra_fallimento(ip, username)
            log('login_fallito', f'username={username}', esito='denied')
            error = 'Credenziali non corrette.'

    return render_template('login.html', error=error, next=next_url)


@auth_bp.route('/logout')
def logout():
    log('logout')
    session.clear()
    flash('Sessione terminata.', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.route('/utenti')
@login_required('gestione_utenti')
def lista_utenti():
    log('visualizza_utenti')
    utenti = Utente.query.order_by(Utente.ruolo, Utente.username).all()
    return render_template('utenti/lista.html', utenti=utenti, ruoli=RUOLI)


@auth_bp.route('/utenti/nuovo', methods=['GET', 'POST'])
@login_required('gestione_utenti')
def nuovo_utente():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        cognome  = request.form.get('cognome', '').strip().title()
        nome     = request.form.get('nome', '').strip().title()
        ruolo    = request.form.get('ruolo', 'segreteria')
        pin      = request.form.get('pin', '').strip()

        if Utente.query.filter_by(username=username).first():
            flash('Username già esistente.', 'error')
        elif len(pin) < 4:
            flash('Il PIN deve essere di almeno 4 cifre.', 'error')
        elif not cognome:
            flash('Il cognome è obbligatorio.', 'error')
        else:
            u = Utente(username=username, cognome=cognome, nome=nome, ruolo=ruolo)
            u.set_pin(pin)
            db.session.add(u)
            db.session.commit()
            log('crea_utente', f'{cognome} {nome} ({username}) ruolo={ruolo}')
            flash(f'Utente {cognome} {nome} creato.', 'success')
            return redirect(url_for('auth.lista_utenti'))

    return render_template('utenti/form.html', utente=None, ruoli=RUOLI)


@auth_bp.route('/utenti/<int:id>/modifica', methods=['GET', 'POST'])
@login_required('gestione_utenti')
def modifica_utente(id):
    u = Utente.query.get_or_404(id)
    if request.method == 'POST':
        u.cognome = request.form.get('cognome', '').strip().title()
        u.nome    = request.form.get('nome', '').strip().title()
        u.ruolo   = request.form.get('ruolo', u.ruolo)
        u.attivo = 'attivo' in request.form
        pin_nuovo = request.form.get('pin_nuovo', '').strip()
        if pin_nuovo:
            if len(pin_nuovo) < 4:
                flash('Il PIN deve essere di almeno 4 cifre.', 'error')
                return render_template('utenti/form.html', utente=u, ruoli=RUOLI)
            u.set_pin(pin_nuovo)
            flash('PIN aggiornato.', 'success')
        db.session.commit()
        log('modifica_utente', f'{u.nome_completo} ({u.username})')
        flash(f'Utente {u.username} aggiornato.', 'success')
        return redirect(url_for('auth.lista_utenti'))
    return render_template('utenti/form.html', utente=u, ruoli=RUOLI)


@auth_bp.route('/utenti/<int:id>/elimina', methods=['POST'])
@login_required('gestione_utenti')
def elimina_utente(id):
    u = Utente.query.get_or_404(id)
    if u.id == session.get('utente_id'):
        flash('Non puoi eliminare il tuo stesso account.', 'error')
        return redirect(url_for('auth.lista_utenti'))
    username = u.username
    db.session.delete(u)
    db.session.commit()
    log('elimina_utente', f'username={username}')
    flash(f'Utente {username} eliminato.', 'warning')
    return redirect(url_for('auth.lista_utenti'))


@auth_bp.route('/cambia-pin', methods=['GET', 'POST'])
@login_required()
def cambia_pin():
    u = get_utente_corrente()
    if request.method == 'POST':
        pin_attuale  = request.form.get('pin_attuale', '').strip()
        pin_nuovo    = request.form.get('pin_nuovo', '').strip()
        pin_conferma = request.form.get('pin_conferma', '').strip()

        if not u.check_pin(pin_attuale):
            flash('PIN attuale non corretto.', 'error')
        elif len(pin_nuovo) < 4:
            flash('Il PIN deve essere di almeno 4 cifre.', 'error')
        elif pin_nuovo != pin_conferma:
            flash('I due PIN non coincidono.', 'error')
        else:
            u.set_pin(pin_nuovo)
            db.session.commit()
            log('cambia_pin')
            flash('PIN aggiornato.', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('cambia_pin.html', utente=u)


@auth_bp.route('/log-accessi')
@login_required('gestione_utenti')
def log_accessi():
    log('visualizza_log')

    q         = request.args.get('q', '').strip()
    azione_f  = request.args.get('azione', '').strip()
    username_f = request.args.get('username', '').strip()
    data_da   = request.args.get('data_da', '').strip()
    data_a    = request.args.get('data_a', '').strip()

    query = LogAccesso.query
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(
            LogAccesso.azione.ilike(like),
            LogAccesso.dettaglio.ilike(like),
        ))
    if azione_f:
        query = query.filter(LogAccesso.azione == azione_f)
    if username_f:
        query = query.filter(LogAccesso.username == username_f)
    if data_da:
        try:
            query = query.filter(LogAccesso.timestamp >= datetime.fromisoformat(data_da))
        except ValueError:
            pass
    if data_a:
        try:
            # fino alla fine del giorno indicato
            query = query.filter(LogAccesso.timestamp < datetime.fromisoformat(data_a) + timedelta(days=1))
        except ValueError:
            pass

    logs = query.order_by(LogAccesso.timestamp.desc()).limit(300).all()

    # Valori distinti per i menu a tendina dei filtri (indipendenti dal
    # filtro corrente, calcolati sull'intera tabella).
    azioni_disponibili = sorted({r[0] for r in
        db.session.query(LogAccesso.azione).distinct().all() if r[0]})
    utenti_disponibili = sorted({r[0] for r in
        db.session.query(LogAccesso.username).distinct().all() if r[0]})

    return render_template('utenti/log.html', logs=logs,
        q=q, azione_f=azione_f, username_f=username_f,
        data_da=data_da, data_a=data_a,
        azioni_disponibili=azioni_disponibili,
        utenti_disponibili=utenti_disponibili)


@auth_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')


# ── GDPR: pulizia log accessi ─────────────────────────────────
GDPR_LOG_RETENTION_DAYS = 180  # art. 5(1)(e) GDPR — limitazione conservazione

def pulisci_log_vecchi():
    """Cancella i log accessi più vecchi di GDPR_LOG_RETENTION_DAYS giorni."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=GDPR_LOG_RETENTION_DAYS)
    n = LogAccesso.query.filter(LogAccesso.timestamp < cutoff).delete()
    db.session.commit()
    return n
