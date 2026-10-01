"""
Navigazione (Sessione 71): elenco unico delle funzioni in
modules/navigazione.py, da cui derivano menu Impostazioni a gruppi,
ricerca delle funzioni (Ctrl+K), voce di navbar attiva, percorso sopra
il contenuto e scorciatoie per ruolo in Dashboard.

Renderizza i TEMPLATE VERI tramite app.py::create_app(), su un database
temporaneo vuoto in /tmp — mai il database.db reale (CLAUDE.md, regola 1).
"""
import os
import shutil
import sqlite3
import tempfile

import pytest


@pytest.fixture
def app_reale():
    tmp_dir = tempfile.mkdtemp()
    db_copia = os.path.join(tmp_dir, 'database_test_navigazione.db')
    sqlite3.connect(db_copia).close()

    orig_join = os.path.join

    def _patched_join(*args):
        if args and args[-1] == 'database.db':
            return db_copia
        return orig_join(*args)

    os.path.join = _patched_join
    try:
        from app import create_app
        flask_app = create_app()
    finally:
        os.path.join = orig_join

    assert db_copia in flask_app.config['SQLALCHEMY_DATABASE_URI'], \
        f"controllo di sicurezza fallito: {flask_app.config['SQLALCHEMY_DATABASE_URI']}"
    flask_app.config['TESTING'] = True

    from models import db
    from models.utente import Utente
    with flask_app.app_context():
        for username, ruolo in (('dsga', 'dsga'), ('segr', 'segreteria'), ('ds', 'ds')):
            u = Utente(username=username, nome=username.upper(), ruolo=ruolo)
            u.set_pin('0000')
            db.session.add(u)
        db.session.commit()

    yield flask_app

    shutil.rmtree(tmp_dir, ignore_errors=True)


def _client_come(app, username):
    from models.utente import Utente
    with app.app_context():
        u = Utente.query.filter_by(username=username).first()
        uid, ruolo = u.id, u.ruolo
    c = app.test_client()
    with c.session_transaction() as s:
        s['utente_id'] = uid
        s['ruolo'] = ruolo
    return c


def test_ogni_voce_punta_a_un_endpoint_esistente(app_reale):
    """Una voce con endpoint rinominato/sparito romperebbe il menu."""
    from flask import url_for
    from modules.navigazione import FUNZIONI, GRUPPI_LABEL, SCORCIATOIE_RUOLO
    with app_reale.test_request_context():
        for v in FUNZIONI:
            assert url_for(v['endpoint'])
            assert v['gruppo'] in GRUPPI_LABEL
    endpoints = {v['endpoint'] for v in FUNZIONI}
    for ruolo, elenco in SCORCIATOIE_RUOLO.items():
        for e in elenco:
            assert e in endpoints, (ruolo, e)


def test_menu_impostazioni_e_funzioni_prima_nascoste(app_reale):
    c = _client_come(app_reale, 'dsga')
    corpo = c.get('/dashboard').get_data(as_text=True)
    assert 'Panoramica impostazioni' in corpo
    # Prima raggiungibili solo attraversando altre pagine o da nessun link.
    assert '/assegnazioni"' in corpo
    assert '/cambi-quadro"' in corpo
    assert '/indisponibilita/ricorrenti' in corpo
    assert 'id="nav-search-sugg"' in corpo
    assert 'Le tue sezioni' in corpo


def test_voce_attiva_e_percorso(app_reale):
    c = _client_come(app_reale, 'dsga')
    corpo = c.get('/docenti').get_data(as_text=True)
    assert 'class="nav-percorso"' in corpo
    assert 'Anagrafica docenti' in corpo
    # La voce Impostazioni (dove ora vive Docenti) è evidenziata.
    i = corpo.index('Impostazioni</a>')
    assert 'class="active"' in corpo[i - 900:i]


def test_ricerca_trova_anche_le_funzioni(app_reale):
    c = _client_come(app_reale, 'dsga')
    corpo = c.get('/ricerca?q=lettere incarico').get_data(as_text=True)
    assert 'Funzioni (1)' in corpo
    assert '/contrattazione/lettere' in corpo
    # Senza accenti trova lo stesso.
    corpo = c.get('/ricerca?q=attivita fuori').get_data(as_text=True)
    assert 'Attività fuori aula' in corpo


def test_voci_filtrate_per_ruolo(app_reale):
    """Le voci riservate non compaiono a chi non può aprirle: Permessi
    solo al DS, Gestione utenti solo a chi ha gestione_utenti."""
    corpo_segr = _client_come(app_reale, 'segr').get('/dashboard').get_data(as_text=True)
    assert 'Permessi per ruolo' not in corpo_segr
    assert 'Gestione utenti e PIN' not in corpo_segr
    corpo_ds = _client_come(app_reale, 'ds').get('/dashboard').get_data(as_text=True)
    assert 'Permessi per ruolo' in corpo_ds


def test_scorciatoie_diverse_per_ruolo(app_reale):
    from modules import navigazione as nav

    class U:
        def __init__(self, ruolo):
            self.ruolo = ruolo

        def ha_permesso(self, p):
            return True

    voci = [dict(v, url='/' + v['endpoint']) for v in nav.FUNZIONI]
    segr = [v['endpoint'] for v in nav.scorciatoie(U('segreteria'), voci)]
    coll = [v['endpoint'] for v in nav.scorciatoie(U('collaboratore'), voci)]
    assert 'banca_ore.index' in segr and 'mail_bozze.index' in segr
    assert 'agenda.index' in coll and 'cambi.lista' in coll
    assert segr != coll


def test_cerca_funzioni_ignora_accenti_e_maiuscole():
    from modules import navigazione as nav
    trovate = [v['label'] for v in nav.cerca_funzioni('INDISPONIBILITA ricorr', nav.FUNZIONI)]
    assert trovate == ['Indisponibilità ricorrenti']
    assert nav.cerca_funzioni('', nav.FUNZIONI) == []


def test_progetti_fse_nel_menu_contabilita_non_in_navbar(app_reale):
    """Progetti FSE/FESR vive nel gruppo contabile del menu Impostazioni
    (accanto a Fondi e capitoli), non più come voce a sé in navbar; resta
    raggiungibile da ricerca, percorso e voce di navbar attiva."""
    from modules import navigazione as nav
    voce = next(v for v in nav.FUNZIONI if v['endpoint'] == 'progetti_fse.index')
    assert voce['gruppo'] == 'contrattazione'
    assert nav.area_navbar('progetti_fse.index') == 'impostazioni'

    c = _client_come(app_reale, 'dsga')
    corpo = c.get('/dashboard').get_data(as_text=True)
    assert 'data-area="progetti_fse"' not in corpo
    assert 'nav_area == \'progetti_fse\'' not in corpo
    # Dentro il menu a tendina, nel blocco "Contabilità e progetti".
    i = corpo.index('Contabilità e progetti')
    fine = corpo.index('nav-mega-titolo', i)
    assert 'Progetti FSE/FESR' in corpo[i:fine]
    # Ricerca (Ctrl+K) e pagina del modulo con voce Impostazioni attiva.
    assert 'Progetti FSE/FESR' in c.get('/ricerca?q=fesr').get_data(as_text=True)
    corpo = c.get('/progetti-fse').get_data(as_text=True)
    j = corpo.index('Impostazioni</a>')
    assert 'class="active"' in corpo[j - 900:j]
