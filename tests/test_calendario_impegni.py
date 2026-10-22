"""
Calendario degli impegni: raccolta delle fonti, sovrapposizioni riusate
dai controlli esistenti, filtro per docente, lezioni solo per docente,
privacy delle assenze, export iCal (nessuna lezione/assenza).
"""
from datetime import date, datetime
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.assenza import Assenza
from models.orario_docente import OrarioDocente
from tests.conftest import crea_docente

LUNEDI = date(2026, 10, 26)


def _riunione(titolo, d, ini, fine, docenti, tipo='altro', **kw):
    ev = AttivitaIst(tipo=tipo, titolo=titolo, data=d, ora_inizio=ini, ora_fine=fine,
                     origine='manuale', **kw)
    db.session.add(ev)
    db.session.flush()
    for doc in docenti:
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=doc.id))
    db.session.commit()
    return ev


def _registra(app):
    from routes.calendario import calendario_bp
    if 'calendario' not in app.blueprints:
        app.register_blueprint(calendario_bp)


def test_sovrapposizione_riunioni_marcata_su_entrambi(app, db_session):
    from modules.calendario_impegni import raccogli_impegni
    rossi, bianchi = crea_docente('Rossi'), crea_docente('Bianchi')
    _riunione('CdC 3A', LUNEDI, '14:30', '15:30', [rossi, bianchi])
    _riunione('Dipartimento', LUNEDI, '15:00', '16:00', [rossi])
    _riunione('Altra', LUNEDI, '17:00', '18:00', [rossi])

    imp = {e['titolo']: e for e in raccogli_impegni(LUNEDI, LUNEDI)}
    assert imp['CdC 3A']['conflitti'] and imp['Dipartimento']['conflitti']
    assert 'Rossi' in imp['CdC 3A']['conflitti'][0]
    assert imp['Altra']['conflitti'] == []


def test_filtro_docente_e_lezioni_solo_per_docente(app, db_session):
    from modules.calendario_impegni import raccogli_impegni
    rossi, bianchi = crea_docente('Rossi'), crea_docente('Bianchi')
    _riunione('Solo Bianchi', LUNEDI, '14:30', '15:30', [bianchi])
    db.session.add(OrarioDocente(id_docente=rossi.id, giorno=0, ora=1, classe='3A',
                                 materia='Mat', tipo_ora='lezione'))
    db.session.commit()

    istituto = raccogli_impegni(LUNEDI, LUNEDI)
    assert [e['titolo'] for e in istituto] == ['Solo Bianchi']      # niente lezioni
    r = raccogli_impegni(LUNEDI, LUNEDI, id_docente=rossi.id)
    assert [(e['fonte'], e['ora_inizio'], e['ora_fine']) for e in r] == [('lezione', '07:45', '08:40')]
    assert raccogli_impegni(LUNEDI, LUNEDI, id_docente=bianchi.id)[0]['titolo'] == 'Solo Bianchi'


def test_lezione_in_sovrapposizione_con_riunione_pomeridiana(app, db_session):
    from modules.calendario_impegni import raccogli_impegni
    rossi = crea_docente('Rossi')
    db.session.add(OrarioDocente(id_docente=rossi.id, giorno=0, ora=7, classe='3A',
                                 materia='Mat', tipo_ora='lezione'))
    _riunione('Collegio', LUNEDI, '14:00', '15:00', [rossi])
    r = raccogli_impegni(LUNEDI, LUNEDI, id_docente=rossi.id)
    assert all(e['conflitti'] for e in r) and len(r) == 2


def test_assenza_non_espone_il_motivo(app, db_session):
    from modules.calendario_impegni import raccogli_impegni
    rossi = crea_docente('Rossi')
    db.session.add(Assenza(id_docente=rossi.id, data=LUNEDI, ora_inizio=1, ora_fine=3,
                           motivo='malattia'))
    db.session.commit()
    e = raccogli_impegni(LUNEDI, LUNEDI)[0]
    assert e['titolo'] == 'Assenza Rossi' and 'malattia' not in str(e)
    assert (e['ora_inizio'], e['ora_fine']) == ('07:45', '10:40')


def test_ical_separa_formazione_e_piano_senza_lezioni(app, db_session):
    from modules.calendario_impegni import raccogli_impegni, genera_ics
    rossi = crea_docente('Rossi')
    _riunione('Corso sicurezza, base', LUNEDI, '14:30', '16:30', [rossi], tipo='formazione')
    _riunione('Collegio', LUNEDI, '14:30', '16:30', [rossi])
    db.session.add(OrarioDocente(id_docente=rossi.id, giorno=0, ora=1, classe='3A',
                                 materia='Mat', tipo_ora='lezione'))
    db.session.commit()

    f = genera_ics('Formazione', raccogli_impegni(LUNEDI, LUNEDI, fonti=['formazione']),
                   datetime(2026, 10, 22))
    p = genera_ics('Piano', raccogli_impegni(LUNEDI, LUNEDI, fonti=['piano']),
                   datetime(2026, 10, 22))
    assert 'SUMMARY:Corso sicurezza\\, base' in f and 'Collegio' not in f
    assert 'SUMMARY:Collegio' in p and 'Corso sicurezza' not in p
    assert 'DTSTART:20261026T143000' in p and 'Mat' not in p
    assert p.startswith('BEGIN:VCALENDAR\r\n') and p.endswith('END:VCALENDAR\r\n')


def test_route_dati_e_ical(app, db_session):
    _registra(app)
    rossi = crea_docente('Rossi')
    _riunione('Collegio', LUNEDI, '14:30', '16:30', [rossi])
    with app.test_client() as c:
        j = c.get('/calendario/dati?da=2026-10-26&a=2026-10-31').get_json()
        assert [e['titolo'] for e in j['impegni']] == ['Collegio']
        assert c.get('/calendario/dati?da=2026-10-26').status_code == 400
        assert c.get('/calendario/dati?da=2026-01-01&a=2026-12-31').status_code == 400
        r = c.get('/calendario/ical/piano.ics?anno=2026-2027')
        assert r.status_code == 200 and r.mimetype == 'text/calendar'
        assert b'SUMMARY:Collegio' in r.data
        assert c.get('/calendario/ical/lezioni.ics').status_code == 404
