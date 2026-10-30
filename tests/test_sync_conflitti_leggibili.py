"""
Pagina /sync/conflitti leggibile: nomi dei docenti al posto degli id, data e
ora in italiano, contesto della riga e ultima modifica di ciascuna versione.
"""
import json
from datetime import date, datetime

from models import db
from models.attivita_ist import AttivitaIst
from models.docente import Docente
from models.sync_conflitto import SyncConflitto
from modules.sync_conflitti_vista import valore_leggibile, carica_nomi_docenti


def _docente(cognome, nome):
    d = Docente(cognome=cognome, nome=nome, ore_contratto=18, attivo=True)
    db.session.add(d)
    db.session.flush()
    return d


def _conflitto(tabella, chiave, locale, remoto, diversi, descrizione='x', **kw):
    c = SyncConflitto(tabella=tabella, chiave_logica=json.dumps(chiave, sort_keys=True),
                      descrizione=descrizione, campi_diversi=json.dumps(diversi),
                      dati_locali=json.dumps(locale, default=str),
                      dati_remoti=json.dumps(remoto, default=str), **kw)
    db.session.add(c)
    db.session.commit()
    return c


def _pagina(app):
    with app.test_client() as client:
        r = client.get('/sync/conflitti')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert 'Errore imprevisto' not in corpo
        return corpo


def test_valori_leggibili():
    nomi = {3: 'ROSSI Mario'}
    assert valore_leggibile('id_sostituto', 3, nomi) == 'ROSSI Mario'
    assert valore_leggibile('id_sostituto', None, nomi) == 'nessuno'
    assert 'non in anagrafica' in valore_leggibile('id_sostituto', 99, nomi)
    assert valore_leggibile('classe_libera', 1, nomi) == 'Sì'
    assert valore_leggibile('classe_libera', 0, nomi) == 'No'
    assert valore_leggibile('data', '2026-10-15', nomi) == 'gio 15/10/2026'
    assert valore_leggibile('modificato_il', '2026-10-15 09:30:00', nomi) == '15/10/2026 09:30'
    assert valore_leggibile('stato', 'in_attesa', nomi) == 'in attesa'
    assert valore_leggibile('note', None, nomi) == '—'


def test_supplenza_mostra_i_nomi_non_gli_id(app_reale):
    with app_reale.app_context():
        assente = _docente('Bianchi', 'Anna')
        a, b = _docente('Rossi', 'Mario'), _docente('Verdi', 'Luca')
        base = {'data': '2026-10-15', 'ora': 3, 'classe': '2B', 'id_assente': assente.id}
        _conflitto('supplenze', base,
                   {**base, 'id_sostituto': a.id, 'stato': 'assegnata',
                    'modificato_il': '2026-10-15 09:30:00', 'creato_da': 'segreteria'},
                   {**base, 'id_sostituto': b.id, 'stato': 'assegnata',
                    'modificato_il': '2026-10-15 10:45:00', 'creato_da': 'vicepreside'},
                   ['id_sostituto'])
    corpo = _pagina(app_reale)
    assert 'BIANCHI Anna' in corpo                 # nel titolo
    assert 'ROSSI Mario' in corpo and 'VERDI Luca' in corpo
    assert 'gio 15/10/2026' in corpo and '2B' in corpo
    assert 'modificata il 15/10/2026 09:30' in corpo
    assert 'modificata il 15/10/2026 10:45' in corpo
    assert 'docente #' not in corpo


def test_assenza_con_motivo_diverso(app_reale):
    with app_reale.app_context():
        d = _docente('Neri', 'Paola')
        k = {'id_docente': d.id, 'data': '2026-10-12', 'ora_inizio': 1, 'ora_fine': 3}
        _conflitto('assenze', k, {**k, 'motivo': 'lutto', 'classe_libera': 0},
                   {**k, 'motivo': 'malattia', 'classe_libera': 1}, ['motivo', 'classe_libera'])
    corpo = _pagina(app_reale)
    assert 'Assenza di NERI Paola' in corpo
    assert 'dalla 1ª alla 3ª ora' in corpo
    assert 'lutto' in corpo and 'malattia' in corpo
    assert 'Sì' in corpo and 'No' in corpo


def test_sostituzione_scrutinio_mostra_evento_e_nomi(app_reale):
    with app_reale.app_context():
        assente, sost = _docente('Gialli', 'Elena'), _docente('Blu', 'Marco')
        ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 3A', data=date(2026, 12, 14))
        db.session.add(ev)
        db.session.flush()
        k = {'id_attivita': ev.id, 'id_assente': assente.id}
        _conflitto('sostituzioni_scrutinio', k,
                   {**k, 'id_sostituto': sost.id, 'n_protocollo': '12'},
                   {**k, 'id_sostituto': None, 'n_protocollo': '13'},
                   ['id_sostituto', 'n_protocollo'])
    corpo = _pagina(app_reale)
    assert 'GIALLI Elena' in corpo and 'BLU Marco' in corpo
    assert 'Scrutinio 3A' in corpo and 'lun 14/12/2026' in corpo
    assert 'nessuno' in corpo


def test_conflitto_anagrafica_e_risolti_recenti_leggibili(app_reale):
    with app_reale.app_context():
        d = _docente('Rossi', 'Mario')
        k = {'cognome': 'Rossi', 'nome': 'Mario'}
        _conflitto('docenti', k, {'email': 'a@scuola.test'}, {'email': 'b@scuola.test'},
                   ['email'], descrizione='Anagrafica docente — Rossi Mario')
        a = _docente('Verdi', 'Anna')
        base = {'id_docente': a.id, 'data': '2026-10-01', 'ora': 2}
        _conflitto('indisponibilita', base, {**base, 'motivo': 'altro'}, {**base, 'motivo': 'visita'},
                   ['motivo'], risolto=True, scelta='locale', risolto_da='dsga',
                   risolto_il=datetime(2026, 10, 2, 8, 0))
    corpo = _pagina(app_reale)
    assert 'Anagrafica di Rossi Mario' in corpo and 'a@scuola.test' in corpo
    assert 'Email' in corpo
    assert 'Indisponibilità di VERDI Anna' in corpo   # nell'elenco dei risolti
    assert 'docente #' not in corpo


def test_carica_nomi_ignora_valori_non_validi(app_reale):
    with app_reale.app_context():
        d = _docente('Rossi', 'Mario')
        assert carica_nomi_docenti([d.id, None, 'x', '']) == {d.id: 'ROSSI Mario'}
        assert carica_nomi_docenti([]) == {}
