"""
Test del modulo di autenticazione: login, blocco per tentativi falliti
ripetuti (rate limiting) e logica dei permessi per ruolo.
"""
import pytest
from models import db
from models.utente import Utente, PERMESSI


@pytest.fixture
def app_auth(app):
    """App di test con auth_bp registrato, per testare le route reali.

    La route di login reindirizza a 'dashboard.index' di default: qui
    registriamo un blueprint 'dashboard' fittizio (senza dipendenze
    pesanti) solo per permettere a url_for(...) di risolverlo, senza
    dover caricare la vera dashboard con tutte le sue query."""
    import os
    from flask import Blueprint
    from jinja2 import FileSystemLoader
    from routes.auth import auth_bp, _LOGIN_ATTEMPTS

    # La app di test (conftest.py) non punta alla cartella templates/
    # reale del progetto: la aggiungiamo qui, serve per renderizzare
    # login.html nelle risposte con errore.
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    app.jinja_loader = FileSystemLoader(templates_dir)

    # login.html chiama csrf_token() nel template: serve CSRFProtect
    # anche su questa app di test minimale per avere quella funzione
    # disponibile in Jinja. La protezione CSRF vera e propria è testata
    # a parte (vedi test_csrf.py) — qui la disattiviamo per concentrarci
    # solo sulla logica di login/permessi.
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.extensions.get('csrf'):
        from flask_wtf import CSRFProtect
        CSRFProtect(app)

    if 'dashboard' not in app.blueprints:
        dashboard_bp = Blueprint('dashboard', __name__)

        @dashboard_bp.route('/dashboard-finta')
        def index():
            return 'ok'

        app.register_blueprint(dashboard_bp)

    if 'auth' not in app.blueprints:
        app.register_blueprint(auth_bp)

    _LOGIN_ATTEMPTS.clear()  # isolamento tra test (stato globale in memoria)
    yield app
    _LOGIN_ATTEMPTS.clear()


def _crea_utente(username, pin, ruolo='segreteria', attivo=True):
    u = Utente(username=username, cognome='Test', nome='Utente', ruolo=ruolo, attivo=attivo)
    u.set_pin(pin)
    db.session.add(u)
    db.session.commit()
    return u


# ── Login base ───────────────────────────────────────────────────

def test_login_corretto_reindirizza(app_auth):
    with app_auth.app_context():
        _crea_utente('dsga', '5678', ruolo='dsga')
        with app_auth.test_client() as c:
            r = c.post('/login', data={'username': 'dsga', 'pin': '5678'})
            assert r.status_code == 302


def test_login_pin_errato_rimane_sulla_pagina(app_auth):
    with app_auth.app_context():
        _crea_utente('dsga', '5678', ruolo='dsga')
        with app_auth.test_client() as c:
            r = c.post('/login', data={'username': 'dsga', 'pin': 'sbagliato'})
            assert r.status_code == 200
            assert 'Credenziali non corrette' in r.get_data(as_text=True)


def test_login_utente_disattivato_fallisce(app_auth):
    with app_auth.app_context():
        _crea_utente('exdipendente', '1111', attivo=False)
        with app_auth.test_client() as c:
            r = c.post('/login', data={'username': 'exdipendente', 'pin': '1111'})
            assert r.status_code == 200
            assert 'Credenziali non corrette' in r.get_data(as_text=True)


# ── Rate limiting ────────────────────────────────────────────────

def test_blocco_dopo_tentativi_falliti_ripetuti(app_auth):
    with app_auth.app_context():
        _crea_utente('dsga', '5678', ruolo='dsga')
        with app_auth.test_client() as c:
            for _ in range(5):
                c.post('/login', data={'username': 'dsga', 'pin': 'sbagliato'})
            # Il 6° tentativo, pur con PIN corretto, deve essere bloccato.
            r = c.post('/login', data={'username': 'dsga', 'pin': '5678'})
            assert 'Troppi tentativi' in r.get_data(as_text=True)


def test_blocco_non_impatta_altro_utente(app_auth):
    with app_auth.app_context():
        _crea_utente('dsga', '5678', ruolo='dsga')
        _crea_utente('ds', '1234', ruolo='ds')
        with app_auth.test_client() as c:
            for _ in range(5):
                c.post('/login', data={'username': 'dsga', 'pin': 'sbagliato'})
            # Un altro utente, stesso IP (stesso test client), deve poter
            # accedere normalmente: il blocco è per coppia IP+username.
            r = c.post('/login', data={'username': 'ds', 'pin': '1234'})
            assert r.status_code == 302


def test_login_corretto_resetta_il_contatore(app_auth):
    with app_auth.app_context():
        _crea_utente('dsga', '5678', ruolo='dsga')
        with app_auth.test_client() as c:
            for _ in range(3):
                c.post('/login', data={'username': 'dsga', 'pin': 'sbagliato'})
            # Login corretto prima di raggiungere la soglia: azzera i tentativi.
            r_ok = c.post('/login', data={'username': 'dsga', 'pin': '5678'})
            assert r_ok.status_code == 302
            c.get('/logout')
            # Da qui altri 3 tentativi falliti non devono sommarsi ai
            # precedenti (già azzerati) e quindi non bloccare.
            for _ in range(3):
                c.post('/login', data={'username': 'dsga', 'pin': 'sbagliato'})
            r2 = c.post('/login', data={'username': 'dsga', 'pin': '5678'})
            assert r2.status_code == 302


# ── Permessi per ruolo (models/utente.py) ────────────────────────

def test_dsga_ha_tutti_i_permessi():
    u = Utente(username='dsga', ruolo='dsga')
    assert u.ha_permesso('supplenze')
    assert u.ha_permesso('gestione_utenti')
    assert u.ha_permesso('qualsiasi_cosa_inventata')


def test_permesso_scrittura_implica_lettura():
    """Chi ha 'banca_ore' (scrittura) deve avere implicitamente anche
    'banca_ore_r' (lettura), anche se non è elencato esplicitamente."""
    u = Utente(username='segreteria', ruolo='segreteria')
    assert 'banca_ore' in PERMESSI['segreteria']
    assert 'banca_ore_r' not in PERMESSI['segreteria']  # non esplicito
    assert u.ha_permesso('banca_ore_r')  # ma implicito
    assert u.ha_permesso('banca_ore')


def test_permesso_lettura_non_implica_scrittura():
    u = Utente(username='ds', ruolo='ds')
    assert u.ha_permesso('supplenze_r')
    assert not u.ha_permesso('supplenze')  # il DS non assegna supplenze


def test_ruolo_sconosciuto_non_ha_permessi():
    u = Utente(username='fantasma', ruolo='ruolo_inesistente')
    assert not u.ha_permesso('supplenze')
    assert not u.ha_permesso('display')
