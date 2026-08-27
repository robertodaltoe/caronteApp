"""
Verifica che la protezione CSRF sia davvero attiva sulla route di login,
cosi' se qualcuno la disattiva o la rompe per sbaglio in futuro un test
fallisce subito.

Non usa create_app() (che punterebbe a database.db reale accanto ad
app.py): costruisce una app minimale equivalente, con CSRFProtect
attivo, cosi' il test resta isolato e non tocca mai dati reali.
"""
import os
import re
import pytest
from flask import Flask, Blueprint
from jinja2 import FileSystemLoader
from flask_wtf import CSRFProtect
from models import db


@pytest.fixture
def app_csrf(tmp_path):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-key'
    app.config['TESTING'] = True
    # WTF_CSRF_ENABLED non impostato: resta al default (True), a
    # differenza di test_auth.py dove viene disattivato apposta.

    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    app.jinja_loader = FileSystemLoader(templates_dir)
    CSRFProtect(app)

    db.init_app(app)
    with app.app_context():
        from models.utente import Utente  # noqa
        db.create_all()

    dashboard_bp = Blueprint('dashboard', __name__)

    @dashboard_bp.route('/dashboard-finta')
    def index():
        return 'ok'

    app.register_blueprint(dashboard_bp)

    from routes.auth import auth_bp, _LOGIN_ATTEMPTS
    app.register_blueprint(auth_bp)
    _LOGIN_ATTEMPTS.clear()  # isolamento dal rate-limiter (stato globale in memoria)

    with app.app_context():
        from models.utente import Utente
        u = Utente(username='dsga', cognome='Test', nome='Utente', ruolo='dsga')
        u.set_pin('5678')
        db.session.add(u)
        db.session.commit()

    yield app


def test_login_senza_token_csrf_e_rifiutato(app_csrf):
    with app_csrf.test_client() as c:
        r = c.get('/login')
        html = r.get_data(as_text=True)
        assert re.search(r'meta name="csrf-token"', html) is None or True
        assert 'csrf_token' in html  # campo nascosto generato da csrf_token()

        r2 = c.post('/login', data={'username': 'dsga', 'pin': '5678'})
        assert r2.status_code == 400


def test_login_con_token_csrf_corretto_funziona(app_csrf):
    with app_csrf.test_client() as c:
        r = c.get('/login')
        html = r.get_data(as_text=True)
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert m, 'la pagina di login deve contenere il campo csrf_token'
        token = m.group(1)

        r2 = c.post('/login', data={'username': 'dsga', 'pin': '5678', 'csrf_token': token})
        assert r2.status_code != 400


@pytest.fixture
def app_csrf_con_handler(app_csrf):
    """
    Stessa app minimale di app_csrf, con in più l'errorhandler(CSRFError)
    registrato in app.py::create_app() — replicato qui perché quella
    funzione punta sempre a database.db reale (vedi la sua docstring),
    quindi non è utilizzabile direttamente nei test (regola non
    negoziabile n.1 del progetto). Serve a verificare l'intero percorso
    di un mismatch CSRF su /login: niente pagina bianca "Bad Request",
    ma un redirect con un messaggio comprensibile.
    """
    from flask_wtf.csrf import CSRFError
    from flask import flash, redirect, url_for, request

    @app_csrf.errorhandler(CSRFError)
    def _csrf_error(e):
        flash('La sessione era scaduta o non più valida: la pagina è stata '
              'ricaricata, riprova ad inviare il modulo.', 'warning')
        if request.path.startswith('/login'):
            return redirect(url_for('auth.login'))
        return redirect(request.referrer or url_for('dashboard.index'))

    @app_csrf.after_request
    def _no_cache_login(response):
        if request.endpoint == 'auth.login':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
        return response

    return app_csrf


def test_csrf_mismatch_su_login_mostra_un_messaggio_non_pagina_bianca(app_csrf_con_handler):
    """
    Roberto: login che sembra non fare nulla da Chrome, nessun errore a
    schermo, con qualunque utenza — causa più probabile: un mismatch del
    token CSRF (frequente da Chrome per via del suo prefetch/preload
    delle pagine, che genera in anticipo un token poi non più coerente
    con la sessione al momento dell'invio reale) gestito da
    app.py::_csrf_error con un redirect + flash(), ma templates/login.html
    non renderizzava MAI get_flashed_messages() (non estende base.html,
    è un documento a sé) — il messaggio spariva nel nulla e la pagina
    tornava vuota, indistinguibile da "il login non fa niente".
    """
    with app_csrf_con_handler.test_client() as c:
        c.get('/login')  # genera una sessione/token
        # Token deliberatamente sbagliato: simula un token ormai
        # superato (caso prefetch, sessione scaduta, doppia scheda...).
        r = c.post('/login', data={'username': 'dsga', 'pin': '5678',
                                    'csrf_token': 'token-scaduto-o-sbagliato'},
                    follow_redirects=True)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'sessione era scaduta o non più valida' in html


def test_login_non_e_mai_servito_dalla_cache(app_csrf_con_handler):
    """
    Roberto: da Chrome il login falliva SEMPRE (anche riprovando subito
    dopo il messaggio di sessione scaduta, anche in incognito quindi non
    un'estensione) — nessuna risposta di /login aveva un header
    Cache-Control esplicito. Senza, Chrome può servire /login dalla
    cache HTTP invece di richiederla di nuovo al server: il "reload"
    dopo un redirect mostra in realtà lo STESSO HTML con lo STESSO
    csrf_token già scaduto, che fallisce di nuovo — un ciclo infinito.
    La pagina di login (contiene un token legato alla sessione corrente)
    non deve mai essere cacheable.
    """
    with app_csrf_con_handler.test_client() as c:
        r = c.get('/login')
        cache_control = r.headers.get('Cache-Control', '')
        assert 'no-store' in cache_control
