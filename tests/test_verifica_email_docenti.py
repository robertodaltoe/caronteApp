"""
Verifica email docenti da CSV della console Workspace (Directory -> Utenti ->
Scarica utenti). Dati finti: nessun nominativo reale.
"""
from io import BytesIO

import pytest

from models import db
from models.docente import Docente
from tests.conftest import crea_docente

from modules.verifica_email_docenti import (
    leggi_csv, confronta, normalizza, ErroreCsv)

INTESTAZIONE = ('First Name [Required],Last Name [Required],Email Address [Required],'
                'Password [Required],Status [READ ONLY],Org Unit Path [Required]\n')


def _csv(*righe, intestazione=INTESTAZIONE):
    return (intestazione + ''.join(righe)).encode('utf-8')


def _riga(nome, cognome, email, stato='Active', ou='/Docenti'):
    return f'{nome},{cognome},{email},,{stato},{ou}\n'


# ── lettura del CSV ────────────────────────────────────────────────────

def test_legge_csv_console_con_intestazioni_google():
    utenti = leggi_csv(_csv(_riga('Mario', 'Rossi', 'Mario.Rossi@scuola.test')))
    assert utenti == [{'nome': 'Mario', 'cognome': 'Rossi',
                       'email': 'mario.rossi@scuola.test',
                       'stato': 'Active', 'ou': '/Docenti'}]


def test_legge_csv_con_bom_punto_e_virgola_e_intestazioni_italiane():
    testo = ('Nome;Cognome;Indirizzo email\n'
             'Anna;Verdi;anna.verdi@scuola.test\n').encode('utf-8-sig')
    utenti = leggi_csv(testo)
    assert utenti[0]['email'] == 'anna.verdi@scuola.test'
    assert utenti[0]['stato'] == ''


def test_legge_csv_latin1():
    testo = 'Nome,Cognome,Email\nNicolò,Dall’Oglio,n@scuola.test\n'.encode('latin-1', 'replace')
    assert leggi_csv(testo)[0]['email'] == 'n@scuola.test'


def test_csv_senza_colonna_email_e_un_errore_chiaro():
    with pytest.raises(ErroreCsv):
        leggi_csv(b'Nome,Cognome\nMario,Rossi\n')


def test_csv_vuoto_e_un_errore():
    with pytest.raises(ErroreCsv):
        leggi_csv(b'')


def test_righe_senza_email_valida_sono_ignorate():
    utenti = leggi_csv(_csv(_riga('A', 'B', ''), _riga('C', 'D', 'non-una-mail')))
    assert utenti == []


def test_normalizza_accenti_apostrofi_maiuscole():
    assert normalizza("  Dall’Òglio-Rossi ") == 'dalloglio rossi'


# ── confronto ──────────────────────────────────────────────────────────

def _confronta(app, utenti):
    return confronta(utenti, Docente.query.all())


def _u(nome, cognome, email, stato='Active', ou='/Docenti'):
    return {'nome': nome, 'cognome': cognome, 'email': email.lower(),
            'stato': stato, 'ou': ou}


def test_email_gia_corretta_e_ok(app, db_session):
    d = crea_docente('Rossi', nome='Mario')
    d.email = 'Mario.Rossi@scuola.test'
    db.session.commit()
    r = _confronta(app, [_u('Mario', 'Rossi', 'mario.rossi@scuola.test')])
    assert [x['docente'].id for x in r['ok']] == [d.id]
    assert not r['da_impostare'] and not r['differenti']


def test_email_mancante_viene_proposta(app, db_session):
    d = crea_docente('Rossi', nome='Mario')
    for vuoto in (None, '', 'None'):
        d.email = vuoto
        db.session.commit()
        r = _confronta(app, [_u('Mario', 'Rossi', 'mario.rossi@scuola.test')])
        assert len(r['da_impostare']) == 1
        assert r['da_impostare'][0]['email_nuova'] == 'mario.rossi@scuola.test'


def test_email_diversa_e_segnalata_non_sovrascritta(app, db_session):
    d = crea_docente('Rossi', nome='Mario')
    d.email = 'mrossi@scuola.test'
    db.session.commit()
    r = _confronta(app, [_u('Mario', 'Rossi', 'mario.rossi@scuola.test')])
    assert len(r['differenti']) == 1
    assert r['differenti'][0]['email_attuale'] == 'mrossi@scuola.test'
    assert r['differenti'][0]['email_nuova'] == 'mario.rossi@scuola.test'


def test_abbinamento_ignora_accenti_ordine_e_maiuscole(app, db_session):
    crea_docente('DE LUCA', nome='Nicolò')
    r = _confronta(app, [_u('Nicolo', 'De Luca', 'nicolo.deluca@scuola.test')])
    assert len(r['da_impostare']) == 1


def test_abbinamento_per_parte_locale_dellemail(app, db_session):
    # nome in Workspace scritto in modo diverso, ma l'indirizzo e' nome.cognome
    crea_docente('Bianchi', nome='Giovanni Battista')
    r = _confronta(app, [_u('Gianbattista', 'B.', 'giovanni.battista.bianchi@scuola.test')])
    assert len(r['da_impostare']) == 1


def test_omonimi_sono_ambigui_e_non_proposti(app, db_session):
    crea_docente('Rossi', nome='Mario')
    crea_docente('Rossi', nome='Mario')
    r = _confronta(app, [_u('Mario', 'Rossi', 'mario.rossi@scuola.test')])
    assert len(r['ambigui']) == 1
    assert not r['da_impostare']


def test_due_account_per_lo_stesso_docente_sono_ambigui(app, db_session):
    crea_docente('Rossi', nome='Mario')
    r = _confronta(app, [_u('Mario', 'Rossi', 'mario.rossi@scuola.test'),
                         _u('Mario', 'Rossi', 'm.rossi@scuola.test')])
    assert len(r['ambigui']) == 1
    assert not r['da_impostare']


def test_stessa_email_su_due_docenti_e_ambigua(app, db_session):
    a = crea_docente('Rossi', nome='Mario')
    b = crea_docente('Bianchi', nome='Luca')
    a.email = b.email = 'condivisa@scuola.test'
    db.session.commit()
    r = _confronta(app, [_u('Mario', 'Rossi', 'condivisa@scuola.test')])
    assert r['ambigui']


def test_email_abbinata_ma_nome_diverso_non_si_tocca(app, db_session):
    # caso tipo "Ghezzi Angelo con l'email di Andrea": segnalato, mai corretto
    d = crea_docente('Ghezzi', nome='Angelo')
    d.email = 'andrea.ghezzi@scuola.test'
    db.session.commit()
    r = _confronta(app, [_u('Andrea', 'Ghezzi', 'andrea.ghezzi@scuola.test')])
    assert [x['docente'].id for x in r['nome_diverso']] == [d.id]
    assert not r['ok'] and not r['differenti']


def test_docenti_attivi_senza_account_e_account_senza_docente(app, db_session):
    crea_docente('Rossi', nome='Mario')
    crea_docente('Uscito', nome='Paolo', attivo=False)
    r = _confronta(app, [_u('Anna', 'Sconosciuta', 'anna.sconosciuta@scuola.test')])
    assert [d.cognome for d in r['docenti_senza_account']] == ['Rossi']
    assert [u['email'] for u in r['account_senza_docente']] == ['anna.sconosciuta@scuola.test']


def test_account_sospeso_con_docente_attivo_e_segnalato(app, db_session):
    crea_docente('Rossi', nome='Mario')
    r = _confronta(app, [_u('Mario', 'Rossi', 'mario.rossi@scuola.test', stato='Suspended')])
    assert len(r['sospesi_con_docente_attivo']) == 1
    # un account sospeso non va proposto come email da impostare
    assert not r['da_impostare']


def test_account_attivo_di_docente_non_piu_attivo_e_segnalato(app, db_session):
    crea_docente('Uscito', nome='Paolo', attivo=False)
    r = _confronta(app, [_u('Paolo', 'Uscito', 'paolo.uscito@scuola.test')])
    assert len(r['account_attivo_docente_inattivo']) == 1
    assert not r['da_impostare']


# ── route: anteprima e applicazione (app reale su DB isolato in /tmp) ──

@pytest.fixture
def app_reale():
    """App vera (app.py::create_app) su un database vuoto in /tmp: mai il
    database.db reale (CLAUDE.md, regola 1). Stesso schema di
    tests/test_docente_nuovo_render.py."""
    import os
    import shutil
    import tempfile
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp_dir = tempfile.mkdtemp()
    db_copia = os.path.join(tmp_dir, 'database_test_email.db')
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


def _nuovo_docente(app_reale, cognome, nome, email=None):
    with app_reale.app_context():
        d = Docente(cognome=cognome, nome=nome, ore_contratto=18, attivo=True, email=email)
        db.session.add(d)
        db.session.commit()
        return d.id


def _email(app_reale, id_docente):
    with app_reale.app_context():
        return db.session.get(Docente, id_docente).email


def test_pagina_e_anteprima_si_vedono_e_non_scrivono(app_reale):
    id_d = _nuovo_docente(app_reale, 'Rossi', 'Mario')
    with app_reale.test_client() as c:
        r = c.get('/docenti/verifica-email')
        assert r.status_code == 200
        assert 'Verifica email docenti' in r.get_data(as_text=True)
        r = c.post('/docenti/verifica-email', data={
            'file': (BytesIO(_csv(_riga('Mario', 'Rossi', 'mario.rossi@scuola.test'))), 'u.csv')},
            content_type='multipart/form-data')
        corpo = r.get_data(as_text=True)
        assert r.status_code == 200
        assert 'mario.rossi@scuola.test' in corpo
        assert 'Errore imprevisto' not in corpo
    assert _email(app_reale, id_d) in (None, '')


def test_file_non_valido_non_va_in_errore(app_reale):
    with app_reale.test_client() as c:
        r = c.post('/docenti/verifica-email', data={
            'file': (BytesIO(b'Nome,Cognome\nA,B\n'), 'u.csv')},
            content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        assert 'File non leggibile' in r.get_data(as_text=True)


def test_applica_scrive_solo_le_righe_selezionate_e_fa_il_backup(app_reale):
    import glob
    import os
    ida = _nuovo_docente(app_reale, 'Rossi', 'Mario')
    idb = _nuovo_docente(app_reale, 'Verdi', 'Anna')
    with app_reale.test_client() as c:
        r = c.post('/docenti/verifica-email/applica',
                   data={'riga': [f'{ida}||Mario.Rossi@scuola.test']})
        assert r.status_code in (302, 303)
    assert _email(app_reale, ida) == 'mario.rossi@scuola.test'
    assert _email(app_reale, idb) in (None, '')
    uri = app_reale.config['SQLALCHEMY_DATABASE_URI']
    cartella = os.path.dirname(uri[len('sqlite:///'):])
    assert glob.glob(os.path.join(cartella, 'data', 'backup', '*pre_import_email_docenti*.db.enc'))


def test_applica_salta_se_l_email_e_cambiata_nel_frattempo(app_reale):
    ida = _nuovo_docente(app_reale, 'Rossi', 'Mario', email='cambiata@scuola.test')
    with app_reale.test_client() as c:
        c.post('/docenti/verifica-email/applica',
               data={'riga': [f'{ida}|vecchia@scuola.test|mario.rossi@scuola.test']})
    assert _email(app_reale, ida) == 'cambiata@scuola.test'


def test_applica_rifiuta_email_non_valide_o_gia_di_un_altro_docente(app_reale):
    ida = _nuovo_docente(app_reale, 'Rossi', 'Mario')
    _nuovo_docente(app_reale, 'Verdi', 'Anna', email='gia.usata@scuola.test')
    with app_reale.test_client() as c:
        c.post('/docenti/verifica-email/applica', data={'riga': [
            f'{ida}||non-una-mail', f'{ida}||GIA.USATA@scuola.test']})
    assert _email(app_reale, ida) in (None, '')


def test_voce_nel_menu_di_navigazione():
    from modules.navigazione import FUNZIONI
    assert any(f['endpoint'] == 'docenti.verifica_email' for f in FUNZIONI)
