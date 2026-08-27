"""
Roberto: login che falliva SEMPRE da Chrome, con qualsiasi utenza,
anche riprovando subito dopo il messaggio di sessione scaduta, anche
in incognito, anche con un profilo Chrome nuovo, anche dopo aver
rigenerato la voce "Chrome Safe Storage" nel Portachiavi — nessuna di
queste cause spiegava un fallimento sistematico e identico ad ogni
tentativo.

Causa reale, trovata nella tab Network di Chrome: una richiesta GET
automatica a /favicon.ico (Chrome la fa da solo quando una pagina non
dichiara un'icona esplicita — templates/login.html non lo faceva)
arrivava a app.py::check_auth() senza corrispondere a nessuna rotta
(endpoint=None). PRIMA di questo fix, endpoint=None diventava '' e
proseguiva come una qualsiasi pagina protetta: utente non loggato →
session.clear() + redirect a /login — cancellando la sessione (e il
token CSRF già incollato nel modulo) appena creata dalla pagina di
login visibile nella STESSA scheda del browser, ancora prima che
l'utente potesse inviare il modulo. Non un caso raro: succedeva ad ogni
caricamento della pagina di login, con qualunque account, perché la
causa non aveva nulla a che fare con le credenziali né con le
impostazioni del browser.

Non usa create_app() (punta sempre a database.db reale, vedi la sua
docstring) — replica qui solo il prima/dopo della porzione rilevante
di check_auth(), stesso pattern di isolamento già usato in test_csrf.py.
"""
import os
import pytest
from flask import Flask, Blueprint, session, redirect, url_for, request
from jinja2 import FileSystemLoader
from flask_wtf import CSRFProtect
from models import db

ROUTE_PUBBLICHE = {'auth.login', 'auth.logout', 'static'}


def _crea_app(corretto):
    """corretto=False replica il comportamento PRIMA del fix (bug
    riprodotto); corretto=True replica quello DOPO (fix applicato)."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-key'
    app.config['TESTING'] = True

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
    _LOGIN_ATTEMPTS.clear()

    with app.app_context():
        from models.utente import Utente
        u = Utente(username='dsga', cognome='Test', nome='Utente', ruolo='dsga')
        u.set_pin('5678')
        db.session.add(u)
        db.session.commit()

    @app.before_request
    def check_auth():
        from routes.auth import get_utente_corrente
        endpoint = request.endpoint or ''

        if endpoint in ROUTE_PUBBLICHE or endpoint.startswith('static'):
            return None

        if corretto and request.endpoint is None:
            # Fix: un 404 genuino (nessuna rotta corrisponde, es.
            # /favicon.ico) non deve toccare la sessione.
            return None

        u = get_utente_corrente()
        if not u or not u.attivo:
            session.clear()
            return redirect(url_for('auth.login', next=request.url))
        return None

    return app


@pytest.fixture
def app_bug():
    return _crea_app(corretto=False)


@pytest.fixture
def app_fix():
    return _crea_app(corretto=True)


def _token_e_cookie(client):
    r = client.get('/login')
    html = r.get_data(as_text=True)
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, 'la pagina di login deve contenere il campo csrf_token'
    return m.group(1)


def test_riproduce_il_bug_favicon_invalida_la_sessione_di_login(app_bug):
    """Prima del fix: la richiesta 'fantasma' a /favicon.ico (nessuna
    rotta corrispondente, endpoint=None) cancella la sessione appena
    creata dalla pagina di login, invalidando il suo token — il login
    fallisce anche con credenziali corrette."""
    with app_bug.test_client() as c:
        token = _token_e_cookie(c)

        # Simula la richiesta automatica del browser per /favicon.ico,
        # generata dalla STESSA scheda/sessione mentre la pagina di
        # login è ancora visibile — nessuna rotta la gestisce in questa
        # app di test, esattamente come /favicon.ico in produzione.
        c.get('/favicon.ico')

        r = c.post('/login', data={'username': 'dsga', 'pin': '5678', 'csrf_token': token})
        assert r.status_code == 400, (
            'con il bug, il token della pagina di login non corrisponde più '
            'alla sessione dopo la richiesta fantasma a /favicon.ico')


def test_il_fix_permette_il_login_nonostante_la_richiesta_favicon(app_fix):
    """Dopo il fix: la stessa identica sequenza (GET /login, poi una
    richiesta a una rotta inesistente come /favicon.ico, poi l'invio
    del modulo con lo stesso token) deve funzionare — endpoint=None non
    tocca più la sessione."""
    with app_fix.test_client() as c:
        token = _token_e_cookie(c)

        c.get('/favicon.ico')

        r = c.post('/login', data={'username': 'dsga', 'pin': '5678', 'csrf_token': token})
        assert r.status_code == 302
        assert '/login' not in r.headers.get('Location', '/login')
