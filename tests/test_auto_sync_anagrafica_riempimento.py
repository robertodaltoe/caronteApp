"""
Merge "a riempimento" dell'anagrafica docenti nel sync automatico
(modules/auto_sync.py::_merge_riempimento_docenti).

Regola: per un docente presente su entrambe le macchine, se un campo e'
vuoto da una parte e compilato dall'altra si copia il valore; se sono
entrambi compilati e diversi e' un conflitto da rivedere (/sync/conflitti);
non si crea e non si elimina mai nessun docente e non si tocca nessun altro
campo. Campi coperti: email e ricevimento (colloqui_giorno / ora_inizio /
ora_fine, piu' le righe per anno DocenteColloquiAnno mancanti in locale).
"""
import json
import sqlite3
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from models import db
from models.docente import Docente, DocenteColloquiAnno
from models.sync_conflitto import SyncConflitto
from modules.auto_sync import _merge_additivo

from tests.conftest import crea_docente


@pytest.fixture
def remoto_path(tmp_path):
    path = tmp_path / 'remoto.db'
    engine = create_engine(f'sqlite:///{path}')
    db.metadata.create_all(engine)
    engine.dispose()
    return str(path)


def _remoto(path, sql, params=()):
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _docente_remoto(path, cognome, nome, **campi):
    campi = {'cognome': cognome, 'nome': nome, 'ore_contratto': 18, 'attivo': 1, **campi}
    colonne = ', '.join(campi)
    segn = ', '.join('?' for _ in campi)
    return _remoto(path, f'INSERT INTO docenti ({colonne}) VALUES ({segn})', list(campi.values()))


def _locale(id_docente):
    db.session.expire_all()
    return db.session.get(Docente, id_docente)


# ── email ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('vuoto', [None, '', 'None'])
def test_email_vuota_in_locale_viene_riempita_dal_remoto(app, db_session, remoto_path, vuoto):
    d = crea_docente('Rossi', nome='Mario')
    d.email = vuoto
    db.session.commit()
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='mario.rossi@scuola.test')

    r = _merge_additivo(db, remoto_path)

    assert _locale(d.id).email == 'mario.rossi@scuola.test'
    assert r['riempiti'] == 1
    assert r['conflitti_nuovi'] == 0


def test_email_locale_gia_compilata_non_si_tocca_e_segnala_da_pubblicare(app, db_session, remoto_path):
    d = crea_docente('Rossi', nome='Mario')
    d.email = 'mario.rossi@scuola.test'
    db.session.commit()
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email=None)

    r = _merge_additivo(db, remoto_path)

    assert _locale(d.id).email == 'mario.rossi@scuola.test'
    assert r['riempiti'] == 0
    # il remoto non ha il valore: bisogna ripubblicare, altrimenti l'altra
    # postazione non lo vedra' mai (stessa logica delle righe "solo locali")
    assert r['solo_locali'] >= 1


def test_email_uguale_a_meno_delle_maiuscole_non_e_un_conflitto(app, db_session, remoto_path):
    d = crea_docente('Rossi', nome='Mario')
    d.email = 'Mario.Rossi@scuola.test'
    db.session.commit()
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='mario.rossi@scuola.test')

    r = _merge_additivo(db, remoto_path)

    assert r['conflitti_nuovi'] == 0 and r['riempiti'] == 0
    assert _locale(d.id).email == 'Mario.Rossi@scuola.test'


def test_email_diverse_in_entrambe_vanno_in_conflitto_senza_modifiche(app, db_session, remoto_path):
    d = crea_docente('Rossi', nome='Mario')
    d.email = 'locale@scuola.test'
    db.session.commit()
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='remota@scuola.test')

    r = _merge_additivo(db, remoto_path)

    assert _locale(d.id).email == 'locale@scuola.test'
    assert r['conflitti_nuovi'] == 1
    c = SyncConflitto.query.filter_by(tabella='docenti').one()
    assert json.loads(c.campi_diversi) == ['email']
    assert json.loads(c.chiave_logica) == {'cognome': 'Rossi', 'nome': 'Mario'}
    assert json.loads(c.dati_remoti)['email'] == 'remota@scuola.test'

    # secondo giro: lo stesso conflitto viene aggiornato, non duplicato
    r2 = _merge_additivo(db, remoto_path)
    assert r2['conflitti_nuovi'] == 0
    assert SyncConflitto.query.filter_by(tabella='docenti', risolto=False).count() == 1


def test_conflitto_risolto_tieni_locale_non_ricompare(app, db_session, remoto_path):
    d = crea_docente('Rossi', nome='Mario')
    d.email = 'locale@scuola.test'
    db.session.commit()
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='remota@scuola.test')
    _merge_additivo(db, remoto_path)
    c = SyncConflitto.query.filter_by(tabella='docenti').one()
    c.risolto, c.scelta, c.risolto_il = True, 'locale', datetime.utcnow()
    db.session.commit()

    r = _merge_additivo(db, remoto_path)

    assert r['conflitti_nuovi'] == 0
    assert SyncConflitto.query.filter_by(tabella='docenti', risolto=False).count() == 0


# ── ricevimento ────────────────────────────────────────────────────────

def test_ricevimento_vuoto_in_locale_viene_riempito_come_gruppo(app, db_session, remoto_path):
    d = crea_docente('Verdi', nome='Anna')
    _docente_remoto(remoto_path, 'Verdi', 'Anna',
                    colloqui_giorno=2, colloqui_ora_inizio=3, colloqui_ora_fine=4)

    r = _merge_additivo(db, remoto_path)

    x = _locale(d.id)
    assert (x.colloqui_giorno, x.colloqui_ora_inizio, x.colloqui_ora_fine) == (2, 3, 4)
    assert r['riempiti'] == 1


def test_ricevimento_giorno_zero_e_un_valore_non_un_vuoto(app, db_session, remoto_path):
    # 0 = lunedi': non va confuso con None
    d = crea_docente('Verdi', nome='Anna')
    d.colloqui_giorno, d.colloqui_ora_inizio, d.colloqui_ora_fine = 0, 1, 2
    db.session.commit()
    _docente_remoto(remoto_path, 'Verdi', 'Anna',
                    colloqui_giorno=3, colloqui_ora_inizio=5, colloqui_ora_fine=6)

    r = _merge_additivo(db, remoto_path)

    x = _locale(d.id)
    assert (x.colloqui_giorno, x.colloqui_ora_inizio, x.colloqui_ora_fine) == (0, 1, 2)
    assert r['conflitti_nuovi'] == 1
    c = SyncConflitto.query.filter_by(tabella='docenti').one()
    assert set(json.loads(c.campi_diversi)) == {'colloqui_giorno', 'colloqui_ora_inizio',
                                                  'colloqui_ora_fine'}


def test_ricevimento_per_anno_mancante_in_locale_viene_aggiunto(app, db_session, remoto_path):
    d = crea_docente('Verdi', nome='Anna')
    id_remoto = _docente_remoto(remoto_path, 'Verdi', 'Anna')
    _remoto(remoto_path,
            'INSERT INTO docenti_colloqui_anno (id_docente, anno_scol, giorno, ora_inizio, ora_fine) '
            'VALUES (?, ?, ?, ?, ?)', (id_remoto, '2026-2027', 4, 2, 3))

    r = _merge_additivo(db, remoto_path)

    righe = DocenteColloquiAnno.query.filter_by(id_docente=d.id).all()
    assert [(x.anno_scol, x.giorno, x.ora_inizio, x.ora_fine) for x in righe] == [
        ('2026-2027', 4, 2, 3)]
    assert r['riempiti'] == 1


def test_ricevimento_per_anno_gia_presente_in_locale_non_si_tocca(app, db_session, remoto_path):
    d = crea_docente('Verdi', nome='Anna')
    # riga locale con giorno None = "nessun colloquio quest'anno": scelta esplicita
    db.session.add(DocenteColloquiAnno(id_docente=d.id, anno_scol='2026-2027',
                                       giorno=None, ora_inizio=None, ora_fine=None))
    db.session.commit()
    id_remoto = _docente_remoto(remoto_path, 'Verdi', 'Anna')
    _remoto(remoto_path,
            'INSERT INTO docenti_colloqui_anno (id_docente, anno_scol, giorno, ora_inizio, ora_fine) '
            'VALUES (?, ?, ?, ?, ?)', (id_remoto, '2026-2027', 4, 2, 3))

    r = _merge_additivo(db, remoto_path)

    riga = DocenteColloquiAnno.query.filter_by(id_docente=d.id).one()
    assert riga.giorno is None
    assert r['riempiti'] == 0 and r['conflitti_nuovi'] == 0


# ── sicurezza del merge ────────────────────────────────────────────────

def test_docenti_solo_remoti_non_vengono_creati(app, db_session, remoto_path):
    crea_docente('Rossi', nome='Mario')
    _docente_remoto(remoto_path, 'Nuovo', 'Docente', email='nuovo@scuola.test')

    _merge_additivo(db, remoto_path)

    assert Docente.query.filter_by(cognome='Nuovo').count() == 0
    assert Docente.query.count() == 1


def test_omonimi_su_una_delle_due_parti_vengono_saltati(app, db_session, remoto_path):
    a = crea_docente('Rossi', nome='Mario')
    b = crea_docente('Rossi', nome='Mario')
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='mario.rossi@scuola.test')

    r = _merge_additivo(db, remoto_path)

    assert _locale(a.id).email in (None, '') and _locale(b.id).email in (None, '')
    assert r['riempiti'] == 0
    assert r['anagrafica_saltati'] == 1


def test_omonimi_nel_remoto_vengono_saltati(app, db_session, remoto_path):
    d = crea_docente('Rossi', nome='Mario')
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='uno@scuola.test')
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='due@scuola.test')

    r = _merge_additivo(db, remoto_path)

    assert _locale(d.id).email in (None, '')
    assert r['anagrafica_saltati'] == 1


def test_docenti_anonimizzati_vengono_ignorati(app, db_session, remoto_path):
    d = crea_docente('ANONIMO_0007', nome='')
    _docente_remoto(remoto_path, 'ANONIMO_0007', '', email='qualcuno@scuola.test')

    r = _merge_additivo(db, remoto_path)

    assert _locale(d.id).email in (None, '')
    assert r['riempiti'] == 0


def test_abbinamento_ignora_maiuscole_e_spazi(app, db_session, remoto_path):
    d = crea_docente('De Luca', nome='Nicola')
    _docente_remoto(remoto_path, ' DE LUCA ', 'nicola', email='n.deluca@scuola.test')

    _merge_additivo(db, remoto_path)

    assert _locale(d.id).email == 'n.deluca@scuola.test'


def test_nessun_altro_campo_cambia_e_il_secondo_giro_e_vuoto(app, db_session, remoto_path):
    """Confronto riga per riga: dopo il merge l'unica differenza sono i campi
    coperti (+ modificato_il); le altre colonne restano identiche."""
    d = crea_docente('Rossi', nome='Mario')
    d.note, d.ore_contratto, d.altra_scuola = 'nota locale', 12, 'Altro Istituto'
    db.session.commit()
    prima = {c.name: getattr(_locale(d.id), c.name) for c in Docente.__table__.columns}
    _docente_remoto(remoto_path, 'Rossi', 'Mario', email='mario.rossi@scuola.test',
                    note='nota remota', ore_contratto=18, altra_scuola=None, attivo=0,
                    colloqui_giorno=1, colloqui_ora_inizio=1, colloqui_ora_fine=2)

    _merge_additivo(db, remoto_path)

    dopo = {c.name: getattr(_locale(d.id), c.name) for c in Docente.__table__.columns}
    cambiati = {k for k in prima if prima[k] != dopo[k]}
    assert cambiati <= {'email', 'colloqui_giorno', 'colloqui_ora_inizio',
                        'colloqui_ora_fine', 'modificato_il'}
    assert dopo['note'] == 'nota locale' and dopo['attivo'] == prima['attivo']

    r2 = _merge_additivo(db, remoto_path)
    assert r2['riempiti'] == 0 and r2['conflitti_nuovi'] == 0


def test_remoto_con_schema_vecchio_senza_colonne_non_da_errore(app, db_session, tmp_path):
    """Un database pubblicato da una macchina con codice piu' vecchio puo'
    non avere ancora le colonne/tabelle dei colloqui: nessun errore."""
    d = crea_docente('Rossi', nome='Mario')
    path = tmp_path / 'vecchio.db'
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE docenti (id INTEGER PRIMARY KEY, cognome TEXT, nome TEXT, email TEXT)')
    conn.execute("INSERT INTO docenti (cognome, nome, email) VALUES ('Rossi', 'Mario', 'm@scuola.test')")
    conn.commit()
    conn.close()

    # le altre tabelle sincronizzate non esistono nel file vecchio: _righe le tratta come vuote
    r = _merge_additivo(db, str(path))

    assert _locale(d.id).email == 'm@scuola.test'
    assert r['riempiti'] == 1


# ── risoluzione dalla pagina /sync/conflitti (app vera su DB in /tmp) ──

@pytest.fixture
def app_reale():
    import os
    import shutil
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    db_copia = os.path.join(tmp_dir, 'database_test_sync_anagrafica.db')
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
    assert db_copia in flask_app.config['SQLALCHEMY_DATABASE_URI']
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    from models.utente import Utente
    with flask_app.app_context():
        if not Utente.query.filter_by(username='dsga', attivo=True).first():
            u = Utente(username='dsga', nome='DSGA', ruolo='dsga')
            u.set_pin('0000')
            db.session.add(u)
            db.session.commit()
    yield flask_app
    with flask_app.app_context():
        db.session.remove()
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_conflitto_docente_si_vede_e_si_risolve_tenendo_il_remoto(app_reale, tmp_path):
    path = tmp_path / 'remoto.db'
    engine = create_engine(f'sqlite:///{path}')
    db.metadata.create_all(engine)
    engine.dispose()
    with app_reale.app_context():
        d = Docente(cognome='Rossi', nome='Mario', ore_contratto=18, attivo=True,
                    email='locale@scuola.test')
        altro = Docente(cognome='Rossi', nome='Luca', ore_contratto=18, attivo=True,
                        email='luca@scuola.test')
        db.session.add_all([d, altro])
        db.session.commit()
        id_d, id_altro = d.id, altro.id
        _docente_remoto(str(path), 'Rossi', 'Mario', email='remota@scuola.test')
        _merge_additivo(db, str(path))
        id_conf = SyncConflitto.query.filter_by(tabella='docenti').one().id

    with app_reale.test_client() as c:
        r = c.get('/sync/conflitti')
        corpo = r.get_data(as_text=True)
        assert r.status_code == 200
        assert 'Anagrafica docente' in corpo and 'remota@scuola.test' in corpo
        assert 'Errore imprevisto' not in corpo
        r = c.post(f'/sync/conflitti/{id_conf}/risolvi', data={'scelta': 'remoto'})
        assert r.status_code in (302, 303)

    with app_reale.app_context():
        assert db.session.get(Docente, id_d).email == 'remota@scuola.test'
        assert db.session.get(Docente, id_altro).email == 'luca@scuola.test'
