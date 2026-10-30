"""Copia dell'orario (globale + sostegno) dal database di Drive: anteprima
in sola lettura, sostituzione solo su conferma, mai con un remoto vuoto."""
import sqlite3

import pytest
from sqlalchemy import create_engine

from models import db
from models.orario_docente import OrarioDocente
from models.orario_sostegno import OrarioSostegno
from modules import orario_da_drive as odd
from tests.conftest import crea_docente


@pytest.fixture
def remoto_path(tmp_path):
    path = tmp_path / 'remoto.db'
    engine = create_engine(f'sqlite:///{path}')
    db.metadata.create_all(engine)
    engine.dispose()
    return str(path)


def _remoto(path, tabella, righe):
    conn = sqlite3.connect(path)
    for r in righe:
        cols = ', '.join(r)
        conn.execute(f"INSERT INTO {tabella} ({cols}) VALUES ({', '.join('?' * len(r))})",
                     list(r.values()))
    conn.commit()
    conn.close()


def _slot(id_docente, giorno, ora, classe, tipo='lezione'):
    return {'id_docente': id_docente, 'giorno': giorno, 'ora': ora, 'classe': classe,
            'materia': 'Italiano', 'tipo_ora': tipo}


def test_confronta_non_scrive_e_mostra_le_differenze_con_i_nomi(app, db_session, remoto_path):
    d = crea_docente('Bianchi')
    db.session.commit()
    db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1, classe='1A',
                                 materia='Italiano'))
    db.session.commit()
    _remoto(remoto_path, 'orario_docenti', [_slot(d.id, 0, 1, '1A'), _slot(d.id, 1, 2, '2B')])

    esito = odd.confronta(db, remoto_path)

    glob = next(t for t in esito['tabelle'] if t['nome'] == 'orario_docenti')
    assert (glob['locali'], glob['remote'], glob['aggiunte'], glob['rimosse']) == (1, 2, 1, 0)
    assert glob['per_titolare'][0][0].startswith('Bianchi')
    assert OrarioDocente.query.count() == 1
    assert esito['applicabile']


def test_applica_sostituisce_globale_e_sostegno(app, db_session, remoto_path):
    d, s = crea_docente('Rossi'), crea_docente('Verdi')
    db.session.commit()
    db.session.add(OrarioDocente(id_docente=d.id, giorno=4, ora=5, classe='5Z'))
    db.session.add(OrarioSostegno(id_docente=s.id, giorno=0, ora=1, classe='1A'))
    db.session.commit()
    _remoto(remoto_path, 'orario_docenti', [_slot(d.id, 0, 1, '1A'), _slot(d.id, 1, 2, '2B')])
    _remoto(remoto_path, 'orario_sostegno', [
        {'id_docente': s.id, 'giorno': 2, 'ora': 3, 'classe': '3C'}])

    imp = odd.confronta(db, remoto_path)['impronta']
    scritte = odd.applica(db, remoto_path, imp)
    db.session.commit()

    assert scritte['orario_docenti'] == 2 and scritte['orario_sostegno'] == 1
    assert {(o.giorno, o.ora, o.classe) for o in OrarioDocente.query} == {(0, 1, '1A'), (1, 2, '2B')}
    assert [(o.giorno, o.ora) for o in OrarioSostegno.query] == [(2, 3)]


def test_remoto_senza_orario_globale_non_cancella_quello_locale(app, db_session, remoto_path):
    d = crea_docente('Neri')
    db.session.commit()
    db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1, classe='1A'))
    db.session.commit()

    esito = odd.confronta(db, remoto_path)
    assert not esito['applicabile']
    with pytest.raises(odd.RemotoSenzaOrario):
        odd.applica(db, remoto_path, esito['impronta'])
    assert OrarioDocente.query.count() == 1


def test_remoto_cambiato_dopo_anteprima_viene_rifiutato(app, db_session, remoto_path):
    d = crea_docente('Gialli')
    db.session.commit()
    _remoto(remoto_path, 'orario_docenti', [_slot(d.id, 0, 1, '1A')])
    imp = odd.confronta(db, remoto_path)['impronta']
    _remoto(remoto_path, 'orario_docenti', [_slot(d.id, 1, 1, '1B')])

    with pytest.raises(odd.RemotoSenzaOrario):
        odd.applica(db, remoto_path, imp)
    assert OrarioDocente.query.count() == 0


def test_righe_con_docente_inesistente_in_locale_sono_saltate(app, db_session, remoto_path):
    d = crea_docente('Blu')
    db.session.commit()
    _remoto(remoto_path, 'orario_docenti', [_slot(d.id, 0, 1, '1A'), _slot(9999, 0, 2, '1A')])

    esito = odd.confronta(db, remoto_path)
    glob = next(t for t in esito['tabelle'] if t['nome'] == 'orario_docenti')
    assert glob['saltate'] == 1

    odd.applica(db, remoto_path, esito['impronta'])
    db.session.commit()
    assert OrarioDocente.query.count() == 1


def test_pagine_si_rendono_e_applicano_su_app_reale(app_reale, tmp_path, monkeypatch):
    """Rendering vero di anteprima e applicazione (app su DB in /tmp, remoto finto)."""
    from models.docente import Docente
    path = tmp_path / 'remoto.db'
    engine = create_engine(f'sqlite:///{path}')
    db.metadata.create_all(engine)
    engine.dispose()
    with app_reale.app_context():
        d = Docente(cognome='Viola', nome='Anna', tipo_contratto='TI', attivo=True, ruolo='titolare')
        db.session.add(d)
        db.session.commit()
        id_d = d.id
    _remoto(str(path), 'orario_docenti', [_slot(id_d, 0, 1, '1A')])

    import routes.sincronizzazione as rs
    from datetime import datetime
    monkeypatch.setattr(rs, '_scarica_remoto_orario', lambda: (str(path), datetime(2026, 10, 30, 12, 0)))
    monkeypatch.setattr(rs, '_elimina_file', lambda p: None)

    client = app_reale.test_client()
    r = client.get('/sincronizzazione/orario-da-drive')
    assert r.status_code == 200 and b'Viola' in r.data

    import re
    imp = re.search(rb'name="impronta" value="([0-9a-f]+)"', r.data).group(1).decode()
    r = client.post('/sincronizzazione/orario-da-drive/applica', data={'impronta': imp},
                    follow_redirects=True)
    assert r.status_code == 200 and b'Orario copiato da Drive' in r.data
    with app_reale.app_context():
        assert OrarioDocente.query.count() == 1
