"""
Regressione: GET /docenti/nuovo dava un errore 500 reale (segnalato da
Roberto in produzione, non preso dai test esistenti perché mockano
render_template — vedi tests/test_docenti_materie_selettore_anno.py).

Causa: templates/docente_form.html, nella card "Materie insegnate",
faceva `url_for('docenti.modifica', id=docente.id)` senza controllare
prima che `docente` non fosse None (il caso "nuovo docente") — la
stessa card ha un fratello quasi identico ("Colloqui") poco più sotto
nel file che invece la guardia ce l'ha (`{% if docente %}`), quindi non
è un pattern nuovo da inventare, solo uno dimenticato in un punto.

Questo test renderizza il TEMPLATE VERO (non mockato) tramite l'app
reale creata da app.py::create_app(), su una copia del database
isolata in /tmp — mai il database.db reale — cosa che i test con
render_template finto non possono catturare per definizione, essendo
proprio un bug di rendering del template.
"""
import os
import shutil
import sqlite3
import tempfile

import pytest


@pytest.fixture
def app_reale():
    """App Flask reale (app.py::create_app()) puntata su una copia
    temporanea del database, mai sul database.db vero — stesso pattern
    di sicurezza usato nelle sessioni di collaudo dal vivo (vedi
    CLAUDE.md, regola 1)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_reale = os.path.join(base_dir, 'database.db')
    tmp_dir = tempfile.mkdtemp()
    db_copia = os.path.join(tmp_dir, 'database_test_render.db')
    if os.path.exists(db_reale):
        shutil.copy(db_reale, db_copia)
    else:
        # database.db potrebbe non esistere in un ambiente di CI pulito:
        # create_app()/db.create_all() lo crea comunque da zero.
        sqlite3.connect(db_copia).close()

    orig_join = os.path.join

    def _patched_join(*args):
        if args and args[-1] == 'database.db':
            return db_copia
        return orig_join(*args)

    os.environ['CARONTE_SKIP_LOGIN'] = '1'
    os.environ['CARONTE_DEBUG'] = '1'
    os.path.join = _patched_join
    try:
        from app import create_app
        flask_app = create_app()
    finally:
        os.path.join = orig_join

    assert db_copia in flask_app.config['SQLALCHEMY_DATABASE_URI'], \
        f"controllo di sicurezza fallito: {flask_app.config['SQLALCHEMY_DATABASE_URI']}"

    flask_app.config['TESTING'] = True
    yield flask_app

    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_docenti_nuovo_get_non_va_in_500(app_reale):
    with app_reale.test_client() as c:
        r = c.get('/docenti/nuovo')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert 'Errore imprevisto' not in corpo
        # Il messaggio che sostituisce la card "Materie insegnate" per
        # un docente non ancora creato deve comparire al suo posto.
        assert 'si assegnano dopo aver creato il docente' in corpo


def test_docenti_modifica_get_mostra_ancora_la_card_materie(app_reale):
    """Verifica che la correzione non abbia nascosto la card anche per
    un docente ESISTENTE (dove invece deve comparire, con il
    selettore d'anno funzionante)."""
    from models import db
    from models.docente import Docente

    with app_reale.app_context():
        d = Docente(cognome='Prova', nome='Test', ore_contratto=18, attivo=True)
        db.session.add(d)
        db.session.commit()
        id_docente = d.id

    with app_reale.test_client() as c:
        r = c.get(f'/docenti/{id_docente}/modifica')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert 'Errore imprevisto' not in corpo
        assert 'Materie insegnate' in corpo
