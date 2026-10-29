"""Render reale (copia del DB in /tmp) della pagina Notifiche supplenze e
del suo invio simulato, passando da CSRF e permessi veri."""
import re
from datetime import date, timedelta

from test_docente_nuovo_render import app_reale  # noqa: F401  (fixture)


def test_pagina_e_invio_simulato(app_reale, monkeypatch):
    from models import db
    from models.docente import Docente
    from models.supplenza import Supplenza
    from models.email_uscita import EmailUscita

    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    g = date.today() + timedelta(days=2)
    with app_reale.app_context():
        s = Docente(cognome='ProvaSost', nome='T', email='prova.sost@davincichiavenna.edu.it', attivo=True)
        a = Docente(cognome='ProvaAss', nome='T', attivo=True)
        db.session.add_all([s, a]); db.session.flush()
        db.session.add(Supplenza(data=g, ora=2, classe='1Z', id_assente=a.id,
                                 id_sostituto=s.id, stato='assegnata'))
        db.session.commit()
        id_s = s.id

    with app_reale.test_client() as c:
        r = c.get(f'/mail-bozze/notifiche-supplenze?data={g.isoformat()}')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert 'ProvaSost' in corpo and 'classe 1Z' in corpo and 'simulato' in corpo
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/notifiche-supplenze/invia',
                   data={'csrf_token': tok, 'data': g.isoformat(), 'docenti': [id_s]})
        assert r.status_code == 200 and 'simulata' in r.get_data(as_text=True)

    with app_reale.app_context():
        e = EmailUscita.query.filter_by(id_docente=id_s).one()
        assert e.stato == 'simulata'
        db.session.delete(e); db.session.commit()


def test_selettore_modalita_salva_e_si_vede(app_reale):
    from models import db
    from models.config_app import ConfigApp
    import re
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/notifiche-supplenze').get_data(as_text=True)
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/notifiche-supplenze/impostazioni',
                   data={'csrf_token': tok, 'modalita': 'simulato', 'solo_a': ''})
        assert r.status_code == 302
        assert '<option value="simulato" selected' in c.get(
            '/mail-bozze/notifiche-supplenze').get_data(as_text=True)
    with app_reale.app_context():
        for k in ('email_modalita', 'email_solo_a'):
            ConfigApp.query.filter_by(chiave=k).delete()
        db.session.commit()


def test_pagina_report_banca_ore_e_invio_simulato(app_reale, monkeypatch):
    import re
    from models import db
    from models.docente import Docente
    from models.email_uscita import EmailUscita
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app_reale.app_context():
        d = Docente(cognome='ProvaBanca', nome='T', email='prova.banca@davincichiavenna.edu.it', attivo=True)
        db.session.add(d); db.session.commit()
        id_d = d.id
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/report-banca-ore').get_data(as_text=True)
        assert 'ProvaBanca' in corpo and 'Corpo del messaggio' in corpo
        assert 'Seleziona tutti' in corpo and 'Deseleziona tutti' in corpo
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        mese = re.search(r'name="mese" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/report-banca-ore/invia',
                   data={'csrf_token': tok, 'mese': mese, 'docenti': [id_d],
                         'oggetto': 'Prova {MESE}', 'corpo': 'Testo mio per {COGNOME}'})
        assert r.status_code == 200 and 'simulata' in r.get_data(as_text=True)
        assert 'Testo mio per {COGNOME}' in c.get('/mail-bozze/report-banca-ore').get_data(as_text=True)
    with app_reale.app_context():
        from models.config_app import ConfigApp
        ConfigApp.query.filter(ConfigApp.chiave.in_(['email_bo_oggetto', 'email_bo_corpo'])).delete(synchronize_session=False)
        EmailUscita.query.filter_by(id_docente=id_d).delete()
        Docente.query.filter_by(id=id_d).delete()
        db.session.commit()


def test_salvataggio_modello_dalla_pagina(app_reale):
    import re
    from models import db
    from models.config_app import ConfigApp
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/notifiche-supplenze').get_data(as_text=True)
        assert 'Modello del messaggio' in corpo and 'Gentile collega,' in corpo
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/notifiche-supplenze/modello',
                   data={'csrf_token': tok, 'saluto': 'Buongiorno,', 'apertura': '', 'chiusura': ''})
        assert r.status_code == 302
        assert 'Buongiorno,' in c.get('/mail-bozze/notifiche-supplenze').get_data(as_text=True)
    with app_reale.app_context():
        ConfigApp.query.filter(ConfigApp.chiave.like('email_modello_%')).delete(synchronize_session=False)
        db.session.commit()


def test_bozze_email_porta_alla_pagina_banca_ore_e_vecchio_metodo_resta(app_reale):
    with app_reale.test_client() as c:
        r = c.get('/mail-bozze')
        assert r.status_code == 302 and r.headers['Location'].endswith('/mail-bozze/report-banca-ore')
        assert c.get('/mail-bozze/bozze-locali').status_code == 200
        assert 'bozze-locali' in c.get('/mail-bozze/report-banca-ore').get_data(as_text=True)


def test_impostazioni_dalla_pagina_banca_ore_tornano_alla_pagina_banca_ore(app_reale):
    import re
    from models import db
    from models.config_app import ConfigApp
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/report-banca-ore').get_data(as_text=True)
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/notifiche-supplenze/impostazioni',
                   data={'csrf_token': tok, 'modalita': 'off', 'solo_a': '', 'torna': 'banca_ore', 'mese': '2026-10'})
        assert r.status_code == 302 and '/mail-bozze/report-banca-ore' in r.headers['Location']
    with app_reale.app_context():
        ConfigApp.query.filter(ConfigApp.chiave.in_(['email_modalita', 'email_solo_a'])).delete(synchronize_session=False)
        db.session.commit()


def test_pagina_orari_docenti_e_invio_simulato(app_reale, monkeypatch):
    import re
    from models import db
    from models.docente import Docente
    from models.orario_docente import OrarioDocente
    from models.email_uscita import EmailUscita
    from models.config_app import ConfigApp
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app_reale.app_context():
        d = Docente(cognome='ProvaOrario', nome='T', email='prova.orario@davincichiavenna.edu.it', attivo=True)
        db.session.add(d); db.session.flush()
        db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1, classe='1Z', materia='Prova'))
        db.session.commit()
        id_d = d.id
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/orari-docenti?valido_dal=2026-11-03').get_data(as_text=True)
        assert 'ProvaOrario' in corpo and 'Seleziona tutti' in corpo and 'valido dal' in corpo.lower()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/orari-docenti/invia',
                   data={'csrf_token': tok, 'valido_dal': '2026-11-03', 'docenti': [id_d],
                         'oggetto': 'Orario {DATA}', 'corpo': 'Ecco {COGNOME}'})
        assert r.status_code == 200 and 'simulata' in r.get_data(as_text=True)
        assert c.get(f'/mail-bozze/orari-docenti/pdf/{id_d}?valido_dal=2026-11-03').status_code in (200, 503)
    with app_reale.app_context():
        ConfigApp.query.filter(ConfigApp.chiave.in_(['email_orario_oggetto', 'email_orario_corpo'])).delete(synchronize_session=False)
        EmailUscita.query.filter_by(id_docente=id_d).delete()
        OrarioDocente.query.filter_by(id_docente=id_d).delete()
        Docente.query.filter_by(id=id_d).delete()
        db.session.commit()


def test_pagina_calendario_docenti_e_invio_simulato(app_reale, monkeypatch):
    import re
    from models import db
    from models.docente import Docente
    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
    from models.email_uscita import EmailUscita
    from models.config_app import ConfigApp
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app_reale.app_context():
        d = Docente(cognome='ProvaCalendario', nome='T', email='prova.cal@davincichiavenna.edu.it', attivo=True)
        db.session.add(d); db.session.flush()
        ev = AttivitaIst(tipo='altro', titolo='Riunione di prova', data=date(2031, 3, 10),
                         ora_inizio='15:00', ora_fine='17:00', origine='manuale')
        db.session.add(ev); db.session.flush()
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id))
        db.session.commit()
        id_d, id_e = d.id, ev.id
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/calendario-docenti?mese=2031-03').get_data(as_text=True)
        assert 'ProvaCalendario' in corpo and 'Seleziona tutti' in corpo
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/calendario-docenti/invia',
                   data={'csrf_token': tok, 'mese': '2031-03', 'docenti': [id_d],
                         'oggetto': 'Impegni {MESE}', 'corpo': 'Ciao {COGNOME}'})
        assert r.status_code == 200 and 'simulata' in r.get_data(as_text=True)
        assert c.get(f'/mail-bozze/calendario-docenti/pdf/{id_d}?mese=2031-03').status_code in (200, 503)
        ics = c.get(f'/mail-bozze/calendario-docenti/ics/{id_d}?mese=2031-03')
        assert ics.status_code == 200 and b'Riunione di prova' in ics.data
        for url in ('mail-bozze/report-banca-ore', 'mail-bozze/orari-docenti', 'mail-bozze/notifiche-supplenze'):
            assert 'calendario-docenti' in c.get('/' + url).get_data(as_text=True)
    with app_reale.app_context():
        ConfigApp.query.filter(ConfigApp.chiave.like('email_cal_%')).delete(synchronize_session=False)
        EmailUscita.query.filter_by(id_docente=id_d).delete()
        AttivitaIstPartecipante.query.filter_by(id_attivita=id_e).delete()
        AttivitaIst.query.filter_by(id=id_e).delete()
        Docente.query.filter_by(id=id_d).delete()
        db.session.commit()


def test_intestazione_notifiche_supplenze_ha_i_pulsanti_delle_altre_pagine(app_reale):
    with app_reale.test_client() as c:
        corpo = c.get('/mail-bozze/notifiche-supplenze').get_data(as_text=True)
        for url in ('/mail-bozze/report-banca-ore', '/mail-bozze/orari-docenti', '/mail-bozze/calendario-docenti'):
            assert f'href="{url}"' in corpo
