"""
Test di regressione: /display (il monitor con supplenze/classi libere del
giorno, cognomi di docenti assenti/sostituti inclusi) NON deve essere
raggiungibile senza login (Sessione 69 addendum 6).

Prima era in ROUTE_PUBBLICHE (app.py) — chiunque sulla rete della scuola
poteva vederla senza autenticarsi, esattamente il caso descritto dal
Garante nel Provvedimento n. 112/2026 (bacheca di assenze/sostituzioni
nominative accessibile anche a soggetti non autorizzati al trattamento).
Il ruolo 'display' esiste apposta per il monitor fisico: un utente
dedicato che fa login una volta sola con un PIN e resta autenticato
(session.permanent), vedendo comunque solo questa pagina.

Usa la vera app (create_app()) su una copia isolata di database.db,
stesso pattern di sicurezza di tests/test_docente_nuovo_render.py — mai
il database reale.
"""
import os
import shutil
import sqlite3
import tempfile

import pytest


@pytest.fixture
def app_reale():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_reale = os.path.join(base_dir, 'database.db')
    tmp_dir = tempfile.mkdtemp()
    db_copia = os.path.join(tmp_dir, 'database_test_display.db')
    if os.path.exists(db_reale):
        shutil.copy(db_reale, db_copia)
    else:
        sqlite3.connect(db_copia).close()

    orig_join = os.path.join
    def _patched_join(*args):
        if args and args[-1] == 'database.db':
            return db_copia
        return orig_join(*args)

    os.environ['CARONTE_SKIP_LOGIN'] = '0'
    os.environ.pop('CARONTE_DEBUG', None)
    os.path.join = _patched_join
    try:
        from app import create_app
        flask_app = create_app()
    finally:
        os.path.join = orig_join

    assert db_copia in flask_app.config['SQLALCHEMY_DATABASE_URI'], \
        f"controllo di sicurezza fallito: {flask_app.config['SQLALCHEMY_DATABASE_URI']}"
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    yield flask_app
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_display_senza_login_reindirizza_al_login(app_reale):
    with app_reale.test_client() as c:
        r = c.get('/display', follow_redirects=False)
        assert r.status_code == 302
        assert '/login' in r.headers['Location']


def test_display_con_login_normale_e_raggiungibile(app_reale):
    from models.utente import Utente
    with app_reale.app_context():
        u = Utente.query.filter_by(username='ds').first()

    with app_reale.test_client() as c:
        with c.session_transaction() as sess:
            sess['utente_id'] = u.id
            sess['ruolo'] = u.ruolo
        r = c.get('/display')
        assert r.status_code == 200


def test_ruolo_display_vede_solo_display(app_reale):
    from models import db
    from models.utente import Utente
    with app_reale.app_context():
        u = Utente.query.filter_by(username='monitor_sala_docenti').first()
        if not u:
            u = Utente(username='monitor_sala_docenti', nome='Monitor', ruolo='display')
            u.set_pin('0000')
            db.session.add(u)
            db.session.commit()
        id_utente = u.id

    with app_reale.test_client() as c:
        with c.session_transaction() as sess:
            sess['utente_id'] = id_utente
            sess['ruolo'] = 'display'
        r_display = c.get('/display')
        assert r_display.status_code == 200

        r_altro = c.get('/dashboard', follow_redirects=False)
        assert r_altro.status_code == 302
        assert '/display' in r_altro.headers['Location']
