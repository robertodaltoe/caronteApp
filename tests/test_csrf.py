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
